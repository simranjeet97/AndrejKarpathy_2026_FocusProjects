import asyncio
import json
import re
import time
from ...models.domain import StartupProfile, AgentResult, FinancialProfile, FinancialSignal, AgentStatus
from ...llm.ollama_client import OllamaClient
from ...config.settings import Settings
from ...tools.financial.financial_tools import (
    get_sec_edgar_filings,
    get_crunchbase_signals,
    get_pitchbook_signals,
    estimate_revenue,
    get_job_posting_signals,
)

class FinancialAgent:
    """Agent responsible for gathering financial signals, estimating burn rate/runway, and profiling funding history."""

    def __init__(self, ollama_client: OllamaClient, tools: dict, settings: Settings):
        """Initialize the financial analysis agent with clients, tools, and configurations."""
        self.ollama_client = ollama_client
        self.tools = tools
        self.settings = settings

    async def run(self, startup: StartupProfile) -> AgentResult:
        """Gather financial signals: funding history, revenue estimates, burn indicators."""
        start_time = time.monotonic()
        raw_data = {}
        try:
            # Step 1: Gather financial raw signals in parallel
            raw_data = await self._gather_financial_signals(startup)

            # Step 2: Analyze financial profile using LLM and heuristics
            profile = await self._analyze_financial_health(raw_data, startup)

            # Step 3: Track unique source URLs
            sources = []
            for f in raw_data.get("sec", []):
                if f.get("url"):
                    sources.append(f["url"])
            sources.extend(raw_data.get("revenue", {}).get("sources", []))
            hiring_src = raw_data.get("hiring", {}).get("source")
            if hiring_src:
                sources.append(hiring_src)
            unique_sources = sorted(list(set(sources)))

            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="financial",
                status=AgentStatus.SUCCESS,
                data=profile.model_dump() if hasattr(profile, "model_dump") else profile.dict(),
                error=None,
                duration_ms=duration_ms,
                sources=unique_sources,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="financial",
                status=AgentStatus.FAILED,
                data=None,
                error=f"Execution error: {str(e)}",
                duration_ms=duration_ms,
                sources=[],
            )

    async def _gather_financial_signals(self, startup: StartupProfile) -> dict:
        """Parallel fetch from EDGAR, Crunchbase signals, job postings, revenue search."""
        results = await asyncio.gather(
            get_sec_edgar_filings(startup.name),
            get_crunchbase_signals(startup.name),
            get_pitchbook_signals(startup.name),
            estimate_revenue(startup.name, startup.industry),
            get_job_posting_signals(startup.name),
            return_exceptions=True,
        )

        sec_res = results[0] if not isinstance(results[0], Exception) else []
        crunchbase_res = results[1] if not isinstance(results[1], Exception) else {}
        pitchbook_res = results[2] if not isinstance(results[2], Exception) else {}
        revenue_res =  results[3] if not isinstance(results[3], Exception) else {}
        hiring_res = results[4] if not isinstance(results[4], Exception) else {}

        return {
            "sec": sec_res,
            "crunchbase": crunchbase_res,
            "pitchbook": pitchbook_res,
            "revenue": revenue_res,
            "hiring": hiring_res,
        }

    async def _parse_funding_rounds(self, raw_data: dict) -> list[dict]:
        """Extract structured funding rounds from raw signal data."""
        mentions = []
        crunchbase_mentions = raw_data.get("crunchbase", {}).get("funding_mentions", [])
        pitchbook_mentions = raw_data.get("pitchbook", {}).get("funding_mentions", [])

        for m in crunchbase_mentions:
            mentions.append((m, "Crunchbase Search"))
        for m in pitchbook_mentions:
            mentions.append((m, "PitchBook Search"))

        extracted = {}
        round_pattern = r'(?i)\b(Seed|Series\s+[A-F]|Pre-seed|Angel|Venture|Debt)\b'
        amount_pattern = r'(?i)\$[\d,.]+\s*(?:million|billion|M|B)?\b'

        for text, source in mentions:
            round_match = re.search(round_pattern, text)
            if round_match:
                round_name = round_match.group(1).title()
                amount_match = re.search(amount_pattern, text)
                amount_str = amount_match.group(0) if amount_match else "unknown"

                date_match = re.search(r'\b(20\d{2})\b', text)
                date_str = date_match.group(1) if date_match else "unknown"

                if round_name not in extracted:
                    extracted[round_name] = {
                        "round": round_name,
                        "amount_str": amount_str,
                        "date_str": date_str,
                        "source": source,
                    }

        return list(extracted.values())

    async def _analyze_financial_health(
        self, raw_data: dict, startup: StartupProfile
    ) -> FinancialProfile:
        """LLM analysis of financial health based on all signals."""
        prompt = self._build_financial_prompt(raw_data, startup)
        funding_rounds = await self._parse_funding_rounds(raw_data)
        heuristic_burn, heuristic_runway = self._estimate_burn_runway(raw_data)

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

            signals_list = []
            for sig in data.get("signals", []):
                signals_list.append(FinancialSignal(
                    metric_name=sig.get("metric_name") or "unknown",
                    value=sig.get("value") or "unknown",
                    period=sig.get("period") or "unknown",
                    source=sig.get("source") or "unknown",
                    confidence=float(sig.get("confidence") or 0.5),
                ))

            if not signals_list:
                rev_est = raw_data.get("revenue", {}).get("revenue_estimate", "Not found")
                if rev_est != "Not found":
                    signals_list.append(FinancialSignal(
                        metric_name="ARR",
                        value=rev_est,
                        period="2024",
                        source="Web Search",
                        confidence=0.5,
                    ))

            burn_rate = data.get("burn_rate_estimate") or heuristic_burn or "unknown"
            runway = data.get("runway_estimate") or heuristic_runway or "unknown"
            if burn_rate == "unknown" or not burn_rate:
                burn_rate = heuristic_burn
            if runway == "unknown" or not runway:
                runway = heuristic_runway

            return FinancialProfile(
                startup_name=startup.name,
                signals=signals_list,
                funding_rounds=funding_rounds,
                burn_rate_estimate=burn_rate,
                runway_estimate=runway,
            )
        except Exception:
            # Fallback construction on LLM extraction failure
            signals_list = []
            rev_est = raw_data.get("revenue", {}).get("revenue_estimate", "Not found")
            if rev_est != "Not found":
                signals_list.append(FinancialSignal(
                    metric_name="ARR",
                    value=rev_est,
                    period="2024",
                    source="Web Search",
                    confidence=0.4,
                ))

            return FinancialProfile(
                startup_name=startup.name,
                signals=signals_list,
                funding_rounds=funding_rounds,
                burn_rate_estimate=heuristic_burn,
                runway_estimate=heuristic_runway,
            )

    def _build_financial_prompt(self, raw_data: dict, startup: StartupProfile) -> str:
        """Build the Ollama prompt for financial health analysis."""
        schema = {
            "signals": [
                {
                    "metric_name": "string (e.g. ARR, Total Funding, Valuation)",
                    "value": "string (value with units)",
                    "period": "string (e.g. 2024, Q3 2024, FY2025)",
                    "source": "string",
                    "confidence": "float (0.0 to 1.0)",
                }
            ],
            "burn_rate_estimate": "string (e.g. high, moderate, low, or specific dollar amount)",
            "runway_estimate": "string (e.g. 18 months, unknown)"
        }
        return (
            f"You are a financial diligence expert assessing the startup '{startup.name}' "
            f"in the '{startup.industry}' industry.\n\n"
            f"Here is the raw financial signal data gathered:\n"
            f"{json.dumps(raw_data, indent=2)}\n\n"
            f"Please analyze these signals, identify any financial metrics (such as revenue/ARR, funding totals, valuation), "
            f"and evaluate the financial risk/health.\n\n"
            f"You MUST return a JSON object adhering to this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"Do not include any chat prefix or suffix. Return ONLY the JSON object."
        )

    def _estimate_burn_runway(self, signals: dict) -> tuple[str, str]:
        """Heuristic estimates for burn rate and runway from hiring/funding signals."""
        hiring_sig = signals.get("hiring", {}).get("hiring_signal", "stable")
        revenue_est = signals.get("revenue", {}).get("revenue_estimate", "Not found")

        cb_funding = signals.get("crunchbase", {}).get("funding_mentions", [])
        pb_funding = signals.get("pitchbook", {}).get("funding_mentions", [])
        funding_str = " ".join(cb_funding + pb_funding).lower()
        has_series_a_plus = any(
            f in funding_str for f in ["series a", "series b", "series c", "series d", "series e", "series f"]
        )

        burn_rate = "moderate"
        runway = "unknown"

        if hiring_sig == "growing":
            burn_rate = "high"
            if revenue_est == "Not found":
                runway = "12-18 months (estimated)"
            else:
                runway = "18-24 months (estimated)"
        elif hiring_sig == "contracting":
            burn_rate = "low"
            runway = "unknown"
        else:
            burn_rate = "moderate"
            runway = "unknown"

        if has_series_a_plus and runway == "unknown":
            runway = "18-24 months (estimated)"

        return burn_rate, runway
