import os
import math
import heapq
import logging
import numpy as np
import tiktoken
from rank_bm25 import BM25Okapi
from typing import List, Dict, Optional, Any
from ..models import PREvent, DocChunk, ScoredChunk, ContextPack, FileDiff
from .harvester import RawContextBundle
from ..config.settings import Settings

logger = logging.getLogger(__name__)

class ContextRanker:
    """Core intelligence layer that scores, ranks, compresses and fills the PR context pack under a token budget."""

    def __init__(self, ollama_client: Any, settings: Settings) -> None:
        """
        Initialize the ContextRanker.

        Args:
            ollama_client: Client for Ollama LLM interactions.
            settings: Configuration settings.
        """
        self.ollama_client = ollama_client
        self.settings = settings

    def rank_and_compress(self, bundle: RawContextBundle, pr_event: PREvent, budget: int) -> ContextPack:
        """
        Rank the raw contexts and compress low-score chunks to fit the token budget.

        Args:
            bundle: The raw contexts harvested.
            pr_event: The pull request event details.
            budget: Maximum allowed tokens for the context pack.

        Returns:
            A ContextPack matching the budget constraints.
        """
        diff_query = self._build_diff_query(pr_event)
        query = f"{pr_event.title} {diff_query}"
        
        # Combine all DocChunk collections from bundle
        all_chunks = bundle.arch_chunks + bundle.standard_chunks + bundle.pr_example_chunks
        
        # Score chunks
        scored_chunks = self._score_chunks(all_chunks, query)
        
        # Compress chunks with final_score < 0.3
        processed_chunks = []
        for chunk in scored_chunks:
            if chunk.final_score < 0.3:
                processed_chunk = self._compress_chunk(chunk)
            else:
                processed_chunk = chunk
            processed_chunks.append(processed_chunk)
            
        # Greedy fill under budget
        selected_chunks = self._greedy_fill(processed_chunks, budget)
        
        # Calculate totals
        total_tokens = sum(c.token_count for c in selected_chunks)
        budget_used = int((total_tokens / budget) * 100) if budget > 0 else 0
        
        return ContextPack(
            pr_id=pr_event.pr_id,
            chunks=selected_chunks,
            total_tokens=total_tokens,
            budget_used=budget_used
        )

    def _score_chunks(self, chunks: List[DocChunk], query: str) -> List[ScoredChunk]:
        """
        Score and sort chunks based on BM25 and semantic embedding scores.

        Args:
            chunks: A list of DocChunks.
            query: The search query.

        Returns:
            A list of ScoredChunk models.
        """
        if not chunks:
            return []
            
        bm25_scores = self._bm25_score(query, chunks)
        semantic_scores = self._semantic_score(query, chunks)
        
        scored_chunks = []
        for c in chunks:
            bm25_val = bm25_scores.get(c.chunk_id, 0.0)
            semantic_val = semantic_scores.get(c.chunk_id, 0.0)
            token_cnt = self._estimate_tokens(c.content)
            
            scored_chunk = ScoredChunk(
                chunk_id=c.chunk_id,
                content=c.content,
                source_type=c.source_type,
                metadata=c.metadata,
                bm25_score=bm25_val,
                semantic_score=semantic_val,
                token_count=token_cnt
            )
            scored_chunks.append(scored_chunk)
            
        scored_chunks.sort(key=lambda x: x.final_score, reverse=True)
        return scored_chunks

    def _bm25_score(self, query: str, chunks: List[DocChunk]) -> Dict[str, float]:
        """
        Calculate BM25 relevance scores for all chunks against the query.

        Args:
            query: The search query string.
            chunks: A list of DocChunks.

        Returns:
            A dictionary mapping chunk_id to BM25 score.
        """
        if not chunks:
            return {}
        
        corpus = [c.content.lower().split() for c in chunks]
        tokenized_query = query.lower().split()
        
        bm25 = BM25Okapi(corpus)
        doc_scores = bm25.get_scores(tokenized_query)
        
        max_score = max(doc_scores) if len(doc_scores) > 0 else 0
        min_score = min(doc_scores) if len(doc_scores) > 0 else 0
        score_range = max_score - min_score
        
        scores = {}
        for idx, chunk in enumerate(chunks):
            raw_score = doc_scores[idx]
            if score_range > 0:
                normalized_score = (raw_score - min_score) / score_range
            else:
                normalized_score = 1.0 if max_score > 0 else 0.0
            scores[chunk.chunk_id] = normalized_score
            
        return scores

    def _semantic_score(self, query: str, chunks: List[DocChunk]) -> Dict[str, float]:
        """
        Calculate semantic embedding similarity scores for all chunks.

        Args:
            query: The search query string.
            chunks: A list of DocChunks.

        Returns:
            A dictionary mapping chunk_id to semantic similarity score.
        """
        if not chunks:
            return {}
            
        texts = [query] + [c.content for c in chunks]
        embeddings = self.ollama_client.embed(texts)
        
        query_vector = embeddings[0]
        chunk_vectors = embeddings[1:]
        
        scores = {}
        for idx, chunk in enumerate(chunks):
            arr1 = np.array(query_vector)
            arr2 = np.array(chunk_vectors[idx])
            dot = np.dot(arr1, arr2)
            norm1 = np.linalg.norm(arr1)
            norm2 = np.linalg.norm(arr2)
            similarity = float(dot / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0
            scores[chunk.chunk_id] = similarity
            
        return scores

    def _greedy_fill(self, scored: List[ScoredChunk], budget: int) -> List[ScoredChunk]:
        """
        Greedily add chunks to the context pack until the token budget is reached.

        Args:
            scored: Ranked ScoredChunks.
            budget: Total token budget.

        Returns:
            A list of selected ScoredChunks that fit within budget.
        """
        heap = []
        for idx, chunk in enumerate(scored):
            # Heapq is a min-heap by default, so negate final_score for max-heap behavior
            heapq.heappush(heap, (-chunk.final_score, idx, chunk))
            
        selected = []
        current_tokens = 0
        
        while heap:
            neg_score, _, chunk = heapq.heappop(heap)
            if current_tokens + chunk.token_count <= budget:
                selected.append(chunk)
                current_tokens += chunk.token_count
            else:
                continue
                
        return selected

    def _compress_chunk(self, chunk: ScoredChunk) -> ScoredChunk:
        """
        Summarize a low-score DocChunk using the LLM to save token space.

        Args:
            chunk: The scored chunk to compress.

        Returns:
            A new ScoredChunk with compressed text and updated token count.
        """
        if chunk.token_count <= 200:
            return chunk
            
        prompt = f"Summarize in 2 sentences:\n{chunk.content}"
        try:
            result = self.ollama_client.generate(prompt, expect_json=False)
            summary = result.get("response", "") if isinstance(result, dict) else str(result)
            if summary and summary.strip():
                new_token_count = self._estimate_tokens(summary.strip())
                return chunk.model_copy(update={
                    "content": summary.strip(),
                    "token_count": new_token_count
                })
        except Exception as e:
            logger.warning(f"Ollama compression failed for chunk {chunk.chunk_id}: {e}")
            
        return chunk

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in the given text using tiktoken.

        Args:
            text: The raw text string.

        Returns:
            The estimated token count.
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))

    def _score_file_importance(self, files: List[FileDiff]) -> Dict[str, float]:
        """
        Analyze changed file paths to determine their relative priority.

        Args:
            files: The changed file differences.

        Returns:
            A dictionary mapping file path to importance score (0.0 to 1.0).
        """
        if not files:
            return {}
            
        changes = [f.additions + f.deletions for f in files]
        max_total_changes = max(changes) if changes else 0
        
        scores = {}
        for f in files:
            total_change = f.additions + f.deletions
            if max_total_changes > 0:
                base_score = total_change / max_total_changes
            else:
                base_score = 0.0
                
            # Boost critical paths
            boost = 0.0
            path_lower = f.path.lower()
            critical_keywords = ['auth', 'security', 'payment', 'core']
            for kw in critical_keywords:
                if kw in path_lower:
                    boost = 0.3
                    break
                    
            final_score = min(max(base_score + boost, 0.0), 1.0)
            scores[f.path] = final_score
            
        return scores

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

