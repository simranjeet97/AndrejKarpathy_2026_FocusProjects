import asyncio
import json
import logging
import re
import httpx

logger = logging.getLogger("VentureMind.OllamaClient")

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
    """Async client wrapper for interacting with the local Ollama LLM service.
    
    Supports sharing a single httpx.AsyncClient instance across requests, 
    connection pooling, exponential retries, and lifecycle hooks.
    """

    def __init__(
        self,
        base_url: str,
        orchestrator_model: str,
        analyst_model: str,
        summary_model: str,
        embed_model: str,
        timeout: float = 180.0,
    ):
        self.base_url = str(base_url).rstrip("/")
        self._orchestrator_model = orchestrator_model
        self._analyst_model = analyst_model
        self._summary_model = summary_model
        self._embed_model = embed_model
        self.timeout = timeout
        self._client = None

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

    @property
    def embed_model(self) -> str:
        """Name of the model reserved for embeddings."""
        return self._embed_model

    async def get_client(self) -> httpx.AsyncClient:
        """Retrieve or initialize the shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            # We configure a pool size suitable for concurrent operations
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
            self._client = httpx.AsyncClient(timeout=self.timeout, limits=limits)
        return self._client

    async def close(self):
        """Close the shared async HTTP client if initialized."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        await self.get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with exponential backoff retry for transient errors."""
        max_attempts = 3
        delay = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                client = await self.get_client()
                if method.upper() == "GET":
                    response = await client.get(url, **kwargs)
                elif method.upper() == "POST":
                    response = await client.post(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Raise exception for 5xx server errors or 429 rate limit to trigger retries
                if response.status_code >= 500 or response.status_code == 429:
                    response.raise_for_status()
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                # If we've reached max attempts, or if it is a 4xx error that is not 429, fail immediately
                if attempt == max_attempts:
                    raise
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                logger.warning(
                    f"Ollama request failed (attempt {attempt}/{max_attempts}): {e}. "
                    f"Retrying in {delay} seconds..."
                )
                await asyncio.sleep(delay)
                delay *= 2

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
            response = await self._request_with_retry(
                "POST",
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
            response = await self._request_with_retry(
                "POST",
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
            response = await self._request_with_retry(
                "POST",
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
            client = await self.get_client()
            response = await client.get(self.base_url, timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Retrieve a list of all models downloaded locally on the Ollama instance."""
        try:
            client = await self.get_client()
            response = await client.get(f"{self.base_url}/api/tags", timeout=10.0)
            response.raise_for_status()
            result = response.json()
            models = result.get("models", [])
            return [m["name"] for m in models]
        except Exception as e:
            raise OllamaError(f"Ollama list models failed: {e}") from e

    async def ensure_model_available(self, model: str) -> None:
        """Verify if a model is available. If not, attempt to pull it. Raises OllamaError on failure."""
        try:
            available = await self.list_models()
        except Exception as e:
            raise OllamaError(f"Failed to list available models: {e}")

        # Check for both exact match and match with/without tag (e.g. qwen2.5:7b vs qwen2.5:7b:latest)
        norm_model = model if ":" in model else f"{model}:latest"
        available_norm = [m if ":" in m else f"{m}:latest" for m in available]

        if norm_model not in available_norm and model not in available:
            logger.info(f"Model '{model}' not found locally. Attempting to pull from Ollama registry...")
            try:
                client = await self.get_client()
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model, "stream": False},
                    timeout=600.0, # Pulling can take several minutes
                )
                response.raise_for_status()
                logger.info(f"Successfully pulled model '{model}'.")
            except Exception as e:
                raise OllamaError(
                    f"Model '{model}' is not available and auto-pull failed: {e}. "
                    f"Please run `ollama pull {model}` manually."
                ) from e

