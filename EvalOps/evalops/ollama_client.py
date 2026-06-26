import aiohttp
import time
from typing import Optional, Dict, Any, List
from evalops.config import get_settings

class OllamaError(Exception):
    """Custom exception raised for Ollama API interaction failures."""
    pass

class OllamaClient:
    """
    Asynchronous client wrapper for local Ollama API service.
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=120)

    async def health_check(self) -> bool:
        """
        Check if the Ollama service is running and accessible.

        Returns:
            bool: True if healthy, False otherwise.
        """
        url = f"{self.base_url}/api/tags"
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """
        List all models currently installed locally in Ollama.

        Returns:
            List[str]: List of model names.
        
        Raises:
            OllamaError: If API call fails.
        """
        url = f"{self.base_url}/api/tags"
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise OllamaError(f"HTTP error {response.status} listing models")
                    data = await response.json()
                    models = data.get("models", [])
                    return [m["name"] for m in models]
        except aiohttp.ClientError as e:
            raise OllamaError(f"Connection failure listing models: {e}")
        except Exception as e:
            if not isinstance(e, OllamaError):
                raise OllamaError(f"Unexpected error listing models: {e}")
            raise

    async def generate(
        self, model: str, prompt: str, system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate text completion for a given prompt using a specified model.

        Args:
            model (str): Name of the model.
            prompt (str): Prompt text.
            system_prompt (str, optional): System instructions.

        Returns:
            Dict[str, Any]: Contains keys: 'text', 'tokens_used', 'latency_ms'.
        
        Raises:
            OllamaError: If generation fails.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.time()
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise OllamaError(f"HTTP error {response.status}: {text}")
                    
                    data = await response.json()
                    response_text = data.get("response", "")
                    
                    # Token counts
                    prompt_tokens = data.get("prompt_eval_count", 0)
                    eval_tokens = data.get("eval_count", 0)
                    tokens_used = prompt_tokens + eval_tokens
                    
                    # Latency tracking (Ollama returns total_duration in nanoseconds)
                    total_duration_ns = data.get("total_duration")
                    if total_duration_ns:
                        latency_ms = total_duration_ns / 1_000_000.0
                    else:
                        latency_ms = (time.time() - start_time) * 1000.0

                    return {
                        "text": response_text,
                        "tokens_used": tokens_used,
                        "latency_ms": latency_ms
                    }
        except aiohttp.ClientError as e:
            raise OllamaError(f"Connection failure during generation: {e}")
        except Exception as e:
            if not isinstance(e, OllamaError):
                raise OllamaError(f"Unexpected error during generation: {e}")
            raise
