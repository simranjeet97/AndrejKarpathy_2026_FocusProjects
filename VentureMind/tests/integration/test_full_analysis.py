import os
import json
import shutil
import pytest
from src.config.settings import Settings
from src.config import settings as settings_module
from src.api import dependencies
from src.models.domain import AgentStatus

# Create isolated test settings redirecting databases and outputs to a temporary directory
test_settings = Settings(
    DATABASE_URL="sqlite:///data/test_reports/test_reports.db",
    DRAGONFLY_URL="sqlite:///data/test_reports/test_shared_memory.db",
    OLLAMA_BASE_URL="http://localhost:11434",
    OLLAMA_ORCHESTRATOR_MODEL="test-model",
    OLLAMA_ANALYST_MODEL="test-model",
    OLLAMA_SUMMARY_MODEL="test-model",
    OLLAMA_EMBED_MODEL="test-model",
    REPORTS_OUTPUT_DIR="data/test_reports",
    MAX_SEARCH_RESULTS=10,
    MAX_PDF_PAGES=50,
    AGENT_TIMEOUT_SECONDS=120,
    PARALLEL_AGENT_LIMIT=4,
    LOG_LEVEL="INFO"
)


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """Module-level setup to override settings and clean up generated test outputs."""
    # Clear caches of all factory functions to use test settings
    settings_module.get_settings.cache_clear()
    dependencies.get_settings.cache_clear()
    dependencies.get_ollama_client.cache_clear()
    dependencies.get_adk_bridge.cache_clear()
    dependencies.get_shared_memory.cache_clear()
    dependencies.get_report_database.cache_clear()
    dependencies.get_market_agent.cache_clear()
    dependencies.get_competitor_agent.cache_clear()
    dependencies.get_financial_agent.cache_clear()
    dependencies.get_legal_agent.cache_clear()
    dependencies.get_summarization_agent.cache_clear()
    dependencies.get_orchestrator.cache_clear()
    dependencies.get_renderer.cache_clear()
    
    orig_get_settings = settings_module.get_settings
    settings_module.get_settings = lambda: test_settings
    dependencies.get_settings = lambda: test_settings
    
    yield
    
    # Restore original settings
    settings_module.get_settings = orig_get_settings
    dependencies.get_settings = orig_get_settings
    
    # Cleanup directory
    test_dir = "data/test_reports"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


# --- Mock Tool Coroutines ---

async def mock_search_company(*args, **kwargs):
    return [{"title": "TestCo company profile", "snippet": "TestCo founded in 2022 by Alice and Bob.", "url": "https://testco.io"}]

async def mock_get_industry_market_size(*args, **kwargs):
    return {"tam_estimate": "$10 billion", "sources": ["https://gartner.com"]}

async def mock_get_market_growth_rate(*args, **kwargs):
    return {"cagr_estimate": "18.5%", "sources": ["https://idc.com"]}

async def mock_get_market_trends(*args, **kwargs):
    return ["trend 1", "trend 2"]

async def mock_get_wikipedia_industry_overview(*args, **kwargs):
    return "SaaS is a software licensing and delivery model."

async def mock_find_competitors(*args, **kwargs):
    return [{"name": "Comp1", "website": "https://comp1.com"}, {"name": "Comp2", "website": "https://comp2.com"}]

async def mock_get_company_info(*args, **kwargs):
    return {"founded_year": 2020, "website": "https://comp.com"}

async def mock_get_funding_info(*args, **kwargs):
    return {"total_funding_estimate": "$50 million"}

async def mock_get_sec_edgar_filings(*args, **kwargs):
    return [{"form": "Form C", "url": "https://sec.gov"}]

async def mock_get_crunchbase_signals(*args, **kwargs):
    return {"funding_mentions": ["Raised $10M Series A in 2024"]}

async def mock_get_pitchbook_signals(*args, **kwargs):
    return {"funding_mentions": ["Valued at $50M in 2025"]}

async def mock_estimate_revenue(*args, **kwargs):
    return {"revenue_estimate": "$2.5M", "sources": ["https://techcrunch.com"]}

