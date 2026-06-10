import asyncio
import json
import time
from ...models.domain import StartupProfile, AgentResult, LegalFlag, LegalProfile, LegalFlagType, Severity, AgentStatus
from ...llm.ollama_client import OllamaClient
from ...config.settings import Settings
from ...tools.legal.legal_tools import (
    search_litigation,
    check_patent_activity,
    check_trademark_status,
    check_incorporation_status,
    search_regulatory_issues,
)

class LegalAgent:
    """Agent responsible for checking incorporation details, identifying active litigation, IP holdings, and regulatory flags."""

    def __init__(self, ollama_client: OllamaClient, tools: dict, settings: Settings):
        """Initialize the legal analysis agent with clients, tools, and configurations."""
        self.ollama_client = ollama_client
        self.tools = tools
        self.settings = settings

    async def run(self, startup: StartupProfile) -> AgentResult:
        """Check legal status: incorporation, litigation, IP, regulatory compliance."""
        start_time = time.monotonic()
        raw_data = {}
        try:
            # Step 1: Gather raw legal data in parallel
            raw_data = await self._gather_legal_data(startup)

            # Step 2: Classify findings into legal flags using LLM
            flags = await self._classify_legal_flags(raw_data, startup)

            # Step 3: Build final LegalProfile
            profile = await self._build_legal_profile(startup, flags, raw_data)

            # Step 4: Calculate risk score
            risk_score = self._calculate_legal_risk_score(flags)

            # Step 5: Aggregate unique source URLs
            sources = []
            for lit in raw_data.get("litigation", []):
                if lit.get("source_url"):
                    sources.append(lit["source_url"])
            patents_src = raw_data.get("patents", {}).get("source")
            if patents_src:
                sources.append(patents_src)
            trademarks_src = raw_data.get("trademarks", {}).get("source")
            if trademarks_src:
                sources.append(trademarks_src)
            for reg in raw_data.get("regulatory", []):
                if reg.get("source"):
                    sources.append(reg["source"])
            unique_sources = sorted(list(set(sources)))

            # Package output data and embed risk score in metadata
            data_dict = profile.model_dump() if hasattr(profile, "model_dump") else profile.dict()
            data_dict["legal_risk_score"] = risk_score
            data_dict["metadata"] = {"legal_risk_score": risk_score}

            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="legal",
                status=AgentStatus.SUCCESS,
                data=data_dict,
                error=None,
                duration_ms=duration_ms,
                sources=unique_sources,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="legal",
                status=AgentStatus.FAILED,
                data=None,
                error=f"Execution error: {str(e)}",
                duration_ms=duration_ms,
                sources=[],
            )

    async def _gather_legal_data(self, startup: StartupProfile) -> dict:
        """Parallel: litigation search + patents + trademarks + incorporation + regulatory."""
        results = await asyncio.gather(
            search_litigation(startup.name),
            check_patent_activity(startup.name),
            check_trademark_status(startup.name),
            check_incorporation_status(startup.name),
            search_regulatory_issues(startup.name, startup.industry),
            return_exceptions=True,
        )

        litigation_res = results[0] if not isinstance(results[0], Exception) else []
        patents_res = results[1] if not isinstance(results[1], Exception) else {}
        trademarks_res = results[2] if not isinstance(results[2], Exception) else {}
        incorporation_res = results[3] if not isinstance(results[3], Exception) else {}
        regulatory_res = results[4] if not isinstance(results[4], Exception) else []

        return {
            "litigation": litigation_res,
            "patents": patents_res,
            "trademarks": trademarks_res,
            "incorporation": incorporation_res,
            "regulatory": regulatory_res,
        }

    async def _classify_legal_flags(
        self, raw_data: dict, startup: StartupProfile
    ) -> list[LegalFlag]:
        """LLM classifies each legal finding into LegalFlag with severity."""
        prompt = self._build_classification_prompt(raw_data, startup)
        try:
            response = await self.ollama_client.generate(
                prompt=prompt,
                model=self.settings.OLLAMA_ANALYST_MODEL,
                expect_json=True,
            )

            if isinstance(response, str):
                data = json.loads(response)
            else:
                data = response

            flags = []
            for item in data.get("flags", []):
                flag_type_str = (item.get("flag_type") or "NONE").upper()
                severity_str = (item.get("severity") or "NONE").upper()

                if flag_type_str in ("NONE", "") or severity_str in ("NONE", ""):
                    continue

                try:
                    flag_type = LegalFlagType(flag_type_str)
                    severity = Severity(severity_str)

                    flags.append(LegalFlag(
                        flag_type=flag_type,
                        severity=severity,
                        description=item.get("description") or "Legal issue identified.",
                        source=item.get("source") or "unknown",
                    ))
                except ValueError:
                    pass

            return flags
        except Exception:
            return []

    async def _build_legal_profile(
        self, startup: StartupProfile, flags: list[LegalFlag], raw_data: dict
    ) -> LegalProfile:
        """Assemble final LegalProfile from all gathered data."""
        inc_data = raw_data.get("incorporation", {})
        is_inc = inc_data.get("incorporated", False)
        jur = inc_data.get("jurisdiction", "unknown")
        inc_status = f"Incorporated in {jur}" if is_inc else "Not incorporated/Unknown status"

        patents_data = raw_data.get("patents", {})
        patent_count = patents_data.get("patent_count_estimate", 0)

        trademarks_data = raw_data.get("trademarks", {})
        trademark_count = trademarks_data.get("trademark_count_estimate", 0)

        return LegalProfile(
            startup_name=startup.name,
            incorporation_status=inc_status,
            flags=flags,
            patent_count=patent_count,
            trademark_count=trademark_count,
        )

    def _build_classification_prompt(self, raw_data: dict, startup: StartupProfile) -> str:
        """Build the Ollama prompt for legal flag classification."""
        schema = {
            "flags": [
                {
                    "flag_type": "string (LAWSUIT | REGULATORY | IP_DISPUTE | COMPLIANCE | NONE)",
                    "severity": "string (HIGH | MEDIUM | LOW | NONE)",
                    "description": "string (one sentence)",
                    "source": "string"
                }
            ]
        }
        return (
            f"You are a legal diligence expert assessing the startup '{startup.name}' "
            f"in the '{startup.industry}' industry.\n\n"
            f"Here is raw legal research data gathered:\n"
            f"{json.dumps(raw_data, indent=2)}\n\n"
            f"Please analyze these findings and classify any active issues, lawsuits, or regulatory/compliance concerns into legal flags.\n\n"
            f"You MUST return a JSON object adhering to this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"If there are no issues, return an empty list for 'flags'.\n"
            f"Do not include any chat prefix or suffix. Return ONLY the JSON object."
        )

    def _calculate_legal_risk_score(self, flags: list[LegalFlag]) -> float:
        """0.0 (clean) to 1.0 (severe) based on flag severities."""
        if not flags:
            return 0.0
        total = 0.0
        for f in flags:
            sev = f.severity.upper() if isinstance(f.severity, str) else f.severity.value.upper()
            if sev == "HIGH":
                total += 0.4
            elif sev == "MEDIUM":
                total += 0.2
            elif sev == "LOW":
                total += 0.05
        return min(1.0, total)
