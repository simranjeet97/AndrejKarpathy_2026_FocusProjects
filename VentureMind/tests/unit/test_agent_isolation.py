import ast
import asyncio
import inspect
import time
import pytest
from src.models.domain import AgentResult, AgentStatus, StartupProfile, MarketData, CompetitorLandscape, FinancialProfile, LegalProfile
from src.agents.market_research.agent import MarketResearchAgent
from src.agents.competitor.agent import CompetitorAgent
from src.agents.financial.agent import FinancialAgent
from src.agents.legal.agent import LegalAgent
from src.agents.summarization.agent import SummarizationAgent
from src.orchestrator.orchestrator import DiligenceOrchestrator


def test_market_agent_does_not_import_competitor_agent():
    """Verify that the market research specialist agent is isolated from competitor modules."""
    # 1. Inspect source of the market research agent module
    from src.agents.market_research import agent as market_agent_mod
    source = inspect.getsource(market_agent_mod)
    
    # 2. Parse source into AST to inspect import nodes
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names]
            
            # Assert "competitor" is not part of module name or targets
            if module and "competitor" in module.lower():
                raise AssertionError(f"Market agent imports competitor module: '{module}'")
            for name in names:
                if "competitor" in name.lower():
                    raise AssertionError(f"Market agent imports competitor symbol/submodule: '{name}'")


@pytest.mark.asyncio
async def test_agents_communicate_only_through_result_types(mocker):
    """Verify that every specialist agent's run method strictly returns an AgentResult object, not a raw dictionary."""
    mock_client = mocker.MagicMock()
    mock_settings = mocker.MagicMock()
    mock_settings.OLLAMA_ANALYST_MODEL = "test"
    mock_settings.OLLAMA_SUMMARY_MODEL = "test"
    mock_settings.AGENT_TIMEOUT_SECONDS = 10

    startup = StartupProfile(
        name="TestStartup",
        website="https://test.com",
        founded_year=2021,
        headquarters="San Francisco, CA",
        industry="Enterprise Software",
        description="A test startup",
        founders=["Founder A"]
    )

    # 1. Market Research Specialist Agent
    market_agent = MarketResearchAgent(mock_client, {}, mock_settings)
    async def mock_gather_raw_data(*args, **kwargs):
        return {}
    async def mock_analyze_with_llm(*args, **kwargs):
        return MarketData(
            tam_usd=1000000.0, sam_usd=500000.0, som_usd=100000.0,
            cagr_pct=5.0, key_trends=["trend"], sources=[]
        )
    market_agent._gather_raw_data = mock_gather_raw_data
    market_agent._analyze_with_llm = mock_analyze_with_llm

    res = await market_agent.run(startup)
    assert isinstance(res, AgentResult)
    assert not isinstance(res, dict)

    # 2. Competitor Analysis Specialist Agent
    competitor_agent = CompetitorAgent(mock_client, {}, mock_settings)
    async def mock_discover_competitors(*args, **kwargs):
        return []
    async def mock_profile_competitors(*args, **kwargs):
        return []
    async def mock_analyze_positioning(*args, **kwargs):
        return CompetitorLandscape(
            startup_name="TestStartup", competitors=[],
            positioning_summary="summary", differentiation_score=0.8
        )
    competitor_agent._discover_competitors = mock_discover_competitors
    competitor_agent._profile_competitors = mock_profile_competitors
    competitor_agent._analyze_positioning = mock_analyze_positioning

    res = await competitor_agent.run(startup)
    assert isinstance(res, AgentResult)
    assert not isinstance(res, dict)

    # 3. Financial Analysis Specialist Agent
    financial_agent = FinancialAgent(mock_client, {}, mock_settings)
    async def mock_gather_financial_signals(*args, **kwargs):
        return {}
    async def mock_analyze_financial_health(*args, **kwargs):
        return FinancialProfile(
            startup_name="TestStartup", signals=[], funding_rounds=[],
            burn_rate_estimate="low", runway_estimate="18 months"
        )
    financial_agent._gather_financial_signals = mock_gather_financial_signals
    financial_agent._analyze_financial_health = mock_analyze_financial_health

    res = await financial_agent.run(startup)
    assert isinstance(res, AgentResult)
    assert not isinstance(res, dict)

    # 4. Legal Analysis Specialist Agent
    legal_agent = LegalAgent(mock_client, {}, mock_settings)
    async def mock_gather_legal_data(*args, **kwargs):
        return {}
    async def mock_classify_legal_flags(*args, **kwargs):
        return []
    async def mock_build_legal_profile(*args, **kwargs):
        return LegalProfile(
            startup_name="TestStartup", incorporation_status="Incorporated",
            flags=[], patent_count=0, trademark_count=0
        )
    legal_agent._gather_legal_data = mock_gather_legal_data
    legal_agent._classify_legal_flags = mock_classify_legal_flags
    legal_agent._build_legal_profile = mock_build_legal_profile

    res = await legal_agent.run(startup)
    assert isinstance(res, AgentResult)
    assert not isinstance(res, dict)

    # 5. Synthesizer & Investment Scorer Agent (Summarization)
    summarization_agent = SummarizationAgent(mock_client, mock_settings)
    async def mock_synthesize_report(*args, **kwargs):
        return {"summary": "summary", "key_strengths": [], "key_risks": []}
    async def mock_score_investment(*args, **kwargs):
        return 8.0
    def mock_extract_risk_flags(*args, **kwargs):
        return []
    summarization_agent._synthesize_report = mock_synthesize_report
    summarization_agent._score_investment = mock_score_investment
    summarization_agent._extract_risk_flags = mock_extract_risk_flags

    res = await summarization_agent.run(startup, {})
    assert isinstance(res, AgentResult)
    assert not isinstance(res, dict)


