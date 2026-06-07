import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from src.agent.queryforge_agent import QueryForgeAgent
from src.agent.tool_registry import ToolRegistry
from src.models import ChurnSegment, IndustryBenchmark, ChartOutput

@pytest.mark.asyncio
async def test_churn_analysis_query(monkeypatch):
    """E2E test with mocked tool implementations and LLM responses."""
    # 1. Setup mock tools results
    mock_segments = [
        ChurnSegment(segment_name="Enterprise Plan", churn_rate=0.06, customer_count=100, period="2026-06"),
        ChurnSegment(segment_name="Pro Plan", churn_rate=0.03, customer_count=500, period="2026-06"),
        ChurnSegment(segment_name="Basic Plan", churn_rate=0.01, customer_count=1000, period="2026-06")
    ]
    
    mock_benchmarks = [
        IndustryBenchmark(metric_name="churn", value=0.035, source="Gartner 2025", retrieved_at=datetime.utcnow()),
        IndustryBenchmark(metric_name="churn", value=0.04, source="SaaS Index 2026", retrieved_at=datetime.utcnow())
    ]
    
    mock_chart_path = "/Users/simranjeetsingh/Downloads/AI_Projects/AndrejKarpathy_2026_FocusProjects/queryforge/data/charts/comparison_churn_test.png"
    mock_chart_output = ChartOutput(
        chart_type="comparison_bar",
        filepath=mock_chart_path,
        title="Internal vs Benchmark: Churn",
        data_summary="Comparison chart"
    )

    # 2. Setup ToolRegistry and Agent
    settings = MagicMock()
    settings.MAX_PDF_PAGES = 10
    settings.CHARTS_OUTPUT_DIR = "/tmp"
    settings.MAX_TOOL_RETRIES = 1
    
    db_pool = MagicMock()
    mock_ollama = MagicMock()
    
    from src.tools.database.churn_tools import get_top_churned_segments
    from src.tools.web.search_tool import search_industry_benchmarks
    from unittest.mock import create_autospec
    import asyncio

    # Patch tool functions directly so ToolRegistry wraps our mocks
    mock_get_top = create_autospec(get_top_churned_segments)
    async def mock_get_top_impl(*args, **kwargs):
        await asyncio.sleep(0.002)
        return mock_segments
    mock_get_top.side_effect = mock_get_top_impl
    mock_get_top.__doc__ = get_top_churned_segments.__doc__

    mock_search_bench = create_autospec(search_industry_benchmarks)
    mock_search_bench.return_value = mock_benchmarks
    mock_search_bench.__doc__ = search_industry_benchmarks.__doc__
    
    monkeypatch.setattr("src.agent.tool_registry.get_top_churned_segments", mock_get_top)
    monkeypatch.setattr("src.agent.tool_registry.search_industry_benchmarks", mock_search_bench)
    
    registry = ToolRegistry(settings, db_pool, mock_ollama)
    # Mock chart tool method on registry
    mock_chart_func = MagicMock(return_value=mock_chart_output)
    mock_chart_func.__name__ = "generate_comparison_chart"
    registry.chart_tool.generate_comparison_chart = mock_chart_func
    registry.register_all()
    
    # Mock LLM calls:
    # 1. Planning response
    planning_response = {
        "steps": [
            {"tool": "get_top_churned_segments", "reason": "Fetch internal churn rates", "depends_on": []},
            {"tool": "search_industry_benchmarks", "reason": "Fetch industry benchmarks", "depends_on": []},
            {"tool": "generate_comparison_chart", "reason": "Compare internal with benchmarks", "depends_on": [0, 1]}
        ]
    }
    
    # 2-4. Argument generation responses
    arg_responses = [
        {"n": 5, "period_months": 3},
        {"metric": "churn", "industry": "saas"},
        {"metric": "churn"}
    ]
    
    # 5. Synthesis response
    synthesis_response = {
        "answer": "Our Enterprise Plan has the highest churn at 6%, which is higher than the industry average of 3.75%. See comparison chart at [comparison_churn_test.png](comparison_churn_test.png).",
        "key_findings": ["Enterprise Plan churn is 6%", "Industry benchmark is 3.75%"],
        "sources": ["Database", "Web Search"]
    }
    
    mock_generate = AsyncMock(side_effect=[
        planning_response,
        arg_responses[0],
        arg_responses[1],
        arg_responses[2],
        synthesis_response
    ])
    mock_ollama.generate = mock_generate
    
    memory = MagicMock()
    memory.get = AsyncMock(return_value=None)
    memory.set = AsyncMock()
    
    agent = QueryForgeAgent(registry, mock_ollama, memory, settings)
    
    # 3. Run Query
    query = "Find our highest churn customer segment using internal data and compare with industry trends"
    response = await agent.run(query)
    
    # 4. Assertions
    assert response.answer is not None
    assert "Enterprise Plan has the highest churn" in response.answer
    assert len(response.tool_calls) == 3
    assert response.chart_paths == [mock_chart_path]
    assert response.total_latency_ms > 0
    assert "get_top_churned_segments" in [call.input.tool_name for call in response.tool_calls]

@pytest.mark.asyncio
async def test_agent_uses_minimum_tools(monkeypatch):
    """Verify that the agent logs a warning if planning outputs excessive tool usage (> 3 steps)."""
    # 1. Setup mocks
    settings = MagicMock()
    settings.MAX_PDF_PAGES = 10
    settings.CHARTS_OUTPUT_DIR = "/tmp"
    settings.MAX_TOOL_RETRIES = 1
    
    db_pool = MagicMock()
    mock_ollama = MagicMock()
    
    # Mock 5 steps
    excessive_plan = {
        "steps": [
            {"tool": "get_customer_count_by_segment", "reason": "Reason 1", "depends_on": []},
            {"tool": "get_customer_count_by_segment", "reason": "Reason 2", "depends_on": []},
            {"tool": "get_customer_count_by_segment", "reason": "Reason 3", "depends_on": []},
            {"tool": "get_customer_count_by_segment", "reason": "Reason 4", "depends_on": []},
            {"tool": "get_customer_count_by_segment", "reason": "Reason 5", "depends_on": []}
        ]
    }
    
    mock_generate = AsyncMock(side_effect=[
        excessive_plan,
        {}, {}, {}, {}, {},  # 5 argument calls
        {"answer": "Excessive tools synthesis", "key_findings": [], "sources": []}  # synthesis
    ])
    mock_ollama.generate = mock_generate
    
    from src.tools.database.churn_tools import get_customer_count_by_segment
    from unittest.mock import create_autospec

    mock_get_count = create_autospec(get_customer_count_by_segment)
    mock_get_count.return_value = {"Enterprise": 100}
    mock_get_count.__doc__ = get_customer_count_by_segment.__doc__
    
    monkeypatch.setattr("src.agent.tool_registry.get_customer_count_by_segment", mock_get_count)
    
    registry = ToolRegistry(settings, db_pool, mock_ollama)
    registry.register_all()
    
    memory = MagicMock()
    memory.get = AsyncMock(return_value=None)
    memory.set = MagicMock()
    
    agent = QueryForgeAgent(registry, mock_ollama, memory, settings)
    
    # Use patch to check if warning log is called
    with patch("src.agent.queryforge_agent.logger.warning") as mock_warning:
        response = await agent.run("A simple query that shouldn't need 5 tools")
        
        # Verify warning log was called
        assert mock_warning.called
        assert "Excessive tool use planned" in mock_warning.call_args[0][0]
        
    # Verify execution completes
    assert len(response.tool_calls) == 5
    assert response.answer == "Excessive tools synthesis"
