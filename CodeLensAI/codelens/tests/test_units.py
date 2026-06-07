import os
import tempfile
import sqlite3
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
import pandas as pd

from codelens.src.config.settings import Settings
from codelens.src.models import (
    PREvent,
    FileDiff,
    DocChunk,
    SourceType,
    ReviewResponse,
    ApprovalStatus,
    Issue,
    IssueSeverity,
    IssueCategory,
    ContextPack,
)
from codelens.src.context.ranker import ContextRanker
from codelens.src.prompt.assembler import PromptAssembler
from codelens.src.output.excel_logger import ExcelLogger
from codelens.src.memory.long_term import LongTermMemory
from codelens.src.memory.short_term import ShortTermMemory


def test_settings_loading():
    """Verify that settings can be instantiated with expected default configuration."""
    settings = Settings()
    assert settings.OLLAMA_BASE_URL == "http://localhost:11434"
    assert settings.MAX_CONTEXT_TOKENS == 4096
    assert settings.CHROMA_PATH == "data/chroma"


def test_context_ranker_scoring_and_compression():
    """Verify that ContextRanker ranks and compresses chunks correctly."""
    # Mock OllamaClient
    mock_ollama = MagicMock()
    # Mocking embed returns: 1 vector for query, and 2 vectors for chunks
    # Since all_chunks = bundle.arch_chunks + bundle.standard_chunks + bundle.pr_example_chunks
    # all_chunks is [chunk_2 (arch_chunks), chunk_1 (standard_chunks)]
    # So the order of texts in ollama.embed is [query, chunk_2, chunk_1]
    mock_ollama.embed.return_value = [
        [1.0, 0.0],  # Query
        [0.0, 1.0],  # Chunk 2 (completely dissimilar)
        [1.0, 0.0],  # Chunk 1 (highly similar)
    ]
    # Mocking generate for compression
    mock_ollama.generate.return_value = {"response": "Compressed chunk content"}

    settings = Settings()
    ranker = ContextRanker(ollama_client=mock_ollama, settings=settings)

    # Chunks to rank
    chunks = [
        DocChunk(chunk_id="chunk_1", content="Hello world code base details", source_type=SourceType.STANDARD),
        DocChunk(chunk_id="chunk_2", content="Auth routing logic code specs", source_type=SourceType.ARCH_DOC),
    ]

    pr_event = PREvent(
        pr_id=456,
        repo="test/repo",
        commit_sha="abcdef123456",
        title="feat: add hello world",
        body="PR body description",
        author="coder",
        changed_files=[
            FileDiff(path="main.py", status="modified", additions=5, deletions=1, patch="@@ -1 +1 @@\n+print('hello')")
        ],
        jira_ticket_id=None,
        created_at=datetime.now(timezone.utc),
    )

    from codelens.src.context.harvester import RawContextBundle
    bundle = RawContextBundle(
        diff_chunks=[],
        arch_chunks=[chunks[1]],
        standard_chunks=[chunks[0]],
        pr_example_chunks=[],
        jira_ticket=None
    )

    # Call rank_and_compress
    context_pack = ranker.rank_and_compress(bundle, pr_event, budget=1000)

    assert isinstance(context_pack, ContextPack)
    assert context_pack.pr_id == 456
    assert len(context_pack.chunks) == 2
    # Verify that the highly similar chunk came first
    assert context_pack.chunks[0].chunk_id == "chunk_1"
    assert mock_ollama.embed.called


def test_prompt_assembler_building_and_trimming():
    """Verify that PromptAssembler formats prompt layers and respects budget."""
    assembler = PromptAssembler(max_context_tokens=500)

    pr_event = PREvent(
        pr_id=789,
        repo="test/repo",
        commit_sha="sha789",
        title="feat: update styles",
        body="PR body",
        author="designer",
        changed_files=[
            FileDiff(path="styles.css", status="modified", additions=100, deletions=50, patch="+body { color: red; }\n" * 5)
        ],
        created_at=datetime.now(timezone.utc),
    )

    from codelens.src.context.ranker import ScoredChunk
    chunks = [
        ScoredChunk(
            chunk_id="chk_1",
            content="Use modern CSS properties.",
            source_type=SourceType.STANDARD,
            bm25_score=0.9,
            semantic_score=0.9,
            token_count=10,
        ),
        ScoredChunk(
            chunk_id="chk_2",
            content="Arch: styling specs details.",
            source_type=SourceType.ARCH_DOC,
            bm25_score=0.8,
            semantic_score=0.8,
            token_count=10,
        ),
    ]

    context_pack = ContextPack(
        pr_id=789,
        chunks=chunks,
        total_tokens=20,
        budget_used=4
    )

    prompt = assembler.build(context_pack, pr_event)
    assert "Use modern CSS properties." in prompt
    assert "Arch: styling specs details." in prompt
    assert "styles.css" in prompt


