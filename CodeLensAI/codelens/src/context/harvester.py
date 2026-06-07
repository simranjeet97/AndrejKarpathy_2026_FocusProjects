import os
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional
from ..models import PREvent, DocChunk, JiraTicket, FileDiff
from ..memory.vector_store import VectorStore
from ..github.client import GitHubClient
from ..config.settings import Settings

logger = logging.getLogger(__name__)

@dataclass
class RawContextBundle:
    """A collection of raw contexts harvested for a PR review."""
    diff_chunks: List[FileDiff]
    arch_chunks: List[DocChunk]
    standard_chunks: List[DocChunk]
    pr_example_chunks: List[DocChunk]
    jira_ticket: Optional[JiraTicket]

class ContextHarvester:
    """Orchestrates raw context collection for a Pull Request from multiple sources."""

    def __init__(self, vector_store: VectorStore, github_client: GitHubClient, settings: Settings) -> None:
        """
        Initialize the ContextHarvester.

        Args:
            vector_store: Instantiated vector database store.
            github_client: GitHub API wrapper client.
            settings: Configuration settings.
        """
        self.vector_store = vector_store
        self.github_client = github_client
        self.settings = settings

    async def collect(self, pr_event: PREvent) -> RawContextBundle:
        """
        Collect and bundle all raw contexts (diffs, arch docs, coding standards, PR examples, Jira) for the PR.

        Args:
            pr_event: The pull request event model.

        Returns:
            A RawContextBundle containing all fetched contexts.
        """
        diff_query = await asyncio.to_thread(self._build_diff_query, pr_event)
        changed_paths = [f.path for f in pr_event.changed_files]
        
        # Define tasks for concurrent execution in thread pool since Chroma/Pandas calls are synchronous
        arch_task = asyncio.to_thread(self._fetch_arch_docs, changed_paths)
        std_task = asyncio.to_thread(self._fetch_standards, changed_paths)
        pr_task = asyncio.to_thread(self._fetch_similar_prs, diff_query)
        
        jira_task = None
        if pr_event.jira_ticket_id:
            jira_task = asyncio.to_thread(self._fetch_jira_context, pr_event.jira_ticket_id)
            
        if jira_task:
            arch_chunks, std_chunks, pr_chunks, jira_ticket = await asyncio.gather(
                arch_task, std_task, pr_task, jira_task
            )
        else:
            arch_chunks, std_chunks, pr_chunks = await asyncio.gather(
                arch_task, std_task, pr_task
            )
            jira_ticket = None
            
        return RawContextBundle(
            diff_chunks=pr_event.changed_files,
            arch_chunks=arch_chunks,
            standard_chunks=std_chunks,
            pr_example_chunks=pr_chunks,
            jira_ticket=jira_ticket
        )

    def _fetch_jira_context(self, ticket_id: str) -> Optional[JiraTicket]:
        """
        Retrieve context/metadata from Jira for the given ticket ID.

        Args:
            ticket_id: Jira issue identifier.

        Returns:
            A JiraTicket object, or None if not found or configured.
        """
        if not ticket_id:
            return None
            
        import pandas as pd
        excel_dir = self.settings.EXCEL_PATH
        if not os.path.exists(excel_dir):
            logger.warning(f"Jira Excel directory not found: {excel_dir}")
            return None
            
        excel_files = [f for f in os.listdir(excel_dir) if f.endswith((".xlsx", ".xls"))]
        if not excel_files:
            logger.warning(f"No Excel files found in {excel_dir} for Jira ticket lookup.")
            return None
            
        for file in excel_files:
            file_path = os.path.join(excel_dir, file)
            try:
                df = pd.read_excel(file_path)
                if "ticket_id" in df.columns:
                    # Case insensitive lookup or string strip to make it robust
                    df["ticket_id_str"] = df["ticket_id"].astype(str).str.strip()
                    row = df[df["ticket_id_str"] == str(ticket_id).strip()]
                    if not row.empty:
                        record = row.iloc[0]
                        return JiraTicket(
                            id=ticket_id,
                            summary=str(record.get("summary", "")),
                            description=str(record.get("description", "")) if pd.notna(record.get("description")) else None,
                            issue_type=str(record.get("issue_type", "Story")),
                            status=str(record.get("status", "Open"))
                        )
            except Exception as e:
                logger.error(f"Error reading Excel file {file_path}: {e}")
                
        return None

    def _fetch_arch_docs(self, changed_paths: List[str]) -> List[DocChunk]:
        """
        Query vector database for architectural documents relevant to changed file paths.

        Args:
            changed_paths: List of relative paths modified in the PR.

        Returns:
            List of matching architecture DocChunks.
        """
        query_terms = []
        for path in changed_paths:
            clean_path = path.replace("/", " ").replace("\\", " ")
            clean_path = os.path.splitext(clean_path)[0]
            query_terms.append(clean_path)
            
        query_text = " ".join(query_terms)[:500]
        if not query_text.strip():
            return []
            
        try:
            return self.vector_store.query("arch_docs", query_text, n_results=5)
        except Exception as e:
            logger.error(f"Error querying arch_docs collection: {e}")
            return []

    def _fetch_standards(self, changed_paths: List[str]) -> List[DocChunk]:
        """
        Query vector database for coding standards/guidelines relevant to changed file paths.

        Args:
            changed_paths: List of relative paths modified in the PR.

        Returns:
            List of matching standard DocChunks.
        """
        query_terms = []
        for path in changed_paths:
            clean_path = path.replace("/", " ").replace("\\", " ")
            clean_path = os.path.splitext(clean_path)[0]
            query_terms.append(clean_path)
            
        query_text = " ".join(query_terms)[:500]
        if not query_text.strip():
            return []
            
        try:
            return self.vector_store.query("standards", query_text, n_results=5)
        except Exception as e:
            logger.error(f"Error querying standards collection: {e}")
            return []

    def _fetch_similar_prs(self, diff_summary: str) -> List[DocChunk]:
        """
        Query vector database for previous pull requests or PR examples matching this diff summary.

        Args:
            diff_summary: A text summary of keywords or changes in this PR.

        Returns:
            List of matching PR example DocChunks.
        """
        if not diff_summary.strip():
            return []
            
        try:
            return self.vector_store.query("pr_examples", diff_summary, n_results=3)
        except Exception as e:
            logger.error(f"Error querying pr_examples collection: {e}")
            return []

    def _build_diff_query(self, pr_event: PREvent) -> str:
        """
        Helper method to extract keywords or write a search query from the PR diff files.

        Args:
            pr_event: The pull request event model.

        Returns:
            A query string for semantic vector search.
        """
        keywords = []
        for f in pr_event.changed_files:
            ext = os.path.splitext(f.path)[1].replace(".", "")
            if ext and ext not in keywords:
                keywords.append(ext)
                
            if f.patch:
                for line in f.patch.split("\n"):
                    cleaned = line.lstrip("+").strip()
                    if cleaned.startswith(("def ", "class ", "func ")):
                        parts = cleaned.split()
                        if len(parts) > 1:
                            name = parts[1].split("(")[0].split(":")[0].strip()
                            if name and name not in keywords:
                                keywords.append(name)
                                
        query_str = " ".join(keywords)
        return query_str[:200]

