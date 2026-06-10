import asyncio
import json
import logging
import time
from datetime import datetime
from ..models.domain import (
    StartupProfile,
    AgentResult,
    DiligenceReport,
    AgentStatus,
    MarketData,
    CompetitorLandscape,
    FinancialProfile,
    LegalProfile,
)
from ..models.orchestration import OrchestratorPlan
from ..config.settings import Settings

# Import all agent classes as requested in Final Check (1)
from ..agents.market_research.agent import MarketResearchAgent
from ..agents.competitor.agent import CompetitorAgent
from ..agents.financial.agent import FinancialAgent
from ..agents.legal.agent import LegalAgent
from ..agents.summarization.agent import SummarizationAgent

class DiligenceOrchestrator:
    """Central orchestrator coordinating specialist agents, planning execution flow, enforcing timeouts, and assembling the final diligence report."""

    def __init__(self, agents: dict, memory, settings: Settings):
        """Initialize orchestrator with domain agents, state memory store, and system settings."""
        self.agents = agents
        self.memory = memory
        self.settings = settings
        self.ollama_client = None
        for agent in agents.values():
            if hasattr(agent, "ollama_client"):
                self.ollama_client = agent.ollama_client
                break

    async def run(self, startup_name: str) -> DiligenceReport:
        """Full orchestration: profile → plan → execute → summarize → report."""
        logger = logging.getLogger("orchestrator")
        start_time = time.monotonic()
        logger.info(f"Starting orchestration pipeline for startup: {startup_name}")

        cache_key = f"report:{startup_name}"
        if self.memory:
            try:
                cached = await self.memory.get(cache_key)
                if cached:
                    logger.info("Found cached diligence report. Returning.")
                    return DiligenceReport(**json.loads(cached))
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        # Step 1: Build startup profile
        startup = await self._build_startup_profile(startup_name)

        # Step 2: Plan execution
        plan = await self._plan_execution(startup)

        # Step 3: Run Group 1 (parallel agents)
        group_1 = plan.parallel_groups[0]
        results = await self._execute_parallel_group(group_1, startup)

        # Step 4: Run Group 2 (summarization)
        summary_result = await self._run_summarization(startup, results)

        # Step 5: Assemble report
        report = await self._assemble_report(startup, results, summary_result)

        # Cache report for 24 hours
        if self.memory:
            try:
                await self.memory.set(
                    cache_key,
                    report.model_dump_json() if hasattr(report, "model_dump_json") else report.json(),
                    ex=86400
                )
            except Exception as e:
                logger.warning(f"Cache write error: {e}")

        total_elapsed = time.monotonic() - start_time
        logger.info(f"Pipeline completed. Total wall-clock time: {total_elapsed:.2f} seconds.")
        return report

    async def _build_startup_profile(self, startup_name: str) -> StartupProfile:
        """Gather basic company info to build StartupProfile before agents start."""
        cache_key = f"profile:{startup_name}"
        if self.memory:
            try:
                cached = await self.memory.get(cache_key)
                if cached:
                    return StartupProfile(**json.loads(cached))
            except Exception:
                pass

        from ..tools.search.web_search import search_company
        search_results = await search_company(startup_name)
        prompt = self._build_profile_prompt(startup_name, search_results)
        
        response = await self.ollama_client.generate(
            prompt=prompt,
            model=self.settings.OLLAMA_ORCHESTRATOR_MODEL,
            expect_json=True
        )
        
        if isinstance(response, str):
            data = json.loads(response)
        else:
            data = response
            
        profile = StartupProfile(
            name=data.get("name") or startup_name,
            website=data.get("website") or "unknown",
            founded_year=int(data.get("founded_year") or 2020),
            headquarters=data.get("headquarters") or "unknown",
            industry=data.get("industry") or "unknown",
            description=data.get("description") or "unknown",
            founders=list(data.get("founders") or [])
        )
        
        if self.memory:
            try:
                await self.memory.set(cache_key, profile.model_dump_json() if hasattr(profile, "model_dump_json") else profile.json())
            except Exception:
                pass
                
        return profile

    async def _plan_execution(self, startup: StartupProfile) -> OrchestratorPlan:
        """Decide parallel groups and sequential deps. Market+Competitor+Financial+Legal in parallel, Summary last."""
        return OrchestratorPlan(
            startup_name=startup.name,
            parallel_groups=[
                ["market_research", "competitor", "financial", "legal"],
                ["summarization"]
            ],
            sequential_deps={
                "summarization": ["market_research", "competitor", "financial", "legal"]
            },
            estimated_duration_ms=60000
        )

    async def _execute_parallel_group(
        self, group: list[str], startup: StartupProfile
    ) -> dict[str, AgentResult]:
        """Run a group of agents concurrently with timeout per agent."""
        tasks = {name: self._execute_agent(name, startup) for name in group}
        results = await asyncio.gather(*tasks.values(), return_exceptions=False)
        return {name: result for name, result in zip(tasks.keys(), results)}

    async def _execute_agent(self, agent_name: str, startup: StartupProfile) -> AgentResult:
        """Run one agent with timeout enforcement and error isolation."""
        logger = logging.getLogger("orchestrator")
        logger.info(f"Starting execution of agent: {agent_name}")
        
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Agent '{agent_name}' not found in registry.")
            return AgentResult(
                agent_name=agent_name,
                status=AgentStatus.FAILED,
                data=None,
                error=f"Agent '{agent_name}' not found.",
                duration_ms=0,
                sources=[]
            )
            
        start_time = time.monotonic()
        try:
            result = await asyncio.wait_for(
                agent.run(startup),
                timeout=float(self.settings.AGENT_TIMEOUT_SECONDS)
            )
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(f"Agent '{agent_name}' completed with status: {result.status}")
            return result
        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning(f"Agent '{agent_name}' execution timed out after {self.settings.AGENT_TIMEOUT_SECONDS}s.")
            return AgentResult(
                agent_name=agent_name,
                status=AgentStatus.TIMEOUT,
                data=None,
                error="Execution timed out.",
                duration_ms=elapsed_ms,
                sources=[]
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Agent '{agent_name}' failed with error: {str(e)}")
            return AgentResult(
                agent_name=agent_name,
                status=AgentStatus.FAILED,
                data=None,
                error=f"Execution error: {str(e)}",
                duration_ms=elapsed_ms,
                sources=[]
            )

    async def _run_summarization(self, startup: StartupProfile, results: dict) -> AgentResult:
        """Run summarization agent with all prior results."""
        logger = logging.getLogger("orchestrator")
        logger.info("Starting execution of summarization agent.")
        
        agent = self.agents.get("summarization")
        if not agent:
            logger.error("Summarization agent not found in registry.")
            return AgentResult(
                agent_name="summarization",
                status=AgentStatus.FAILED,
                data=None,
                error="Summarization agent not found.",
                duration_ms=0,
                sources=[]
            )
            
        start_time = time.monotonic()
        try:
            result = await asyncio.wait_for(
                agent.run(startup, results),
                timeout=float(self.settings.AGENT_TIMEOUT_SECONDS)
            )
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(f"Summarization agent completed with status: {result.status}")
            return result
        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning(f"Summarization agent execution timed out after {self.settings.AGENT_TIMEOUT_SECONDS}s.")
            return AgentResult(
                agent_name="summarization",
                status=AgentStatus.TIMEOUT,
                data=None,
                error="Execution timed out.",
                duration_ms=elapsed_ms,
                sources=[]
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Summarization agent failed with error: {str(e)}")
            return AgentResult(
                agent_name="summarization",
                status=AgentStatus.FAILED,
                data=None,
                error=f"Execution error: {str(e)}",
                duration_ms=elapsed_ms,
                sources=[]
            )

    async def _assemble_report(
        self, startup: StartupProfile, all_results: dict, summary: AgentResult
    ) -> DiligenceReport:
        """Assemble final DiligenceReport from all specialist findings and executive summary."""
        market = None
        market_res = all_results.get("market_research")
        if market_res and market_res.status in (AgentStatus.SUCCESS, "SUCCESS") and market_res.data:
            try:
                market = MarketData(**market_res.data)
            except Exception:
                pass

        competitors = None
        competitor_res = all_results.get("competitor")
        if competitor_res and competitor_res.status in (AgentStatus.SUCCESS, "SUCCESS") and competitor_res.data:
            try:
                competitors = CompetitorLandscape(**competitor_res.data)
            except Exception:
                pass

        financials = None
        financial_res = all_results.get("financial")
        if financial_res and financial_res.status in (AgentStatus.SUCCESS, "SUCCESS") and financial_res.data:
            try:
                financials = FinancialProfile(**financial_res.data)
            except Exception:
                pass

        legal = None
        legal_res = all_results.get("legal")
        if legal_res and legal_res.status in (AgentStatus.SUCCESS, "SUCCESS") and legal_res.data:
            try:
                legal = LegalProfile(**legal_res.data)
            except Exception:
                pass

        summary_data = summary.data if summary and summary.data else {}
        summary_str = summary_data.get("summary") or "Due diligence summary is unavailable."
        investment_score = summary_data.get("investment_score") or 0.0
        risk_flags = summary_data.get("risk_flags") or []

        agent_results = list(all_results.values())
        if summary:
            agent_results.append(summary)

        return DiligenceReport(
            startup_name=startup.name,
            generated_at=datetime.utcnow(),
            market=market,
            competitors=competitors,
            financials=financials,
            legal=legal,
            summary=summary_str,
            investment_score=investment_score,
            risk_flags=risk_flags,
            agent_results=agent_results,
        )

    def _build_profile_prompt(self, company_name: str, search_results: list[dict]) -> str:
        """Build the prompt for startup profile extraction."""
        schema = {
            "name": "string (Startup name)",
            "website": "string (Official website URL)",
            "founded_year": "integer",
            "headquarters": "string (City, State/Country)",
            "industry": "string (Industry vertical, e.g. Enterprise AI)",
            "description": "string (One sentence description)",
            "founders": ["string (Founder name 1)", "string (Founder name 2)"]
        }
        return (
            f"You are a VC diligence assistant. Extract structural profile information for the company '{company_name}' "
            f"from these web search results:\n\n"
            f"{json.dumps(search_results, indent=2)}\n\n"
            f"You MUST return a JSON object adhering to this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"If a field cannot be found, estimate or use 'unknown' for strings and 2020 for founded_year.\n"
            f"Do not include any chat prefix or suffix. Return ONLY the JSON object."
        )
