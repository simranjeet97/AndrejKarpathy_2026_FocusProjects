import json
import re
import asyncio
from typing import Any, Union, Optional
import httpx

class OllamaError(Exception):
    """Exception raised for errors during Ollama API operations."""
    pass

class OllamaClient:
    """Async client for Ollama local inference service."""

    def __init__(self, base_url: str, agent_model: str, embed_model: str):
        self.base_url = str(base_url).rstrip("/")
        self.agent_model = agent_model
        self.embed_model = embed_model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        """Close the underlying HTTP client session."""
        await self.client.aclose()

    async def generate(self, prompt: str, system: Optional[str] = None, expect_json: bool = False) -> Union[str, dict]:
        """Send a prompt to Ollama's /api/generate endpoint."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.agent_model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if expect_json:
            payload["format"] = "json"

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "")
            
            if expect_json:
                return self._extract_json(response_text)
            return response_text
        except Exception as e:
            raise OllamaError(f"Ollama generate request failed: {e}") from e

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Fetch embeddings for a list of texts. Batches requests in groups of 20."""
        if not texts:
            return []

        url = f"{self.base_url}/api/embeddings"
        
        async def embed_single(text: str) -> list[float]:
            payload = {
                "model": self.embed_model,
                "prompt": text,
            }
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if "embedding" not in data:
                raise OllamaError("Response did not contain 'embedding' key")
            return data["embedding"]

        embeddings = []
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                # Process the batch concurrently
                batch_results = await asyncio.gather(*(embed_single(text) for text in batch))
                embeddings.extend(batch_results)
            except Exception as e:
                raise OllamaError(f"Ollama embedding request failed for batch: {e}") from e

        return embeddings

    async def chat(self, messages: list[dict]) -> str:
        """Send a list of messages (chat history) to Ollama's /api/chat endpoint."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.agent_model,
            "messages": messages,
            "stream": False,
        }

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            return message.get("content", "")
        except Exception as e:
            raise OllamaError(f"Ollama chat request failed: {e}") from e

    async def health_check(self) -> bool:
        """Check if the Ollama service is reachable and running."""
        try:
            response = await self.client.get(f"{self.base_url}/")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List the model names available on the Ollama service."""
        url = f"{self.base_url}/api/tags"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            return [m["name"] for m in models]
        except Exception as e:
            raise OllamaError(f"Failed to list Ollama models: {e}") from e

    def _extract_json(self, text: str) -> dict:
        """Extract and parse JSON from response text, handling raw and fenced JSON."""
        cleaned_text = text.strip()
        pattern = r"^```(?:json)?\s*(.*?)\s*```$"
        match = re.match(pattern, cleaned_text, re.DOTALL | re.IGNORECASE)
        content = match.group(1) if match else cleaned_text
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise OllamaError(f"Failed to parse JSON response: {content}") from e
