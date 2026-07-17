import json
import os
from typing import Any, Dict, List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import structlog

from src.resilience.retry import with_retry
from src.resilience.timeout import with_timeout

logger = structlog.get_logger()


class PolicyStore:
    """Manages system policies and performs semantic keyword searches using TF-IDF."""
    def __init__(self, filepath: Optional[str] = None) -> None:
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "policies.json")
        self.filepath = filepath
        self.policies: List[Dict[str, Any]] = []
        self._load_policies()
        
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix: Any = None
        self._fit_vectorizer()

    def _load_policies(self) -> None:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.policies = json.load(f)
            logger.info("Loaded system policies successfully", path=self.filepath, count=len(self.policies))
        except Exception as e:
            logger.error("Failed to load policies.json", path=self.filepath, error=str(e))
            self.policies = []

    def _fit_vectorizer(self) -> None:
        if not self.policies:
            return
        corpus = []
        for p in self.policies:
            # Combine content, title, and keywords to create a rich text representations for indexing
            text = f"{p['title']} {p['content']} {' '.join(p['keywords'])} {p['category']}"
            corpus.append(text)
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a policy by its ID."""
        for p in self.policies:
            if p["id"] == policy_id:
                return p
        return None

    @with_retry(max_attempts=3)
    async def search_policy(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Searches policies matching the query using TF-IDF cosine similarity.
        Wrapped with timeout and retry mechanisms.
        """
        async def _execute() -> List[Dict[str, Any]]:
            if not self.policies or self.tfidf_matrix is None:
                return []
            
            # Compute TF-IDF similarities
            query_vec = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            
            results = []
            for idx, score in enumerate(similarities):
                if score > 0.0:
                    policy = self.policies[idx].copy()
                    policy["score"] = float(score)
                    results.append(policy)
            
            # Sort results by similarity score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        return await with_timeout(_execute(), 5.0, f"search_policy: {query[:20]}")
