import time
from typing import Any, Dict, List, Optional
import httpx
import structlog
from pydantic import BaseModel

from src.config import settings
from src.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
from src.resilience.retry import with_retry, RateLimitError
from src.observability.tracing import llm_call_span

logger = structlog.get_logger()


class SafeResponse(BaseModel):
    message: str
    escalate: bool = True


async def call_anthropic_api(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper method to make HTTP requests to Anthropic Messages API."""
    from src.policy.pii_scrubber import scrub_messages, scrub
    
    # Scrub incoming messages before transmitting to external provider
    scrubbed_messages = scrub_messages(messages)
    
    api_key = settings.ANTHROPIC_API_KEY.get_secret_value()
    
    # Fast path: simulation if key is a mock key
    if api_key.startswith("mock-"):
        # Simulate network failure or timeout for testing fallback
        if "fail" in model or "sonnet" in model:
            raise httpx.ConnectError("Failed to connect to simulated provider")
            
        raw_text = f"Simulated response from {model}"
        scrubbed_response = scrub(raw_text).scrubbed_text
        return {
            "content": [{"type": "text", "text": scrubbed_response}],
            "model": model,
        }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": scrubbed_messages,
        "max_tokens": 1024,
    }
    if tools:
        payload["tools"] = tools
    if system_prompt:
        payload["system"] = system_prompt

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=settings.TIMEOUT_SECONDS,
        )
        if response.status_code == 429:
            raise RateLimitError("Anthropic API rate limit exceeded")
        response.raise_for_status()
        
        result = response.json()
        # Scrub assistant output text block content
        if "content" in result:
            for block in result["content"]:
                if block.get("type") == "text" and "text" in block:
                    block["text"] = scrub(block["text"]).scrubbed_text
                    
        return result


async def call_with_fallback(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    system_prompt: Optional[str] = None,
    redis_client: Optional[Any] = None,
) -> Any:
    """
    Tries PRIMARY_MODEL first. On failure, logs metrics and falls back to FALLBACK_MODEL.
    On subsequent failure, returns a SafeResponse warning the user and escalating.
    """
    # Fallback to local memory if redis_client isn't passed (useful for tests)
    import redis.asyncio as aioredis
    if redis_client is None:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    # Initialize Circuit Breakers for both paths
    primary_cb = CircuitBreaker(
        redis_client=redis_client,
        service_name=f"llm:{settings.PRIMARY_MODEL}",
        failure_threshold=settings.CIRCUIT_BREAKER_THRESHOLD,
    )
    fallback_cb = CircuitBreaker(
        redis_client=redis_client,
        service_name=f"llm:{settings.FALLBACK_MODEL}",
        failure_threshold=settings.CIRCUIT_BREAKER_THRESHOLD,
    )

    start_time = time.time()
    
    # 1. Try Primary Model
    try:
        # Wrap API call with retry mechanism
        @with_retry(
            max_attempts=settings.MAX_RETRIES,
            base_delay=settings.RETRY_BASE_DELAY,
        )
        async def primary_call_with_retry() -> Dict[str, Any]:
            async with llm_call_span(model=settings.PRIMARY_MODEL, fallback_used=False):
                return await call_anthropic_api(
                    model=settings.PRIMARY_MODEL,
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                )

        return await primary_cb.call(primary_call_with_retry())

    except Exception as primary_error:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warn(
            "Primary LLM failed, initiating fallback",
            from_model=settings.PRIMARY_MODEL,
            to_model=settings.FALLBACK_MODEL,
            reason=str(primary_error),
            latency_ms=latency_ms,
        )

        fallback_start_time = time.time()
        
        # 2. Try Fallback Model
        try:
            @with_retry(
                max_attempts=settings.MAX_RETRIES,
                base_delay=settings.RETRY_BASE_DELAY,
            )
            async def fallback_call_with_retry() -> Dict[str, Any]:
                async with llm_call_span(model=settings.FALLBACK_MODEL, fallback_used=True):
                    return await call_anthropic_api(
                        model=settings.FALLBACK_MODEL,
                        messages=messages,
                        tools=tools,
                        system_prompt=system_prompt,
                    )

            return await fallback_cb.call(fallback_call_with_retry())

        except Exception as fallback_error:
            fallback_latency_ms = int((time.time() - fallback_start_time) * 1000)
            logger.error(
                "Fallback LLM failed, escalating to human agent",
                from_model=settings.FALLBACK_MODEL,
                to_model="SafeResponse",
                reason=str(fallback_error),
                latency_ms=fallback_latency_ms,
            )
            
            # Return canned response
            return SafeResponse(
                message="I'm unable to process your request right now. A human agent will follow up within 2 hours.",
                escalate=True,
            )
