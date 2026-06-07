import os
import sqlite3
import asyncio
import logging
import aiosqlite
from typing import List, Dict, Optional
from ..models import PREvent, ReviewResponse, DocChunk, SourceType
from ..memory.vector_store import VectorStore

logger = logging.getLogger(__name__)

class LongTermMemory:
    """Manages SQLite and ChromaDB persistent long-term storage of PR reviews."""

    def __init__(self, vector_store: VectorStore, sqlite_path: str) -> None:
        """
        Initialize the LongTermMemory.

        Args:
            vector_store: Instantiated vector database store.
            sqlite_path: Filepath to SQLite database.
        """
        self.vector_store = vector_store
        self.sqlite_path = sqlite_path
        self._init_db()

    def _init_db(self) -> None:
        """
        Synchronously initialize SQLite database and create reviews table if not exists.
        """
        db_dir = os.path.dirname(self.sqlite_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    pr_id INTEGER,
                    repo TEXT,
                    commit_sha TEXT,
                    summary TEXT,
                    approval TEXT,
                    tokens_used INTEGER,
                    issues_json TEXT,
                    suggestions_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (pr_id, repo)
                )
            """)
            # Check for migration if columns don't exist
            cursor.execute("PRAGMA table_info(reviews)")
            columns = [col[1] for col in cursor.fetchall()]
            if "issues_json" not in columns:
                cursor.execute("ALTER TABLE reviews ADD COLUMN issues_json TEXT")
            if "suggestions_json" not in columns:
                cursor.execute("ALTER TABLE reviews ADD COLUMN suggestions_json TEXT")
            conn.commit()
            conn.close()
            logger.info("Initialized long term SQLite database successfully with migrated columns.")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}", exc_info=True)

    async def store_review(self, pr_event: PREvent, review: ReviewResponse) -> None:
        """
        Store a completed review in both SQLite and ChromaDB.

        Args:
            pr_event: The Pull Request event.
            review: Final review response.
        """
        # 1. Insert into SQLite
        try:
            import json
            issues_serialized = json.dumps([i.model_dump() for i in review.issues])
            suggestions_serialized = json.dumps(review.suggestions)

            async with aiosqlite.connect(self.sqlite_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO reviews (pr_id, repo, commit_sha, summary, approval, tokens_used, issues_json, suggestions_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pr_event.pr_id,
                        pr_event.repo,
                        pr_event.commit_sha,
                        review.summary,
                        str(review.approval),
                        review.tokens_used,
                        issues_serialized,
                        suggestions_serialized
                    )
                )
                await db.commit()
            logger.info(f"Stored review for {pr_event.repo} PR {pr_event.pr_id} in SQLite.")
        except Exception as e:
            logger.error(f"Failed to store review in SQLite for PR {pr_event.pr_id}: {e}", exc_info=True)

        # 2. Embed review summary and store in ChromaDB
        try:
            chunk = self._build_review_chunk(pr_event, review)
            await asyncio.to_thread(self.vector_store.add_documents, "pr_examples", [chunk])
            logger.info(f"Stored review summary in ChromaDB 'pr_examples' collection for PR {pr_event.pr_id}.")
        except Exception as e:
            logger.error(f"Failed to store review in ChromaDB for PR {pr_event.pr_id}: {e}", exc_info=True)

    async def get_similar_reviews(self, diff_query: str, n: int = 3) -> List[Dict]:
        """
        Query ChromaDB 'pr_examples' for similar past PR reviews.

        Args:
            diff_query: Keyword diff summary search string.
            n: Number of similar reviews to return.

        Returns:
            List of dictionaries representing matched reviews.
        """
        try:
            chunks = await asyncio.to_thread(self.vector_store.query, "pr_examples", diff_query, n)
            results = []
            for chunk in chunks:
                results.append({
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "metadata": chunk.metadata
                })
            return results
        except Exception as e:
            logger.error(f"Failed to query similar reviews from ChromaDB: {e}", exc_info=True)
            return []

    async def get_review_history(self, repo: str, limit: int = 20) -> List[Dict]:
        """
        Query SQLite for recent reviews by repository name.

        Args:
            repo: Repo name (e.g. 'owner/repo').
            limit: Maximum count of reviews.

        Returns:
            List of dictionaries containing review history metadata.
        """
        try:
            async with aiosqlite.connect(self.sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT pr_id, repo, commit_sha, summary, approval, tokens_used, issues_json, suggestions_json, created_at
                    FROM reviews
                    WHERE repo = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (repo, limit)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to retrieve review history for repo {repo}: {e}", exc_info=True)
            return []

    def _build_review_chunk(self, pr_event: PREvent, review: ReviewResponse) -> DocChunk:
        """
        Build a DocChunk object representing a pull request review.

        Args:
            pr_event: The Pull Request event.
            review: Final review response.

        Returns:
            A DocChunk model representing the review.
        """
        content = (
            f"PR Title: {pr_event.title}\n"
            f"PR Author: {pr_event.author}\n"
            f"Review Summary: {review.summary}\n"
            f"Approval Status: {review.approval}"
        )
        chunk_id = f"rev_{pr_event.repo.replace('/', '_')}_{pr_event.pr_id}"
        return DocChunk(
            chunk_id=chunk_id,
            content=content,
            source_type=SourceType.PR_EXAMPLE,
            metadata={
                "pr_id": str(pr_event.pr_id),
                "repo": pr_event.repo,
                "commit_sha": pr_event.commit_sha
            }
        )