@pytest.mark.asyncio
async def test_orchestrator_handles_agent_timeout(mocker):
    """Verify that if a specialist agent exceeds the configuration timeout limit, the orchestrator logs a TIMEOUT and continues."""
    mock_settings = mocker.MagicMock()
    mock_settings.AGENT_TIMEOUT_SECONDS = 1
    mock_settings.OLLAMA_ORCHESTRATOR_MODEL = "test"

    startup = StartupProfile(
        name="TestStartup", website="test.com", founded_year=2020,
        headquarters="SF", industry="Tech", description="Test", founders=[]
    )

    # Mock market research to sleep past timeout
    mock_market = mocker.MagicMock()
    async def slow_run(startup):
        await asyncio.sleep(200)
        return AgentResult(agent_name="market_research", status=AgentStatus.SUCCESS, duration_ms=0, sources=[])
    mock_market.run = slow_run

    # Mock other agents to return successfully and fast
    mock_competitor = mocker.MagicMock()
    async def fast_comp(startup):
        return AgentResult(agent_name="competitor", status=AgentStatus.SUCCESS, duration_ms=10, sources=[])
    mock_competitor.run = fast_comp

    mock_financial = mocker.MagicMock()
    async def fast_fin(startup):
        return AgentResult(agent_name="financial", status=AgentStatus.SUCCESS, duration_ms=10, sources=[])
    mock_financial.run = fast_fin

    mock_legal = mocker.MagicMock()
    async def fast_leg(startup):
        return AgentResult(agent_name="legal", status=AgentStatus.SUCCESS, duration_ms=10, sources=[])
    mock_legal.run = fast_leg

    mock_summarization = mocker.MagicMock()
    async def fast_sum(startup, results):
        return AgentResult(
            agent_name="summarization",
            status=AgentStatus.SUCCESS,
            data={"summary": "Success summary", "investment_score": 8.0, "risk_flags": []},
            duration_ms=10,
            sources=[]
        )
    mock_summarization.run = fast_sum

    agents = {
        "market_research": mock_market,
        "competitor": mock_competitor,
        "financial": mock_financial,
        "legal": mock_legal,
        "summarization": mock_summarization,
    }

    orchestrator = DiligenceOrchestrator(agents, None, mock_settings)
    mocker.patch.object(orchestrator, "_build_startup_profile", return_value=startup)

    report = await orchestrator.run("TestStartup")

    market_res = next(r for r in report.agent_results if r.agent_name == "market_research")
    competitor_res = next(r for r in report.agent_results if r.agent_name == "competitor")
    financial_res = next(r for r in report.agent_results if r.agent_name == "financial")
    legal_res = next(r for r in report.agent_results if r.agent_name == "legal")

    assert market_res.status == AgentStatus.TIMEOUT
    assert competitor_res.status == AgentStatus.SUCCESS
    assert financial_res.status == AgentStatus.SUCCESS
    assert legal_res.status == AgentStatus.SUCCESS


