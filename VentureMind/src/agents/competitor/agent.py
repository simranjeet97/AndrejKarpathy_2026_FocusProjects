import asyncio
import json
import re
import time
from ...models.domain import StartupProfile, AgentResult, Competitor, CompetitorLandscape, AgentStatus
from ...llm.ollama_client import OllamaClient
from ...config.settings import Settings
from ...tools.search.competitor_tools import find_competitors, get_company_info, get_funding_info

class CompetitorAgent:
    """Agent responsible for identifying competitors, profiling their funding and scale, and assessing positioning."""

    def __init__(self, ollama_client: OllamaClient, tools: dict, settings: Settings):
        """Initialize the competitor analysis agent with clients, tools, and configurations."""
        self.ollama_client = ollama_client
        self.tools = tools
        self.settings = settings

    async def run(self, startup: StartupProfile) -> AgentResult:
        """Identify and profile top competitors, assess competitive positioning."""
        start_time = time.monotonic()
        try:
            # Step 1: Discover competitor names and websites
            raw_competitors = await self._discover_competitors(startup)

            # Step 2: Profile each competitor in parallel
            competitors = await self._profile_competitors(raw_competitors)

            # Step 3: Analyze positioning and moat using LLM
            landscape = await self._analyze_positioning(startup, competitors)

            # Step 4: Aggregate sources (competitor websites)
            sources = []
            for c in competitors:
                if c.website and c.website.startswith("http"):
                    sources.append(c.website)
            unique_sources = sorted(list(set(sources)))

            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="competitor",
                status=AgentStatus.SUCCESS,
                data=landscape.model_dump() if hasattr(landscape, "model_dump") else landscape.dict(),
                error=None,
                duration_ms=duration_ms,
                sources=unique_sources,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AgentResult(
                agent_name="competitor",
                status=AgentStatus.FAILED,
                data=None,
                error=f"Execution error: {str(e)}",
                duration_ms=duration_ms,
                sources=[],
            )

    async def _discover_competitors(self, startup: StartupProfile) -> list[dict]:
        """Find competitor names and basic info."""
        raw_competitors = await find_competitors(startup.name, startup.industry)
        return raw_competitors[:8]

    async def _profile_competitors(self, competitors_raw: list[dict]) -> list[Competitor]:
        """Enrich each competitor with detailed data in parallel using a Semaphore of 4."""
        sem = asyncio.Semaphore(4)
        tasks = [self._profile_competitor_single(raw, sem) for raw in competitors_raw]
        return list(await asyncio.gather(*tasks))

    async def _profile_competitor_single(self, raw: dict, sem: asyncio.Semaphore) -> Competitor:
        """Helper to profile a single competitor with semaphore gating."""
        name = raw.get("name", "")
        async with sem:
            info_task = get_company_info(name)
            funding_task = get_funding_info(name)
            info, funding = await asyncio.gather(info_task, funding_task)

            website = info.get("website") or raw.get("website") or ""
            founded_year = info.get("founded_year") or raw.get("founded_year") or 2020
            funding_usd = self._parse_funding_to_float(funding.get("total_funding_estimate"))

            return Competitor(
                name=name,
                website=website,
                founded_year=founded_year,
                funding_usd=funding_usd,
                market_share_pct=None,
                strengths=[],
                weaknesses=[],
            )

    async def _analyze_positioning(
        self, startup: StartupProfile, competitors: list[Competitor]
    ) -> CompetitorLandscape:
        """LLM analysis: where does this startup sit in the landscape?"""
        prompt = self._build_positioning_prompt(startup, competitors)
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

            llm_diff_score = float(data.get("differentiation_score") or 0.5)
            final_diff_score = self._score_differentiation(startup, competitors, llm_diff_score)

            return CompetitorLandscape(
                startup_name=startup.name,
                competitors=competitors,
                positioning_summary=data.get("positioning_summary") or "Competitive landscape analyzed.",
                differentiation_score=final_diff_score,
            )
        except Exception:
            final_diff_score = self._score_differentiation(startup, competitors, 0.5)
            return CompetitorLandscape(
                startup_name=startup.name,
                competitors=competitors,
                positioning_summary="Competitive landscape profiling completed with fallback metrics.",
                differentiation_score=final_diff_score,
            )

    def _build_positioning_prompt(
        self, startup: StartupProfile, competitors: list[Competitor]
    ) -> str:
        """Build the Ollama prompt for positioning analysis."""
        competitors_list = []
        for c in competitors:
            c_dict = {
                "name": c.name,
                "website": c.website,
                "founded_year": c.founded_year,
                "funding_usd": c.funding_usd,
                "strengths": c.strengths,
                "weaknesses": c.weaknesses,
            }
            competitors_list.append(c_dict)

        schema = {
            "positioning_summary": "string (exactly 2 sentences summarizing the startup's positioning and competitive landscape)",
            "differentiation_score": "float (0.0 to 1.0 representing how unique the startup's offering is)",
            "key_advantages": "list of strings (reasons for the differentiation)"
        }

        return (
            f"You are a VC analyst conducting due diligence on the startup '{startup.name}'.\n"
            f"Industry: {startup.industry}\n"
            f"Description: {startup.description}\n\n"
            f"Here are the identified competitors and their profiles:\n"
            f"{json.dumps(competitors_list, indent=2)}\n\n"
            f"Analyze the startup's competitive positioning relative to these competitors. "
            f"Identify the startup's main differentiation, assess their competitive moat, and write "
            f"a 2-sentence positioning summary.\n\n"
            f"You MUST return a JSON object adhering to this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"Do not include any chat prefix or suffix. Return ONLY the JSON object."
        )

    def _score_differentiation(
        self, startup: StartupProfile, competitors: list[Competitor], llm_score: float = 0.5
    ) -> float:
        """Heuristic 0-1 score: how differentiated is this startup?"""
        heuristic_score = 0.5
        if len(competitors) < 3:
            heuristic_score = 0.8

        if competitors:
            recent_count = sum(
                1 for c in competitors if c.founded_year and startup.founded_year > c.founded_year
            )
            if recent_count > len(competitors) / 2:
                heuristic_score += 0.1

        final_score = (heuristic_score + llm_score) / 2.0
        return max(0.0, min(1.0, final_score))

    def _parse_funding_to_float(self, funding_str: str) -> float | None:
        """Parse estimated funding string into float USD representation."""
        if not funding_str or "Not found" in funding_str:
            return None
        match = re.search(r'\$?([\d.]+)\s*(million|billion|M|B)?', funding_str, re.IGNORECASE)
        if not match:
            return None
        try:
            val = float(match.group(1))
            unit = match.group(2).lower() if match.group(2) else ""
            if "billion" in unit or "b" in unit:
                return val * 1_000_000_000
            elif "million" in unit or "m" in unit:
                return val * 1_000_000
            return val
        except Exception:
            return None
