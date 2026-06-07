import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
import chromadb
from chromadb.utils.embedding_functions import known_embedding_functions

from codelens.src.models import (
    PREvent,
    FileDiff,
    ReviewResponse,
    ApprovalStatus,
    DocChunk,
    SourceType,
)
from codelens.src.config.settings import Settings
from codelens.src.memory.vector_store import VectorStore
from codelens.src.context.harvester import ContextHarvester
from codelens.src.context.ranker import ContextRanker
from codelens.src.prompt.assembler import PromptAssembler
from codelens.src.output.excel_logger import ExcelLogger
from codelens.src.output.dispatcher import ReviewDispatcher
from codelens.src.memory.long_term import LongTermMemory
from codelens.src.agent.review_agent import ReviewAgent
from codelens.src.github.client import GitHubClient
from codelens.src.llm.ollama_client import OllamaClient


class MockEmbeddingFunction(chromadb.EmbeddingFunction):
    """Mock embedding function to avoid downloading models from HuggingFace."""
    def __init__(self):
        pass

    def __call__(self, input):
        return [[0.1] * 384 for _ in input]

    @classmethod
    def name(cls) -> str:
        return "MockEmbeddingFunction"

    @classmethod
    def is_legacy(cls) -> bool:
        return False

    @classmethod
    def get_config(cls) -> dict:
        return {}

    @classmethod
    def build_from_config(cls, config: dict):
        return cls()


# Register the mock embedding function in ChromaDB's known registry
known_embedding_functions["MockEmbeddingFunction"] = MockEmbeddingFunction