@pytest.mark.asyncio
async def test_orchestrator_handles_agent_exception(mocker):
    """Verify that when a specialist agent raises a runtime exception, the orchestrator reports FAILED for that agent but completes the report."""
    mock_settings = mocker.MagicMock()
    mock_settings.AGENT_TIMEOUT_SECONDS = 10
    mock_settings.OLLAMA_ORCHESTRATOR_MODEL = "test"

    startup = StartupProfile(
        name="TestStartup", website="test.com", founded_year=2020,
        headquarters="SF", industry="Tech", description="Test", founders=[]
    )

    # Mock competitor agent to raise error
    mock_competitor = mocker.MagicMock()
    async def error_run(startup):
        raise RuntimeError("Competitor agent crashed!")
    mock_competitor.run = error_run

    # Mock other agents to return successfully
    mock_market = mocker.MagicMock()
    async def fast_market(startup):
        return AgentResult(agent_name="market_research", status=AgentStatus.SUCCESS, duration_ms=10, sources=[])
    mock_market.run = fast_market

    mock_financial = mocker.MagicMock()
    async def fast_fin(startup):
        return AgentResult(agent_name="financial", status=AgentStatus.SUCCESS, duration_ms=10, sources=[])
    mock_financial.run = fast_fin

    mock_legal = mocker.MagicMock()
    async def fast_leg(startup):
        return AgentResult(agent_name="legal", status=AgentStatus.SUCCESS, duration_ms=10, sources=[])
    mock_legal.run = fast_leg

    mock_summarization = mocker.MagicMock()
    async def fast_sum(startup, results):
        return AgentResult(
            agent_name="summarization",
            status=AgentStatus.SUCCESS,
            data={"summary": "Success summary", "investment_score": 8.0, "risk_flags": []},
            duration_ms=10,
            sources=[]
        )
    mock_summarization.run = fast_sum

    agents = {
        "market_research": mock_market,
        "competitor": mock_competitor,
        "financial": mock_financial,
        "legal": mock_legal,
        "summarization": mock_summarization,
    }

    orchestrator = DiligenceOrchestrator(agents, None, mock_settings)
    mocker.patch.object(orchestrator, "_build_startup_profile", return_value=startup)

    report = await orchestrator.run("TestStartup")

    market_res = next(r for r in report.agent_results if r.agent_name == "market_research")
    competitor_res = next(r for r in report.agent_results if r.agent_name == "competitor")

    assert competitor_res.status == AgentStatus.FAILED
    assert competitor_res.error is not None
    assert "crashed" in competitor_res.error
    assert market_res.status == AgentStatus.SUCCESS
    assert report.startup_name == "TestStartup"


@pytest.mark.asyncio
async def test_parallel_execution_is_actually_parallel(mocker):
    """Verify that parallel specialist agents run concurrently, completing in less than the sum of their individual sleep durations."""
    mock_settings = mocker.MagicMock()
    mock_settings.AGENT_TIMEOUT_SECONDS = 10
    mock_settings.OLLAMA_ORCHESTRATOR_MODEL = "test"

    startup = StartupProfile(
        name="TestStartup", website="test.com", founded_year=2020,
        headquarters="SF", industry="Tech", description="Test", founders=[]
    )

    # Mock all 4 specialist agents to sleep for 1 second each
    async def slow_mock_run(startup):
        await asyncio.sleep(1.0)
        return AgentResult(agent_name="dummy", status=AgentStatus.SUCCESS, duration_ms=1000, sources=[])

    mock_market = mocker.MagicMock()
    mock_market.run = slow_mock_run

    mock_competitor = mocker.MagicMock()
    mock_competitor.run = slow_mock_run

    mock_financial = mocker.MagicMock()
    mock_financial.run = slow_mock_run

    mock_legal = mocker.MagicMock()
    mock_legal.run = slow_mock_run

    agents = {
        "market_research": mock_market,
        "competitor": mock_competitor,
        "financial": mock_financial,
        "legal": mock_legal,
    }

    orchestrator = DiligenceOrchestrator(agents, None, mock_settings)

    # Measure time around executing parallel group
    start_time = time.monotonic()
    await orchestrator._execute_parallel_group(
        ["market_research", "competitor", "financial", "legal"],
        startup
    )
    elapsed = time.monotonic() - start_time

    # Since all 4 agents sleep 1s, sequential execution would take 4s.
    # Parallel execution must complete in slightly over 1s (definitely < 2s).
    assert elapsed < 2.0