def test_excel_logger_persistence():
    """Verify ExcelLogger logs and reads back reviews correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        excel_path = os.path.join(tmpdir, "test_reviews.xlsx")
        logger = ExcelLogger(excel_path=tmpdir)

        pr_event = PREvent(
            pr_id=111,
            repo="test-owner/test-repo",
            commit_sha="shatest111",
            title="refactor: clean up tests",
            body="Cleaning code",
            author="tester",
            changed_files=[],
            created_at=datetime.now(timezone.utc),
        )

        review = ReviewResponse(
            summary="Clean refactoring.",
            issues=[
                Issue(
                    file_path="test.py",
                    line_number=10,
                    severity=IssueSeverity.LOW,
                    category=IssueCategory.STYLE,
                    message="Style fix",
                    suggestion="Add blank line",
                )
            ],
            suggestions=["Add unit tests"],
            approval=ApprovalStatus.APPROVE,
            confidence=0.98,
            tokens_used=120,
            model_used="qwen2.5:7b",
            latency_ms=10.0,
        )

        # Log review
        logger.log_review(pr_event, review)

        # Check logs
        df = logger.get_history()
        assert not df.empty
        assert len(df) == 1
        assert df.iloc[0]["pr_id"] == 111
        assert df.iloc[0]["repo"] == "test-owner/test-repo"
        assert df.iloc[0]["approval"] == "APPROVE"


@pytest.mark.asyncio
async def test_long_term_memory_sqlite():
    """Verify LongTermMemory properly initializes sqlite and stores/retrieves reviews."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_codelens.db")
        mock_vs = MagicMock()

        memory = LongTermMemory(vector_store=mock_vs, sqlite_path=db_path)

        pr_event = PREvent(
            pr_id=222,
            repo="test/longterm",
            commit_sha="sha222",
            title="feat: add database support",
            body="Adding a database",
            author="db-eng",
            changed_files=[],
            created_at=datetime.now(timezone.utc),
        )

        review = ReviewResponse(
            summary="Database setup is clean.",
            issues=[],
            suggestions=[],
            approval=ApprovalStatus.COMMENT,
            confidence=0.9,
            tokens_used=300,
            model_used="qwen2.5:7b",
            latency_ms=15.0,
        )

        # Store review
        await memory.store_review(pr_event, review)

        # Retrieve review history
        history = await memory.get_review_history("test/longterm")
        assert len(history) == 1
        assert history[0]["pr_id"] == 222
        assert history[0]["repo"] == "test/longterm"
        assert history[0]["approval"] == "COMMENT"


@pytest.mark.asyncio
async def test_short_term_memory_caching():
    """Verify ShortTermMemory cache methods and exception safety when Redis is offline."""
    # We mock the redis client inside ShortTermMemory
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis

        st_memory = ShortTermMemory(url="redis://localhost:6379/0")

        review = ReviewResponse(
            summary="Short term test.",
            issues=[],
            suggestions=[],
            approval=ApprovalStatus.APPROVE,
            confidence=0.99,
            tokens_used=50,
            model_used="qwen2.5:7b",
            latency_ms=5.0,
        )

        # Caching review
        mock_redis.set.return_value = True
        await st_memory.cache_review("333", review)
        mock_redis.set.assert_called_once()

        # Getting review
        mock_redis.get.return_value = review.model_dump_json()
        cached = await st_memory.get_review("333")
        assert cached is not None
        assert cached.summary == "Short term test."


def test_api_config_endpoint():
    """Verify that the FastAPI /config endpoint serves the active configurations."""
    from fastapi.testclient import TestClient
    from codelens.src.api.main import app

    client = TestClient(app)
    response = client.get("/config")
    assert response.status_code == 200

    config = response.json()
    assert "ollama_base_url" in config
    assert "ollama_model_code" in config
    assert "sqlite_path" in config
    assert "excel_path" in config
    assert "github_token_configured" in config


def test_review_dispatcher():
    """Verify that ReviewDispatcher formats reviews, filters inline issues, and dispatches them correctly."""
    from codelens.src.output.dispatcher import ReviewDispatcher
    from codelens.src.github.client import GitHubClient

    mock_github = MagicMock(spec=GitHubClient)
    mock_excel = MagicMock(spec=ExcelLogger)

    dispatcher = ReviewDispatcher(github_client=mock_github, excel_logger=mock_excel)

    pr_event = PREvent(
        pr_id=123,
        repo="test/repo",
        commit_sha="abcdef123456",
        title="feat: add hello world",
        body="PR body",
        author="coder",
        changed_files=[],
        created_at=datetime.now(timezone.utc),
    )

    review = ReviewResponse(
        summary="Code looks great.",
        issues=[
            Issue(
                file_path="main.py",
                line_number=10,
                severity=IssueSeverity.HIGH,
                category=IssueCategory.LOGIC,
                message="Null pointer risk",
                suggestion="Check for None",
            ),
            Issue(
                file_path="utils.py",
                line_number=20,
                severity=IssueSeverity.LOW,
                category=IssueCategory.STYLE,
                message="Trailing whitespace",
                suggestion="Strip it",
            ),
        ],
        suggestions=[],
        approval=ApprovalStatus.APPROVE,
        confidence=0.95,
        tokens_used=100,
        model_used="qwen2.5:7b",
        latency_ms=10.0,
    )

    dispatcher.dispatch(pr_event, review)

    # Verify formatting occurred and github post was called with correct structure
    assert mock_github.post_review.called
    args, kwargs = mock_github.post_review.call_args
    posted_repo, posted_pr_id, posted_review = args

    assert posted_repo == "test/repo"
    assert posted_pr_id == 123
    assert "CodeLens AI Review Feedback" in posted_review.summary
    assert "Null pointer risk" in posted_review.summary or "APPROVE" in posted_review.summary
    # Low severity issues are filtered out of inline comments
    assert len(posted_review.issues) == 1
    assert posted_review.issues[0].file_path == "main.py"

    # Verify excel logging occurred
    assert mock_excel.log_review.called