async def mock_get_job_posting_signals(*args, **kwargs):
    return {"hiring_signal": "growing", "source": "https://linkedin.com"}

async def mock_search_litigation(*args, **kwargs):
    return []

async def mock_check_patent_activity(*args, **kwargs):
    return {"patent_count_estimate": 2, "source": "https://patents.google.com"}

async def mock_check_trademark_status(*args, **kwargs):
    return {"trademark_count_estimate": 1, "source": "https://uspto.gov"}

async def mock_check_incorporation_status(*args, **kwargs):
    return {"incorporated": True, "jurisdiction": "Delaware"}

async def mock_search_regulatory_issues(*args, **kwargs):
    return []


# --- Mock Ollama generate Coroutine ---

async def mock_generate(prompt: str, model: str = None, system: str = None, expect_json: bool = False):
    prompt_lower = prompt.lower()
    
    if "extract structural profile information" in prompt_lower or "structural profile" in prompt_lower:
        val = {
            "name": "TestCo",
            "website": "https://testco.io",
            "founded_year": 2022,
            "headquarters": "New York, NY",
            "industry": "SaaS",
            "description": "Enterprise workflow automation SaaS platform.",
            "founders": ["Alice", "Bob"]
        }
    elif "market size metrics" in prompt_lower or "market sizing" in prompt_lower or "tam_usd" in prompt_lower:
        val = {
            "tam_usd": 10000000000.0,
            "sam_usd": 2000000000.0,
            "som_usd": 300000000.0,
            "cagr_pct": 18.5,
            "key_trends": [
                "AI-driven workflow optimization",
                "Transition to product-led growth (PLG)",
                "API-first integration architecture"
            ],
            "sources": ["https://gartner.com/saas-2026", "https://idc.com/reports"]
        }
    elif "positioning_summary" in prompt_lower or "differentiation_score" in prompt_lower:
        val = {
            "positioning_summary": "TestCo is positioned as the high-security enterprise option in workflow SaaS. It holds a distinct technological moat with proprietary automation algorithms compared to legacy players.",
            "differentiation_score": 0.85,
            "key_advantages": ["High security focus", "Advanced integration APIs"]
        }
    elif "burn_rate_estimate" in prompt_lower or "runway_estimate" in prompt_lower or "signals" in prompt_lower:
        val = {
            "signals": [
                {
                    "metric_name": "ARR",
                    "value": "$2.5M",
                    "period": "Q1 2026",
                    "source": "Crunchbase Search",
                    "confidence": 0.9
                },
                {
                    "metric_name": "YoY Growth",
                    "value": "120%",
                    "period": "FY2025",
                    "source": "PitchBook Search",
                    "confidence": 0.8
                }
            ],
            "burn_rate_estimate": "$100k/month",
            "runway_estimate": "24 months"
        }
    elif "flags" in prompt_lower or "severity" in prompt_lower or "flag_type" in prompt_lower:
        val = {
            "flags": [
                {
                    "flag_type": "NONE",
                    "severity": "NONE",
                    "description": "No active lawsuits or trademark disputes identified.",
                    "source": "USPTO and Court Records"
                }
            ]
        }
    elif "3-paragraph executive summary" in prompt_lower or "synthesize" in prompt_lower:
        val = {
            "summary": "TestCo represents a high-potential enterprise SaaS startup showing robust indicators of market viability and financial health. The market research specialist identifies a substantial TAM of $10B growing at 18.5% CAGR, which provides a strong tailwind.\n\nFrom a competitive standpoint, TestCo is well-differentiated (differentiation score of 0.85) due to its high-security enterprise focus. Direct competitors exist but lack equivalent automation APIs, offering a window for market penetration.\n\nFinancially, the company shows low risk with $2.5M ARR and 24 months of estimated runway under a moderate burn rate. Legal and IP diligence shows a clean C-corp structure in Delaware with no litigation issues, making it a highly attractive investment candidate.",
            "key_strengths": ["Proprietary automation APIs", "24-month runway", "Large market opportunity"],
            "key_risks": ["Execution speed in crowded market", "Dependence on enterprise client cycles"]
        }
    elif "investment committee" in prompt_lower or "investment score" in prompt_lower or "rubric" in prompt_lower:
        val = {
            "score": 8.5,
            "rationale": "TestCo has a strong score of 8.5 due to a combination of high market growth, competitive moat, solid financial signals, and clean legal structure.",
            "top_3_reasons": ["Large high-growth addressable market", "Clear product differentiation", "Substantial financial runway"]
        }
    else:
        val = {}
        
    return val if expect_json else json.dumps(val)


