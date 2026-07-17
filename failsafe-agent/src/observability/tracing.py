import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional

from opentelemetry import context, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import NonRecordingSpan, SpanContext, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

import structlog

logger = structlog.get_logger()

# --------------------------------------------------------------------------- #
#  Singleton TracerProvider                                                    #
# --------------------------------------------------------------------------- #

_tracer_provider: Optional[TracerProvider] = None
_tracer: Optional[Tracer] = None


def _build_provider() -> TracerProvider:
    resource = Resource.create(
        {
            "service.name": "failsafe-agent",
            "service.version": "0.1.0",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    # Register as the global provider so otel context propagation works
    trace.set_tracer_provider(provider)
    return provider


def get_tracer() -> Tracer:
    """Returns the singleton Tracer instance, configuring the provider on first call."""
    global _tracer_provider, _tracer
    if _tracer is None:
        _tracer_provider = _build_provider()
        _tracer = _tracer_provider.get_tracer("failsafe-agent")
    return _tracer


# --------------------------------------------------------------------------- #
#  Root span: conversation                                                     #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def conversation_span(
    conversation_id: str,
    customer_id: str,
) -> AsyncGenerator[trace.Span, None]:
    """
    Root span that wraps a full conversation. Tool spans started inside this
    context manager will be recorded as children automatically via OTel context.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("conversation") as span:
        span.set_attribute("conversation.id", conversation_id)
        span.set_attribute("conversation.customer_id", customer_id)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise
        finally:
            # Caller sets final attributes on span before it closes
            pass


def set_conversation_outcome(
    span: trace.Span,
    intent: Optional[str],
    resolved: bool,
    escalated: bool,
    total_tool_calls: int,
) -> None:
    """Stamps outcome attributes onto an already-open conversation span."""
    if intent:
        span.set_attribute("conversation.intent", intent)
    span.set_attribute("conversation.resolved", resolved)
    span.set_attribute("conversation.escalated", escalated)
    span.set_attribute("conversation.total_tool_calls", total_tool_calls)
    status = trace.StatusCode.OK if resolved else trace.StatusCode.ERROR
    span.set_status(status)


# --------------------------------------------------------------------------- #
#  Child span: llm.call                                                        #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def llm_call_span(
    model: str,
    fallback_used: bool = False,
) -> AsyncGenerator[trace.Span, None]:
    """
    Span for a single LLM invocation. Must be opened inside a conversation_span
    context so it becomes a child automatically.
    """
    tracer = get_tracer()
    start = time.time()
    with tracer.start_as_current_span("llm.call") as span:
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.fallback_used", fallback_used)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise
        finally:
            latency_ms = int((time.time() - start) * 1000)
            span.set_attribute("llm.latency_ms", latency_ms)


def set_llm_token_counts(
    span: trace.Span,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Sets token usage attributes onto an open llm.call span."""
    span.set_attribute("llm.prompt_tokens", prompt_tokens)
    span.set_attribute("llm.completion_tokens", completion_tokens)


# --------------------------------------------------------------------------- #
#  Child span: tool.{name}                                                     #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def tool_call_span(
    tool_name: str,
    input_keys: List[str],
) -> AsyncGenerator[trace.Span, None]:
    """
    Span for a single tool invocation. Must be opened inside a conversation_span
    context (or llm_call_span) so it is automatically parented.
    """
    tracer = get_tracer()
    start = time.time()
    success = False
    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("tool.input_keys", input_keys)
        try:
            yield span
            success = True
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise
        finally:
            latency_ms = int((time.time() - start) * 1000)
            span.set_attribute("tool.latency_ms", latency_ms)
            span.set_attribute("tool.success", success)
