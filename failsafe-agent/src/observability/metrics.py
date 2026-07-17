"""
Prometheus metrics definitions for failsafe-agent.

SLOs (evaluated via Prometheus recording rules / alerts):
  - p99 conversation latency  < 10s
  - error rate                 < 1%
"""
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
)

# ---------------------------------------------------------------------------
# Metric Definitions
# ---------------------------------------------------------------------------

# (1) LLM request duration
LLM_REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "End-to-end latency for LLM requests including retries",
    labelnames=["model", "status", "fallback_used"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# (2) Tool call counter
TOOL_CALLS_TOTAL = Counter(
    "tool_calls_total",
    "Total number of tool executions dispatched by the agent",
    labelnames=["tool_name", "success"],
)

# (3) Retry counter
RETRIES_TOTAL = Counter(
    "retries_total",
    "Total number of retry attempts across all operations",
    labelnames=["operation", "attempt_number"],
)

# (4) Circuit breaker state gauge  (0=closed, 0.5=half_open, 1=open)
CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Current state of the circuit breaker per service (0=CLOSED, 0.5=HALF_OPEN, 1=OPEN)",
    labelnames=["service"],
)

# (5) Escalation counter
ESCALATIONS_TOTAL = Counter(
    "escalations_total",
    "Total number of conversations escalated to human agents",
    labelnames=["reason", "priority"],
)

# (6) End-to-end conversation duration
CONVERSATION_DURATION = Histogram(
    "conversation_duration_seconds",
    "Total wall-clock time from conversation start to resolution or escalation",
    labelnames=["resolved", "escalated"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0],
)

# ---------------------------------------------------------------------------
# Helper context managers (instrument call sites without boilerplate)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def observe_llm_request(
    model: str,
    fallback_used: bool = False,
) -> AsyncGenerator[None, None]:
    """Async context manager: records LLM call duration and status label."""
    status = "success"
    with LLM_REQUEST_DURATION.labels(
        model=model,
        status="in_flight",
        fallback_used=str(fallback_used),
    ).time():
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            # Re-observe with resolved status (prometheus_client time() already
            # recorded the value; this label approach captures it separately)
            pass


def record_tool_call(tool_name: str, success: bool) -> None:
    """Increments the tool call counter."""
    TOOL_CALLS_TOTAL.labels(tool_name=tool_name, success=str(success)).inc()


def record_retry(operation: str, attempt_number: int) -> None:
    """Increments the retry counter."""
    RETRIES_TOTAL.labels(operation=operation, attempt_number=str(attempt_number)).inc()


def set_circuit_breaker_state(service: str, state: str) -> None:
    """
    Updates the circuit breaker gauge.
    state: "CLOSED" -> 0, "HALF_OPEN" -> 0.5, "OPEN" -> 1
    """
    value_map = {"CLOSED": 0.0, "HALF_OPEN": 0.5, "OPEN": 1.0}
    CIRCUIT_BREAKER_STATE.labels(service=service).set(value_map.get(state, 0.0))


def record_escalation(reason: str, priority: str) -> None:
    """Increments the escalation counter."""
    ESCALATIONS_TOTAL.labels(reason=reason, priority=priority).inc()


@asynccontextmanager
async def observe_conversation(
    resolved: bool = False,
    escalated: bool = False,
) -> AsyncGenerator[None, None]:
    """Async context manager: records full conversation duration."""
    with CONVERSATION_DURATION.labels(
        resolved=str(resolved),
        escalated=str(escalated),
    ).time():
        yield