@pytest.fixture(autouse=True)
def mock_all_tools(mocker):
    """Fixture applying all tool patches and Ollama client mock generate."""
    mocker.patch("src.tools.search.web_search.search_company", side_effect=mock_search_company)
    
    mocker.patch("src.agents.market_research.agent.get_industry_market_size", side_effect=mock_get_industry_market_size)
    mocker.patch("src.agents.market_research.agent.get_market_growth_rate", side_effect=mock_get_market_growth_rate)
    mocker.patch("src.agents.market_research.agent.get_market_trends", side_effect=mock_get_market_trends)
    mocker.patch("src.agents.market_research.agent.get_wikipedia_industry_overview", side_effect=mock_get_wikipedia_industry_overview)
    
    mocker.patch("src.agents.competitor.agent.find_competitors", side_effect=mock_find_competitors)
    mocker.patch("src.agents.competitor.agent.get_company_info", side_effect=mock_get_company_info)
    mocker.patch("src.agents.competitor.agent.get_funding_info", side_effect=mock_get_funding_info)
    
    mocker.patch("src.agents.financial.agent.get_sec_edgar_filings", side_effect=mock_get_sec_edgar_filings)
    mocker.patch("src.agents.financial.agent.get_crunchbase_signals", side_effect=mock_get_crunchbase_signals)
    mocker.patch("src.agents.financial.agent.get_pitchbook_signals", side_effect=mock_get_pitchbook_signals)
    mocker.patch("src.agents.financial.agent.estimate_revenue", side_effect=mock_estimate_revenue)
    mocker.patch("src.agents.financial.agent.get_job_posting_signals", side_effect=mock_get_job_posting_signals)
    
    mocker.patch("src.agents.legal.agent.search_litigation", side_effect=mock_search_litigation)
    mocker.patch("src.agents.legal.agent.check_patent_activity", side_effect=mock_check_patent_activity)
    mocker.patch("src.agents.legal.agent.check_trademark_status", side_effect=mock_check_trademark_status)
    mocker.patch("src.agents.legal.agent.check_incorporation_status", side_effect=mock_check_incorporation_status)
    mocker.patch("src.agents.legal.agent.search_regulatory_issues", side_effect=mock_search_regulatory_issues)
    
    client = dependencies.get_ollama_client()
    mocker.patch.object(client, "generate", side_effect=mock_generate)


class TestFullAnalysis:
    report = None

    @pytest.mark.asyncio
    async def test_analyze_startup_end_to_end(self):
        """E2E test checking startup dilution analysis runs correctly and gathers all expected agent results."""
        orchestrator = dependencies.get_orchestrator()
        report = await orchestrator.run("TestCo")
        
        # Save to class variable for next test
        TestFullAnalysis.report = report
        
        assert report.startup_name == "TestCo"
        assert 0.0 <= report.investment_score <= 10.0
        assert len(report.agent_results) == 5
        assert report.market is not None
        assert report.summary != ""
        
        analysis_agents = ["market_research", "competitor", "financial", "legal"]
        for agent_name in analysis_agents:
            result = next(r for r in report.agent_results if r.agent_name == agent_name)
            assert result.status == AgentStatus.SUCCESS

    def test_report_renders_without_error(self):
        """Test checking that the final report renders correctly into Markdown format."""
        assert TestFullAnalysis.report is not None
        
        renderer = dependencies.get_renderer()
        markdown = renderer.render_markdown(TestFullAnalysis.report)
        
        assert "TestCo" in markdown
        badge = renderer._render_score_badge(TestFullAnalysis.report.investment_score)
        assert badge in markdown
