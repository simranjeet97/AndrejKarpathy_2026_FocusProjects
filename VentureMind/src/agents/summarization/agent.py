import json
import time
from datetime import datetime, timezone
from ...models.domain import (
    StartupProfile,
    AgentResult,
    DiligenceReport,
    AgentStatus,
    MarketData,
    CompetitorLandscape,
    FinancialProfile,
    LegalProfile
)
from ...llm.ollama_client import OllamaClient
from ...config.settings import Settings

class SummarizationAgent:
    """Agent responsible for combining all domain specialist agent findings and synthesising the final due diligence report."""

    def __init__(self, ollama_client: OllamaClient, settings: Settings):
        """Initialize the summarization agent with Ollama clients and settings."""
        self.ollama_client = ollama_client
        self.settings = settings

    async def run(self, startup: StartupProfile, agent_results: dict[str, AgentResult]) -> AgentResult:
        """Synthesize all agent outputs into final DiligenceReport summary details."""
        start_time = time.monotonic()
        try:
            # Check successful agents count
            success_count = sum(1 for r in agent_results.values() if r.status in ("SUCCESS", AgentStatus.SUCCESS))

            # 1. Assess data completeness
            completeness = self._assess_data_completeness(agent_results)

            # 2. Synthesize agent reports into a summary
            synthesis = await self._synthesize_report(startup, agent_results)

            # 3. Calculate final investment score
            score = await self._score_investment(startup, agent_results, synthesis)

            # 4. Consolidate and extract risk flags
            risk_flags = self._extract_risk_flags(agent_results)

            summary_str = synthesis.get("summary") or "Due diligence summary is unavailable."

            # Collect unique sources
            results_list = list(agent_results.values())
            sources = []
            for r in results_list:
                if r.sources:
                    sources.extend(r.sources)
            unique_sources = sorted(list(set(sources)))

            # Synthesized summary fields dictionary
            data = {
                "summary": summary_str,
                "investment_score": score,
                "risk_flags": risk_flags
            }

            # Determine summarization agent status
            status = AgentStatus.SUCCESS if success_count > 0 else AgentStatus.FAILED
            error_msg = None if success_count > 0 else "All specialist agents failed. Diligence report generated with empty findings."

            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="summarization",
                status=status,
                data=data,
                error=error_msg,
                duration_ms=duration_ms,
                sources=unique_sources,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="summarization",
                status=AgentStatus.FAILED,
                data=None,
                error=f"Execution error: {str(e)}",
                duration_ms=duration_ms,
                sources=[],
            )

    async def _synthesize_report(self, startup: StartupProfile, results: dict) -> dict:
        """Main LLM call: combine all findings into coherent narrative."""
        prompt = self._build_synthesis_prompt(startup, results)
        try:
            response = await self.ollama_client.generate(
                prompt=prompt,
                model=self.settings.OLLAMA_SUMMARY_MODEL,
                expect_json=True,
            )
            if isinstance(response, str):
                return json.loads(response)
            return response
        except Exception as e:
            return {
                "summary": f"Synthesis failed due to LLM error: {str(e)}",
                "key_strengths": ["Diligence pipelines run"],
                "key_risks": ["Executive synthesis model execution failed"],
            }

    async def _score_investment(self, startup: StartupProfile, results: dict, synthesis: dict) -> float:
        """LLM + heuristic: 0-10 investment attractiveness score."""
        completeness = self._assess_data_completeness(results)
        prompt = self._build_scoring_prompt(startup, synthesis, completeness)
        try:
            response = await self.ollama_client.generate(
                prompt=prompt,
                model=self.settings.OLLAMA_SUMMARY_MODEL,
                expect_json=True,
            )
            if isinstance(response, str):
                data = json.loads(response)
            else:
                data = response

            raw_score = float(data.get("score") or 5.0)
            # Adjust score dynamically based on data completeness
            score = raw_score * completeness
            return min(10.0, max(0.0, score))
        except Exception:
            return min(10.0, max(0.0, 5.0 * completeness))

    def _extract_risk_flags(self, results: dict) -> list[str]:
        """Consolidate risk flags from all agents into prioritized list."""
        risk_flags = []

        # 1. Market Research agent risks
        market_res = results.get("market_research")
        if market_res and market_res.status in ("SUCCESS", AgentStatus.SUCCESS) and market_res.data:
            cagr = market_res.data.get("cagr_pct", 0.0)
            if cagr < 5.0:
                risk_flags.append(f"Slow Industry Growth: Market CAGR is low ({cagr:.1f}%)")

        # 2. Competitor agent risks
        competitor_res = results.get("competitor")
        if competitor_res and competitor_res.status in ("SUCCESS", AgentStatus.SUCCESS) and competitor_res.data:
            diff_score = competitor_res.data.get("differentiation_score", 1.0)
            if diff_score < 0.3:
                risk_flags.append(f"Low Competitive Differentiation: Differentiation score is low ({diff_score:.2f})")

        # 3. Financial agent risks
        financial_res = results.get("financial")
        if financial_res and financial_res.status in ("SUCCESS", AgentStatus.SUCCESS) and financial_res.data:
            signals = financial_res.data.get("signals", [])
            for sig in signals:
                conf = sig.get("confidence", 1.0)
                if conf < 0.5:
                    risk_flags.append(f"Unreliable Financial Data: Low confidence signal for '{sig.get('metric_name')}' ({sig.get('value')})")

        # 4. Legal agent risks
        legal_res = results.get("legal")
        if legal_res and legal_res.status in ("SUCCESS", AgentStatus.SUCCESS) and legal_res.data:
            flags = legal_res.data.get("flags", [])
            for flag in flags:
                sev = flag.get("severity", "NONE").upper()
                if sev in ("HIGH", "MEDIUM"):
                    risk_flags.append(f"Legal Warning ({sev}): {flag.get('description')} (Source: {flag.get('source')})")

        # Deduplicate
        seen = set()
        deduped_risks = []
        for r in risk_flags:
            if r not in seen:
                seen.add(r)
                deduped_risks.append(r)
        return deduped_risks

    def _build_synthesis_prompt(self, startup: StartupProfile, results: dict) -> str:
        """Build the prompt for synthesis generation."""
        sections = []
        for agent_name, result in results.items():
            if result.status in ("SUCCESS", AgentStatus.SUCCESS):
                data_str = json.dumps(result.data, indent=2)
                sections.append(f"### Specialist Agent: {agent_name}\nData findings:\n{data_str}")

        sections_str = "\n\n".join(sections)

        from ...utils.prompt_loader import get_prompt_loader
        return get_prompt_loader().render(
            "synthesis",
            company_name=startup.name,
            industry=startup.industry,
            description=startup.description,
            sections_str=sections_str
        )

    def _build_scoring_prompt(self, startup: StartupProfile, synthesis: dict, completeness: float) -> str:
        """Build the prompt for scoring calculation."""
        from ...utils.prompt_loader import get_prompt_loader
        return get_prompt_loader().render(
            "scoring",
            company_name=startup.name,
            industry=startup.industry,
            synthesis_data=json.dumps(synthesis, indent=2),
            completeness=completeness
        )

    def _assess_data_completeness(self, results: dict) -> float:
        """What fraction of agents succeeded? Affects confidence in score."""
        if not results:
            return 0.0
        success_count = sum(1 for r in results.values() if r.status in ("SUCCESS", AgentStatus.SUCCESS))
        return float(success_count) / len(results)
