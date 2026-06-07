from functools import lru_cache

from ..config.settings import Settings
from ..github.client import GitHubClient
from ..memory.vector_store import VectorStore
from ..memory.short_term import ShortTermMemory
from ..memory.long_term import LongTermMemory
from ..llm.ollama_client import OllamaClient
from ..context.harvester import ContextHarvester
from ..context.ranker import ContextRanker
from ..prompt.assembler import PromptAssembler
from ..output.excel_logger import ExcelLogger
from ..output.dispatcher import ReviewDispatcher
from ..agent.review_agent import ReviewAgent


@lru_cache
def get_settings() -> Settings:
    """Retrieve Settings singleton."""
    return Settings()


@lru_cache
def get_github_client() -> GitHubClient:
    """Retrieve GitHubClient singleton."""
    settings = get_settings()
    return GitHubClient(token=settings.GITHUB_TOKEN)


@lru_cache
def get_vector_store() -> VectorStore:
    """Retrieve VectorStore singleton."""
    settings = get_settings()
    return VectorStore(path=settings.CHROMA_PATH)


@lru_cache
def get_short_term_memory() -> ShortTermMemory:
    """Retrieve ShortTermMemory singleton."""
    settings = get_settings()
    return ShortTermMemory(url=settings.DRAGONFLY_URL)


@lru_cache
def get_long_term_memory() -> LongTermMemory:
    """Retrieve LongTermMemory singleton."""
    settings = get_settings()
    vector_store = get_vector_store()
    return LongTermMemory(vector_store=vector_store, sqlite_path=settings.SQLITE_PATH)


@lru_cache
def get_ollama_client() -> OllamaClient:
    """Retrieve OllamaClient singleton."""
    settings = get_settings()
    return OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model_code=settings.OLLAMA_MODEL_CODE,
        model_reason=settings.OLLAMA_MODEL_REASON,
        embed_model=settings.OLLAMA_EMBED_MODEL
    )


@lru_cache
def get_harvester() -> ContextHarvester:
    """Retrieve ContextHarvester singleton."""
    settings = get_settings()
    vector_store = get_vector_store()
    github_client = get_github_client()
    return ContextHarvester(
        vector_store=vector_store,
        github_client=github_client,
        settings=settings
    )


@lru_cache
def get_ranker() -> ContextRanker:
    """Retrieve ContextRanker singleton."""
    settings = get_settings()
    ollama_client = get_ollama_client()
    return ContextRanker(ollama_client=ollama_client, settings=settings)


@lru_cache
def get_assembler() -> PromptAssembler:
    """Retrieve PromptAssembler singleton."""
    settings = get_settings()
    return PromptAssembler(max_context_tokens=settings.MAX_CONTEXT_TOKENS)


@lru_cache
def get_excel_logger() -> ExcelLogger:
    """Retrieve ExcelLogger singleton."""
    settings = get_settings()
    return ExcelLogger(excel_path=settings.EXCEL_PATH)


@lru_cache
def get_dispatcher() -> ReviewDispatcher:
    """Retrieve ReviewDispatcher singleton."""
    github_client = get_github_client()
    excel_logger = get_excel_logger()
    return ReviewDispatcher(github_client=github_client, excel_logger=excel_logger)


@lru_cache
def get_agent() -> ReviewAgent:
    """Retrieve ReviewAgent singleton with all 7 dependencies."""
    return ReviewAgent(
        harvester=get_harvester(),
        ranker=get_ranker(),
        assembler=get_assembler(),
        ollama=get_ollama_client(),
        dispatcher=get_dispatcher(),
        memory=get_long_term_memory(),
        settings=get_settings()
    )
