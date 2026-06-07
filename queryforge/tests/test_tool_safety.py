import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock

# Imports
from src.tools.database.churn_tools import get_monthly_churn_by_segment
from src.tools.api.stripe_tools import get_stripe_customer_segment
from src.tools.api.markdown_kb_tools import get_markdown_file_content
from src.tools.web.search_tool import search_web
from src.agent.queryforge_agent import QueryForgeAgent
from src.models import PermissionLevel

def test_no_raw_sql_in_churn_tools():
    """Verify that churn_tools.py does not contain dynamically formatted SQL via f-strings."""
    import src.tools.database.churn_tools as churn_tools
    source = inspect.getsource(churn_tools)

    for line in source.split("\n"):
        if "f\"" in line or "f'" in line:
            line_lower = line.lower()
            sql_keywords = ["select", "insert", "update", "delete", "where", "join", "group by"]
            assert not any(kw in line_lower for kw in sql_keywords), (
                f"Potential raw SQL f-string injection found in line: {line}"
            )

@pytest.mark.asyncio
async def test_customer_id_validation():
    """Verify that get_stripe_customer_segment rejects invalid Stripe customer IDs."""
    with pytest.raises(ValueError):
        await get_stripe_customer_segment("DROP TABLE customers")
    with pytest.raises(ValueError):
        await get_stripe_customer_segment("cus_123; SELECT * FROM users")

@pytest.mark.asyncio
async def test_markdown_kb_path_traversal():
    """Verify get_markdown_file_content rejects path traversal out of the knowledge directory."""
    with pytest.raises(ValueError):
        await get_markdown_file_content("/etc/passwd")
    with pytest.raises(ValueError):
        await get_markdown_file_content("../../../etc/passwd")

def test_permission_check_blocks_restricted():
    """Verify _check_permission blocks restricted tools for queries without business context."""
    tool_registry = MagicMock()
    mock_permission = MagicMock()
    mock_permission.permission_level = PermissionLevel.RESTRICTED
    tool_registry.permissions = {"get_stripe_customer_segment": mock_permission}

    agent = QueryForgeAgent(
        tool_registry=tool_registry,
        ollama_bridge=MagicMock(),
        memory=MagicMock(),
        settings=MagicMock()
    )

    # Context without business keywords
    assert agent._check_permission("get_stripe_customer_segment", "What is the weather today?") is False

    # Context with business keywords
    assert agent._check_permission("get_stripe_customer_segment", "Retrieve LTV and MRR for customer segment") is True

@pytest.mark.asyncio
async def test_web_search_rejects_sql_injection():
    """Verify search_web rejects SQL injection attempts in search queries."""
    with pytest.raises(ValueError):
        await search_web("SELECT * FROM users")
    with pytest.raises(ValueError):
        await search_web("UNION SELECT username, password FROM administrators")

@pytest.mark.asyncio
async def test_database_tools_use_parameterized_queries(monkeypatch):
    """Verify that database tools pass parameters separately instead of formatting SQL directly."""
    mock_pool = MagicMock()
    mock_pool.execute_query = AsyncMock()

    # Patch get_pool to return our mock pool
    monkeypatch.setattr("src.tools.database.churn_tools.get_pool", lambda: mock_pool)

    # Run the function
    await get_monthly_churn_by_segment("06", 2026)

    # Assert execute_query was called
    assert mock_pool.execute_query.called
    args, _ = mock_pool.execute_query.call_args
    query_str = args[0]
    params = args[1]

    # Assert query string has placeholders ($1, $2) and separate parameters tuple is passed
    assert "$1" in query_str
    assert "$2" in query_str
    assert len(params) == 2

@pytest.mark.asyncio
async def test_pdf_tool_path_traversal():
    """Verify PDFTool rejects path traversal out of the pdfs directory."""
    from src.tools.pdf.pdf_tool import PDFTool
    from unittest.mock import MagicMock
    
    pdf_tool = PDFTool(ollama_client=MagicMock(), max_pages=10, pdf_dir="/workspace/data/pdfs")
    
    # _extract_text should raise ValueError directly
    with pytest.raises(ValueError):
        pdf_tool._extract_text("/etc/passwd")
    with pytest.raises(ValueError):
        pdf_tool._extract_text("/workspace/data/pdfs/../../../etc/passwd")
        
    # summarize_pdf should catch ValueError and return a PDFSummary with error
    res1 = await pdf_tool.summarize_pdf("/etc/passwd")
    assert "Error:" in res1.summary
    res2 = await pdf_tool.summarize_pdf("/workspace/data/pdfs/../../../etc/passwd")
    assert "Error:" in res2.summary

@pytest.mark.asyncio
async def test_web_search_ssrf():
    """Verify fetch_page_content rejects internal/loopback/private IP addresses (SSRF)."""
    from src.tools.web.search_tool import fetch_page_content
    
    with pytest.raises(ValueError):
        await fetch_page_content("http://127.0.0.1:8080/admin")
    with pytest.raises(ValueError):
        await fetch_page_content("http://localhost:9000/info")
    with pytest.raises(ValueError):
        await fetch_page_content("http://169.254.169.254/latest/meta-data")

@pytest.mark.asyncio
async def test_background_job_serialization(monkeypatch):
    """Verify fetch_industry_benchmarks job serializes datetime objects successfully."""
    from src.scheduler.jobs import fetch_industry_benchmarks
    from src.models import IndustryBenchmark
    from datetime import datetime
    
    mock_benchmarks = [
        IndustryBenchmark(
            metric_name="churn",
            value=0.035,
            source="http://example.com",
            retrieved_at=datetime.utcnow()
        )
    ]
    
    async def mock_search_bench(*args, **kwargs):
        return mock_benchmarks
        
    monkeypatch.setattr("src.scheduler.jobs.search_industry_benchmarks", mock_search_bench)
    
    mock_memory = MagicMock()
    mock_memory.client = AsyncMock()
    
    # Run the background job (should not raise TypeError: datetime is not JSON serializable)
    await fetch_industry_benchmarks(mock_memory)
    
    # Assert setex was called
    assert mock_memory.client.setex.called

def test_resolve_date_params_with_ints():
    """Verify that _resolve_date_params in both tools handles integer month inputs successfully."""
    from src.tools.database.revenue_tools import _resolve_date_params as rev_resolve
    from src.tools.database.churn_tools import _resolve_date_params as churn_resolve

    assert rev_resolve(1, 2023) == (1, 2023)
    assert rev_resolve("1", 2023) == (1, 2023)
    assert rev_resolve("january", 2023) == (1, 2023)

    assert churn_resolve(1, 2023) == (1, 2023)
    assert churn_resolve("1", 2023) == (1, 2023)
    assert churn_resolve("january", 2023) == (1, 2023)

def test_chart_parsing_robustness():
    """Verify chart tools do not raise TypeError on non-float dictionary values."""
    from src.tools.charts.chart_tool import ChartTool
    
    chart_tool = ChartTool(output_dir="/tmp")
    
    # Test generate_revenue_chart doesn't crash when list is passed as a value in dict
    res = chart_tool.generate_revenue_chart(
        revenue_data={"segment": "Enterprise", "time_period": ["current_month", "last_month"], "metric": "MRR"}
    )
    assert res is not None
    assert res.filepath is not None
    
    # Test generate_generic_chart doesn't crash with similar inputs
    res_gen = chart_tool.generate_generic_chart(
        data={"segment": "Enterprise", "time_period": ["current_month", "last_month"], "metric": "MRR"},
        title="Test Metric"
    )
    assert res_gen is not None

