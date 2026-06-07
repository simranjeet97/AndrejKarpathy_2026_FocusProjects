import json
import httpx
from typing import List, Dict, Optional, Any, AsyncIterator

class OllamaError(Exception):
    """Custom exception raised by the OllamaClient."""
    pass

class OllamaClient:
    """Client for interacting with the Ollama LLM APIs."""

    def __init__(self, base_url: str, model_code: str, model_reason: str, embed_model: str) -> None:
        """
        Initialize the Ollama Client.

        Args:
            base_url: Base URL of the Ollama server.
            model_code: Model name for code/generation tasks.
            model_reason: Model name for reasoning tasks.
            embed_model: Model name for embeddings.
        """
        self.base_url = base_url.rstrip("/")
        self.model_code = model_code
        self.model_reason = model_reason
        self.embed_model = embed_model
        # Use a persistent httpx sync client for non-streaming requests
        self.client = httpx.Client(timeout=60.0)

    def generate(self, prompt: str, model: str = None, expect_json: bool = True) -> dict:
        """
        Generate a response for a prompt.

        Args:
            prompt: Text prompt to send to the model.
            model: Optional model override.
            expect_json: If True, parses the response as JSON.

        Returns:
            A dictionary containing the response or parsed JSON.
        """
        model_name = model or self.model_code
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
        if expect_json:
            payload["format"] = "json"

        try:
            response = self.client.post(url, json=payload)
            if response.status_code != 200:
                raise OllamaError(f"Ollama generate failed with status {response.status_code}: {response.text}")
            
            data = response.json()
            response_text = data.get("response", "")

            if expect_json:
                cleaned_text = response_text.strip()
                # Strip markdown fences if present
                if cleaned_text.startswith("```"):
                    lines = cleaned_text.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned_text = "\n".join(lines).strip()
                
                try:
                    return json.loads(cleaned_text)
                except json.JSONDecodeError as je:
                    raise OllamaError(f"Failed to parse JSON response from Ollama: {cleaned_text}") from je
            else:
                return {"response": response_text}

        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error during Ollama generate: {e}") from e
        except Exception as e:
            if not isinstance(e, OllamaError):
                raise OllamaError(f"Unexpected error during Ollama generate: {e}") from e
            raise

    async def generate_stream(self, prompt: str) -> AsyncIterator[str]:
        """
        Stream generation response chunks asynchronously.

        Args:
            prompt: Text prompt to send to the model.

        Yields:
            Text tokens as they arrive.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_code,
            "prompt": prompt,
            "stream": True
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as async_client:
                async with async_client.stream("POST", url, json=payload) as r:
                    if r.status_code != 200:
                        raise OllamaError(f"Ollama stream failed with status {r.status_code}")
                    async for line in r.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                continue
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error during Ollama streaming: {e}") from e

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts, batching in sizes of 20.

        Args:
            texts: List of text strings to embed.

        Returns:
            A list of float lists representing embeddings.
        """
        if not texts:
            return []

        url = f"{self.base_url}/api/embed"
        all_embeddings = []
        batch_size = 20

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            payload = {
                "model": self.embed_model,
                "input": batch
            }
            try:
                response = self.client.post(url, json=payload)
                # Fallback to legacy endpoint if /api/embed is not found (404) or allowed (405)
                if response.status_code in [404, 405]:
                    batch_embeddings = []
                    for text in batch:
                        legacy_url = f"{self.base_url}/api/embeddings"
                        legacy_payload = {
                            "model": self.embed_model,
                            "prompt": text
                        }
                        legacy_resp = self.client.post(legacy_url, json=legacy_payload)
                        if legacy_resp.status_code != 200:
                            raise OllamaError(f"Legacy embeddings failed with status {legacy_resp.status_code}: {legacy_resp.text}")
                        batch_embeddings.append(legacy_resp.json().get("embedding", []))
                    all_embeddings.extend(batch_embeddings)
                    continue
                elif response.status_code != 200:
                    raise OllamaError(f"Ollama embed failed with status {response.status_code}: {response.text}")
                
                data = response.json()
                embeddings = data.get("embeddings", [])
                if not embeddings:
                    raise OllamaError(f"No embeddings returned from Ollama for batch: {batch}")
                all_embeddings.extend(embeddings)

            except httpx.HTTPError as e:
                raise OllamaError(f"HTTP error during Ollama embed: {e}") from e

        return all_embeddings

    def health_check(self) -> bool:
        """
        Check if the Ollama server is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        url = f"{self.base_url}/api/tags"
        try:
            response = self.client.get(url, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
