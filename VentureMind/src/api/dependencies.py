from functools import lru_cache

# 1. Import order: settings → llm → memory → agents → orchestrator
from ..config.settings import get_settings, Settings
from ..llm.ollama_client import OllamaClient
from ..llm.adk_bridge import OllamaADKModel
from ..memory.shared_memory import SharedMemory
from ..memory.database import ReportDatabase
from ..agents.market_research.agent import MarketResearchAgent
from ..agents.competitor.agent import CompetitorAgent
from ..agents.financial.agent import FinancialAgent
from ..agents.legal.agent import LegalAgent
from ..agents.summarization.agent import SummarizationAgent
from ..orchestrator.orchestrator import DiligenceOrchestrator
from ..report.renderer import ReportRenderer

# Import tools to construct the registry dictionaries passed to specialist agents
from ..tools.financial.market_tools import (
    get_industry_market_size,
    get_market_growth_rate,
    get_market_trends,
    get_wikipedia_industry_overview,
)
from ..tools.search.competitor_tools import (
    find_competitors,
    get_company_info,
    get_funding_info,
)
from ..tools.financial.financial_tools import (
    get_sec_edgar_filings,
    get_crunchbase_signals,
    get_pitchbook_signals,
    estimate_revenue,
    get_job_posting_signals,
)
from ..tools.legal.legal_tools import (
    search_litigation,
    check_patent_activity,
    check_trademark_status,
    check_incorporation_status,
    search_regulatory_issues,
)


@lru_cache
def get_ollama_client() -> OllamaClient:
    """FastAPI dependency factory providing a singleton OllamaClient instance."""
    settings = get_settings()
    return OllamaClient(
        base_url=str(settings.OLLAMA_BASE_URL),
        orchestrator_model=settings.OLLAMA_ORCHESTRATOR_MODEL,
        analyst_model=settings.OLLAMA_ANALYST_MODEL,
        summary_model=settings.OLLAMA_SUMMARY_MODEL,
        embed_model=settings.OLLAMA_EMBED_MODEL,
        timeout=float(settings.AGENT_TIMEOUT_SECONDS),
    )


@lru_cache
def get_adk_bridge() -> OllamaADKModel:
    """FastAPI dependency factory providing a singleton OllamaADKModel instance."""
    client = get_ollama_client()
    settings = get_settings()
    return OllamaADKModel(
        ollama_client=client,
        model_name=settings.OLLAMA_ANALYST_MODEL,
    )


@lru_cache
def get_shared_memory() -> SharedMemory:
    """FastAPI dependency factory providing a singleton SharedMemory instance."""
    settings = get_settings()
    return SharedMemory(db_path=str(settings.DRAGONFLY_URL))


@lru_cache
def get_report_database() -> ReportDatabase:
    """FastAPI dependency factory providing a singleton ReportDatabase instance."""
    settings = get_settings()
    return ReportDatabase(database_url=str(settings.DATABASE_URL))


@lru_cache
def get_market_agent() -> MarketResearchAgent:
    """FastAPI dependency factory providing a singleton MarketResearchAgent instance."""
    client = get_ollama_client()
    settings = get_settings()
    tools = {
        "get_industry_market_size": get_industry_market_size,
        "get_market_growth_rate": get_market_growth_rate,
        "get_market_trends": get_market_trends,
        "get_wikipedia_industry_overview": get_wikipedia_industry_overview,
    }
    return MarketResearchAgent(ollama_client=client, tools=tools, settings=settings)


@lru_cache
def get_competitor_agent() -> CompetitorAgent:
    """FastAPI dependency factory providing a singleton CompetitorAgent instance."""
    client = get_ollama_client()
    settings = get_settings()
    tools = {
        "find_competitors": find_competitors,
        "get_company_info": get_company_info,
        "get_funding_info": get_funding_info,
    }
    return CompetitorAgent(ollama_client=client, tools=tools, settings=settings)


@lru_cache
def get_financial_agent() -> FinancialAgent:
    """FastAPI dependency factory providing a singleton FinancialAgent instance."""
    client = get_ollama_client()
    settings = get_settings()
    tools = {
        "get_sec_edgar_filings": get_sec_edgar_filings,
        "get_crunchbase_signals": get_crunchbase_signals,
        "get_pitchbook_signals": get_pitchbook_signals,
        "estimate_revenue": estimate_revenue,
        "get_job_posting_signals": get_job_posting_signals,
    }
    return FinancialAgent(ollama_client=client, tools=tools, settings=settings)


@lru_cache
def get_legal_agent() -> LegalAgent:
    """FastAPI dependency factory providing a singleton LegalAgent instance."""
    client = get_ollama_client()
    settings = get_settings()
    tools = {
        "search_litigation": search_litigation,
        "check_patent_activity": check_patent_activity,
        "check_trademark_status": check_trademark_status,
        "check_incorporation_status": check_incorporation_status,
        "search_regulatory_issues": search_regulatory_issues,
    }
    return LegalAgent(ollama_client=client, tools=tools, settings=settings)


@lru_cache
def get_summarization_agent() -> SummarizationAgent:
    """FastAPI dependency factory providing a singleton SummarizationAgent instance."""
    client = get_ollama_client()
    settings = get_settings()
    return SummarizationAgent(ollama_client=client, settings=settings)


@lru_cache
def get_orchestrator() -> DiligenceOrchestrator:
    """FastAPI dependency factory providing a singleton DiligenceOrchestrator instance."""
    market = get_market_agent()
    competitor = get_competitor_agent()
    financial = get_financial_agent()
    legal = get_legal_agent()
    summarization = get_summarization_agent()

    agents = {
        "market_research": market,
        "competitor": competitor,
        "financial": financial,
        "legal": legal,
        "summarization": summarization,
    }
    memory = get_shared_memory()
    settings = get_settings()

    return DiligenceOrchestrator(agents=agents, memory=memory, settings=settings)


@lru_cache
def get_renderer() -> ReportRenderer:
    """FastAPI dependency factory providing a singleton ReportRenderer instance."""
    settings = get_settings()
    return ReportRenderer(output_dir=settings.REPORTS_OUTPUT_DIR)
