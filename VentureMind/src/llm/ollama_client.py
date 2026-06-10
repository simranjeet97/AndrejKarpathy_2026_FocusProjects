import asyncio
import json
import re
import httpx

class OllamaError(Exception):
    """Exception raised when an error occurs during an Ollama API call."""
    pass

def clean_json_text(text: str) -> str:
    """Clean markdown code fences from JSON strings if present."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

class OllamaClient:
    """Async client wrapper for interacting with the local Ollama LLM service."""

    def __init__(
        self,
        base_url: str,
        orchestrator_model: str,
        analyst_model: str,
        summary_model: str,
        embed_model: str,
    ):
        self.base_url = str(base_url).rstrip("/")
        self._orchestrator_model = orchestrator_model
        self._analyst_model = analyst_model
        self._summary_model = summary_model
        self._embed_model = embed_model

    @property
    def orchestrator_model(self) -> str:
        """Name of the model reserved for orchestrator tasks."""
        return self._orchestrator_model

    @property
    def analyst_model(self) -> str:
        """Name of the model reserved for analyst tasks."""
        return self._analyst_model

    @property
    def summary_model(self) -> str:
        """Name of the model reserved for summarization tasks."""
        return self._summary_model

    async def generate(
        self,
        prompt: str,
        model: str = None,
        system: str = None,
        expect_json: bool = False,
    ) -> str | dict:
        """Generate a text completion response using the Ollama server."""
        target_model = model or self._orchestrator_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if expect_json:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                response_text = result.get("response", "")

                if expect_json:
                    cleaned_text = clean_json_text(response_text)
                    try:
                        return json.loads(cleaned_text)
                    except json.JSONDecodeError as e:
                        raise OllamaError(
                            f"Ollama returned invalid JSON: {response_text}"
                        ) from e

                return response_text
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama generation request failed: {e}") from e

    async def chat(self, messages: list[dict], model: str = None) -> str:
        """Generate a chat conversation response using the Ollama server."""
        target_model = model or self._orchestrator_model
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return result.get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama chat request failed: {e}") from e

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of strings, batching at 20 concurrent requests."""
        if not texts:
            return []

        results = []
        for i in range(0, len(texts), 20):
            batch = texts[i : i + 20]
            tasks = [self._get_embedding(text) for text in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        return results

    async def _get_embedding(self, text: str) -> list[float]:
        """Fetch the embedding vector for a single prompt."""
        payload = {
            "model": self._embed_model,
            "prompt": text,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                if "embedding" not in result:
                    raise OllamaError("Response did not contain an embedding field.")
                return result["embedding"]
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama embedding request failed: {e}") from e

    async def health_check(self) -> bool:
        """Perform a quick health check to verify if the Ollama server is running."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url)
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[str]:
        """Retrieve a list of all models downloaded locally on the Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                result = response.json()
                models = result.get("models", [])
                return [m["name"] for m in models]
        except httpx.HTTPError as e:
            raise OllamaError(f"Ollama list models failed: {e}") from e
