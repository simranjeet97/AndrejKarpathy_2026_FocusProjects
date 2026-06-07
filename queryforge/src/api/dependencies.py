from functools import lru_cache
from src.config.settings import get_settings, Settings
from src.tools.database.connection import get_pool, AsyncDBPool
from src.llm.ollama_client import OllamaClient
from src.llm.adk_bridge import OllamaADKModel
from src.memory.agent_memory import AgentMemory
from src.tools.charts.chart_tool import ChartTool
from src.tools.pdf.pdf_tool import PDFTool
from src.agent.tool_registry import ToolRegistry
from src.agent.queryforge_agent import QueryForgeAgent

@lru_cache
def get_db_pool() -> AsyncDBPool:
    """Fastapi dependency for AsyncDBPool singleton."""
    settings = get_settings()
    pool = get_pool(str(settings.DATABASE_URL))
    pool.memory = get_memory()
    return pool

@lru_cache
def get_ollama_client() -> OllamaClient:
    """Fastapi dependency for OllamaClient singleton."""
    settings = get_settings()
    return OllamaClient(
        base_url=str(settings.OLLAMA_BASE_URL),
        agent_model=settings.OLLAMA_AGENT_MODEL,
        embed_model=settings.OLLAMA_EMBED_MODEL
    )

@lru_cache
def get_adk_bridge() -> OllamaADKModel:
    """Fastapi dependency for OllamaADKModel singleton."""
    settings = get_settings()
    client = get_ollama_client()
    return OllamaADKModel(model=settings.OLLAMA_AGENT_MODEL, client=client)

@lru_cache
def get_memory() -> AgentMemory:
    """Fastapi dependency for AgentMemory singleton."""
    settings = get_settings()
    return AgentMemory(url=str(settings.DRAGONFLY_URL))

@lru_cache
def get_chart_tool() -> ChartTool:
    """Fastapi dependency for ChartTool singleton."""
    settings = get_settings()
    return ChartTool(output_dir=settings.CHARTS_OUTPUT_DIR)

@lru_cache
def get_pdf_tool() -> PDFTool:
    """Fastapi dependency for PDFTool singleton."""
    import os
    settings = get_settings()
    client = get_ollama_client()
    pdf_dir = os.path.abspath(os.path.join(settings.CHARTS_OUTPUT_DIR, "../pdfs"))
    return PDFTool(ollama_client=client, max_pages=settings.MAX_PDF_PAGES, pdf_dir=pdf_dir)

@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Fastapi dependency for ToolRegistry singleton, registering all tools."""
    settings = get_settings()
    db_pool = get_db_pool()
    client = get_ollama_client()
    registry = ToolRegistry(settings=settings, db_pool=db_pool, ollama_client=client)
    registry.register_all()
    return registry

@lru_cache
def get_agent() -> QueryForgeAgent:
    """Fastapi dependency for QueryForgeAgent singleton."""
    settings = get_settings()
    registry = get_tool_registry()
    bridge = get_adk_bridge()
    memory = get_memory()
    return QueryForgeAgent(
        tool_registry=registry,
        ollama_bridge=bridge,
        memory=memory,
        settings=settings
    )
