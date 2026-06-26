import asyncio
import json
import re
import time
from ...models.domain import StartupProfile, AgentResult, MarketData, AgentStatus
from ...llm.ollama_client import OllamaClient
from ...config.settings import Settings
from ...tools.financial.market_tools import (
    get_industry_market_size,
    get_market_growth_rate,
    get_market_trends,
    get_wikipedia_industry_overview,
)

class MarketResearchAgent:
    """Agent responsible for conducting market research, analyzing market size (TAM/SAM/SOM), and identifying trends."""

    def __init__(self, ollama_client: OllamaClient, tools: dict, settings: Settings):
        """Initialize the market research agent with clients, tools, and configurations."""
        self.ollama_client = ollama_client
        self.tools = tools
        self.settings = settings

    async def run(self, startup: StartupProfile) -> AgentResult:
        """Main entry: research market size, trends, TAM/SAM/SOM for startup's industry."""
        start_time = time.monotonic()
        raw_data = {}
        error_msg = None

        try:
            # Step 1: Gather raw research data
            raw_data = await self._gather_raw_data(startup.industry)

            # Step 2: Structure and analyze gathered data using LLM
            market_data = await self._analyze_with_llm(raw_data, startup)

            # Step 3: Track and aggregate all collected sources
            sources = list(market_data.sources or [])
            sources.extend(raw_data.get("size", {}).get("sources", []))
            sources.extend(raw_data.get("growth", {}).get("sources", []))
            unique_sources = sorted(list(set(sources)))
            market_data.sources = unique_sources

            # Step 4: Validate output
            valid = self._validate_output(market_data)
            status = AgentStatus.SUCCESS if valid else AgentStatus.FAILED
            if not valid:
                error_msg = "Validation failed: TAM is 0 or key trends are empty."

            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="market_research",
                status=status,
                data=market_data.model_dump() if hasattr(market_data, "model_dump") else market_data.dict(),
                error=error_msg,
                duration_ms=duration_ms,
                sources=unique_sources,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            
            # Aggregate whatever sources we can salvage
            fallback_sources = []
            if raw_data:
                fallback_sources.extend(raw_data.get("size", {}).get("sources", []))
                fallback_sources.extend(raw_data.get("growth", {}).get("sources", []))
            unique_fallback_sources = sorted(list(set(fallback_sources)))

            return AgentResult(
                agent_name="market_research",
                status=AgentStatus.FAILED,
                data=None,
                error=f"Execution error: {str(e)}",
                duration_ms=duration_ms,
                sources=unique_fallback_sources,
            )

    async def _gather_raw_data(self, industry: str) -> dict:
        """Parallel fetch: market size + growth rate + trends + wikipedia."""
        results = await asyncio.gather(
            get_industry_market_size(industry),
            get_market_growth_rate(industry),
            get_market_trends(industry),
            get_wikipedia_industry_overview(industry),
            return_exceptions=True,
        )

        size_res = results[0] if not isinstance(results[0], Exception) else {}
        growth_res = results[1] if not isinstance(results[1], Exception) else {}
        trends_res = results[2] if not isinstance(results[2], Exception) else []
        overview_res = results[3] if not isinstance(results[3], Exception) else ""

        return {
            "size": size_res,
            "growth": growth_res,
            "trends": trends_res,
            "overview": overview_res,
        }

    async def _analyze_with_llm(self, raw_data: dict, startup: StartupProfile) -> MarketData:
        """Send gathered data to Ollama for structured extraction into MarketData."""
        prompt = self._build_analysis_prompt(raw_data, startup)
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

            sources = list(data.get("sources", []))
            if not sources:
                sources.extend(raw_data.get("size", {}).get("sources", []))
                sources.extend(raw_data.get("growth", {}).get("sources", []))

            return MarketData(
                tam_usd=float(data.get("tam_usd") or 0.0),
                sam_usd=float(data.get("sam_usd") or 0.0),
                som_usd=float(data.get("som_usd") or 0.0),
                cagr_pct=float(data.get("cagr_pct") or 0.0),
                key_trends=list(data.get("key_trends") or []),
                sources=list(set(sources)),
            )

        except Exception:
            # Fallback estimation parsing if LLM output fails
            fallback_sources = []
            fallback_sources.extend(raw_data.get("size", {}).get("sources", []))
            fallback_sources.extend(raw_data.get("growth", {}).get("sources", []))

            # Attempt a basic regex extract from size estimate text
            tam_val = 0.0
            size_est = raw_data.get("size", {}).get("tam_estimate", "")
            match_tam = re.search(r'\$?([\d.]+)\s*(billion|million|trillion)?', size_est, re.IGNORECASE)
            if match_tam:
                try:
                    num = float(match_tam.group(1))
                    unit = match_tam.group(2).lower() if match_tam.group(2) else ""
                    if "billion" in unit:
                        tam_val = num * 1_000_000_000
                    elif "million" in unit:
                        tam_val = num * 1_000_000
                    elif "trillion" in unit:
                        tam_val = num * 1_000_000_000_000
                    else:
                        tam_val = num
                except Exception:
                    pass

            cagr_val = 0.0
            cagr_est = raw_data.get("growth", {}).get("cagr_estimate", "")
            match_cagr = re.search(r'([\d.]+)%', cagr_est)
            if match_cagr:
                try:
                    cagr_val = float(match_cagr.group(1))
                except Exception:
                    pass

            return MarketData(
                tam_usd=tam_val,
                sam_usd=0.0,
                som_usd=0.0,
                cagr_pct=cagr_val,
                key_trends=list(raw_data.get("trends") or []),
                sources=list(set(fallback_sources)),
            )

    def _build_analysis_prompt(self, raw_data: dict, startup: StartupProfile) -> str:
        """Build the Ollama prompt for market analysis."""
        from ...utils.prompt_loader import get_prompt_loader
        return get_prompt_loader().render(
            "market_analysis",
            company_name=startup.name,
            industry=startup.industry,
            raw_data=json.dumps(raw_data, indent=2)
        )

    def _validate_output(self, market_data: MarketData) -> bool:
        """Check MarketData has minimum required fields populated."""
        return market_data.tam_usd > 0.0 and len(market_data.key_trends) > 0
