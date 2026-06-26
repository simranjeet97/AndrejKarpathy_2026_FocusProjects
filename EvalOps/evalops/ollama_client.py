import aiohttp
import time
import os
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
        self.mock_mode = os.getenv("MOCK_OLLAMA", "false").lower() == "true"

    async def health_check(self) -> bool:
        """
        Check if the Ollama service is running and accessible.

        Returns:
            bool: True if healthy, False otherwise.
        """
        if self.mock_mode:
            return True

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
        if self.mock_mode:
            return ["llama3", "mistral", "phi3"]

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
        if self.mock_mode:
            # Deterministic mock responses
            if system_prompt and "evaluator" in system_prompt.lower():
                # LLM Judge scoring mock
                if "amelia thorne" in prompt.lower() and "flux-capacitor" in prompt.lower():
                    # If model didn't refuse, trigger hallucination detect
                    if "1985" in prompt or "invented" in prompt:
                        response_text = '{"score": 0.0, "reason": "Model hallucinated fake historical fact.", "hallucination": true}'
                    else:
                        response_text = '{"score": 1.0, "reason": "Model correctly refused the fictional prompt.", "hallucination": false}'
                else:
                    response_text = '{"score": 0.9, "reason": "Output is correct and matches expected results.", "hallucination": false}'
            elif system_prompt and "compare" in system_prompt.lower():
                # Pairwise comparator mock
                response_text = '{"winner": "A", "reason": "Output A is better structured."}'
            else:
                # Regular mock task completions
                prompt_lower = prompt.lower()
                if "speed of light" in prompt_lower:
                    response_text = "The speed of light in a vacuum is approximately 299,792,458 meters per second."
                elif "factorial" in prompt_lower:
                    response_text = "def factorial(n):\n    if n == 0 or n == 1:\n        return 1\n    return n * factorial(n - 1)"
                elif "colors" in prompt_lower:
                    response_text = "- RED\n- GREEN\n- BLUE"
                elif "amelia thorne" in prompt_lower:
                    # Hallucination trap expect refusal
                    response_text = "I don't know. Dr. Amelia Thorne is a fictional character, so no such invention exists."
                else:
                    response_text = f"Mock completion for model '{model}' prompt: '{prompt[:40]}'"
            
            return {
                "text": response_text,
                "tokens_used": 120,
                "latency_ms": 15.0
            }

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