@pytest.mark.asyncio
async def test_full_pr_review_flow():
    # 1. Create a mock PREvent with 3 changed Python files
    changed_files = [
        FileDiff(
            path="src/main.py",
            status="modified",
            additions=10,
            deletions=2,
            patch="@@ -1,5 +1,13 @@\n def main():\n+    print('Hello World')\n+    x = 1\n+    y = 2\n+    return x + y\n-    pass",
        ),
        FileDiff(
            path="src/utils.py",
            status="modified",
            additions=5,
            deletions=0,
            patch="@@ -1,3 +1,8 @@\n+def add(a, b):\n+    return a + b\n",
        ),
        FileDiff(
            path="src/auth.py",
            status="added",
            additions=20,
            deletions=0,
            patch="@@ -0,0 +1,20 @@\n+class Auth:\n+    def login(self):\n+        return True\n",
        ),
    ]

    pr_event = PREvent(
        pr_id=123,
        repo="test-owner/test-repo",
        commit_sha="mocksha1234567890abcdef",
        title="feat: add hello world and login",
        body="This PR implements basic hello world printing and auth structure.",
        author="testuser",
        changed_files=changed_files,
        jira_ticket_id="PROJ-456",
        created_at=datetime.now(timezone.utc),
    )

    # 2. Mock GitHubClient to return the PREvent without hitting real API
    mock_github_client = MagicMock(spec=GitHubClient)
    mock_github_client.get_pr.return_value = pr_event
    mock_github_client.post_review.return_value = True
    mock_github_client.post_inline_comment.return_value = True

    # Define paths for temporary databases
    sqlite_path = "test_sqlite.db"
    excel_path = "test_excel.xlsx"

    # Instantiate Settings
    settings = Settings()
    settings.MAX_CONTEXT_TOKENS = 4096
    settings.CHROMA_PATH = "test_chroma"
    settings.SQLITE_PATH = sqlite_path
    settings.EXCEL_PATH = excel_path

    # 3. Use real ChromaDB (in-memory: chromadb.EphemeralClient) with mock embeddings
    mock_emb = MockEmbeddingFunction()
    real_vector_store = VectorStore(path=settings.CHROMA_PATH, embedding_function=mock_emb)
    real_vector_store.client = chromadb.EphemeralClient()

    # Pre-populate ChromaDB with mock chunks so harvesting works
    arch_chunks = [
        DocChunk(
            chunk_id="arch_1",
            content="This architecture specifies using main.py and hello world functions.",
            source_type=SourceType.ARCH_DOC,
            metadata={"file_path": "src/main.py"},
        )
    ]
    standards_chunks = [
        DocChunk(
            chunk_id="std_1",
            content="Always write clean code and document functions in utils.py.",
            source_type=SourceType.STANDARD,
            metadata={"file_path": "src/utils.py"},
        )
    ]
    pr_example_chunks = [
        DocChunk(
            chunk_id="pr_1",
            content="PR Title: feat: add hello world\nPR Author: testuser\nReview Summary: Looks good\nApproval Status: APPROVE",
            source_type=SourceType.PR_EXAMPLE,
            metadata={"pr_id": "122", "repo": "test-owner/test-repo"},
        )
    ]

    real_vector_store.add_documents("arch_docs", arch_chunks)
    real_vector_store.add_documents("standards", standards_chunks)
    real_vector_store.add_documents("pr_examples", pr_example_chunks)

    # 4. Mock OllamaClient.generate to return a valid ReviewResponse JSON
    mock_review_response_json = {
        "summary": "The PR looks good overall. Minor suggestions for comments.",
        "issues": [
            {
                "file_path": "src/main.py",
                "line_number": 5,
                "severity": "HIGH",
                "category": "STYLE",
                "message": "Prefer absolute imports.",
                "suggestion": "Change import to absolute format.",
            }
        ],
        "suggestions": ["Add unit tests for main function."],
        "approval": "APPROVE",
        "confidence": 0.95,
        "tokens_used": 1200,
        "model_used": "mock-ollama-model",
        "latency_ms": 150.5,
    }

    mock_ollama_client = MagicMock(spec=OllamaClient)

    def mock_generate(prompt, expect_json=True, **kwargs):
        if expect_json:
            return mock_review_response_json
        return {"response": "Mock text response"}

    mock_ollama_client.generate.side_effect = mock_generate
    mock_ollama_client.embed.side_effect = lambda texts: [[0.1] * 128 for _ in texts]

    # Instantiate remaining real dependencies
    harvester = ContextHarvester(
        vector_store=real_vector_store,
        github_client=mock_github_client,
        settings=settings,
    )
    ranker = ContextRanker(ollama_client=mock_ollama_client, settings=settings)
    assembler = PromptAssembler(max_context_tokens=settings.MAX_CONTEXT_TOKENS)
    excel_logger = ExcelLogger(excel_path=excel_path)
    dispatcher = ReviewDispatcher(github_client=mock_github_client, excel_logger=excel_logger)
    memory = LongTermMemory(vector_store=real_vector_store, sqlite_path=sqlite_path)

    try:
        # Patch ShortTermMemory to prevent Redis connection during agent __init__
        with patch(
            "codelens.src.memory.short_term.ShortTermMemory"
        ) as MockShortTermMemory:
            mock_short_term = MagicMock()
            mock_short_term.get_review = AsyncMock(return_value=None)
            mock_short_term.get_context = AsyncMock(return_value=None)
            mock_short_term.cache_review = AsyncMock(return_value=None)
            mock_short_term.cache_context = AsyncMock(return_value=None)
            mock_short_term.health_check = AsyncMock(return_value=True)
            MockShortTermMemory.return_value = mock_short_term

            # Instantiate ReviewAgent
            agent = ReviewAgent(
                harvester=harvester,
                ranker=ranker,
                assembler=assembler,
                ollama=mock_ollama_client,
                dispatcher=dispatcher,
                memory=memory,
                settings=settings,
            )

            # 5. Run ReviewAgent.run(pr_event)
            state = await agent.run(pr_event)

            # 6. Assertions
            assert state["review"] is not None
            assert state["review"].approval in [
                ApprovalStatus.APPROVE,
                ApprovalStatus.REQUEST_CHANGES,
                ApprovalStatus.COMMENT,
            ]
            assert state["error"] is None
            assert state["context_pack"] is not None
            assert state["context_pack"].total_tokens > 0

    finally:
        # Cleanup temporary files
        if os.path.exists(sqlite_path):
            try:
                os.remove(sqlite_path)
            except Exception:
                pass
        if os.path.exists(excel_path):
            try:
                os.remove(excel_path)
            except Exception:
                pass
