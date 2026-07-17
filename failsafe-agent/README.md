# Failsafe Agent 🛡️🤖

A production-grade, highly resilient AI Customer Support Agent framework built using Python 3.9/3.11, **LangGraph**, **FastAPI**, **Redis**, and **PostgreSQL**. 

This system is engineered for **resilience-first operations**, **cryptographic audit logging**, **data privacy (PII scrubbing)**, and **real-time observability** to handle production traffic safely.

---

## 🏗️ Core Architecture

```mermaid
graph TD
    A[FastAPI Client] -->|HTTP Request| B(Rate Limiter Middleware)
    B -->|Check Limits| C{Redis Window}
    C -->|Allowed| D(PII Scrubber)
    D -->|Scrubbed Message| E[LangGraph Conversation Engine]
    E -->|1. Classify| F[Intent Classifier Node]
    E -->|2. Agent Loop| G[Main Agent Node]
    G -->|Tool Execution| H[Stripe / Policy / Customer Tools]
    G -->|Failure/Degradation| I[Escalation Gate Node]
    I -->|Create Ticket| J[Escalation Tool]
    E -->|Audit Log| K[PostgreSQL Cryptographic Chain]
```

### 1. Multi-Agent Reasoning Loop (LangGraph)
*   **Classifier Node**: Employs a fast fallback model to categorize incoming intent (`REFUND_REQUEST`, `POLICY_LOOKUP`, etc.). Sets confidence score.
*   **Main Agent Node**: Governs the reasoning chain. Checks policies and customer context before issuing refunds.
*   **Escalation Gate**: Monitors agent state. Automatically intercepts and triggers human handoff if the confidence is low ($< 0.4$), Stripe is down, or retry thresholds are exceeded.

### 2. Multi-Tier Resilience & Self-Healing
*   **LLM Provider Fallback**: Automatic transitions between primary and secondary LLM providers with exponential backoff & full jitter.
*   **Stripe Circuit Breaker**: Tracks failures in outbound API calls. Temporarily disables Stripe operations (trips to `OPEN`) if $\ge 5$ failures occur in a 60s window.
*   **Temporal Budgeting**: Guarantees bounded API response times; execution automatically degrades to human handoff if the budgeted time budget runs dry.

### 3. Data Governance & Security
*   **Cryptographic Audit Logging**: Every conversation stage is logged using SHA-256 hash chains. Back-linked rows form a tamper-evident ledger verified upon audit requests.
*   **PII Redaction**: Pre-processes messages using Microsoft Presidio to redact Credit Cards, Emails, SSNs, and Phone Numbers before persisting to database/cache.
*   **Idempotency Engine**: Deduplicates Stripe actions (like refunds) based on request hashes using a Redis-backed lock.

---

## 📊 Observability (SLOs & Metrics)

The agent exposes Prometheus metrics configured with the following Service Level Objectives (SLOs):
*   **Latency**: $p99$ conversation response latency $< 10s$.
*   **Availability**: Successful/un-escalated request rate $\ge 99\%$.

### Custom Metrics Exposed:
1.  `llm_request_duration_seconds`: Histogram measuring end-to-end latency labeled by model and status.
2.  `tool_calls_total`: Counter for tool dispatch rates labeled by success/failure.
3.  `retries_total`: Count of retry attempts labeled by operation name.
4.  `circuit_breaker_state`: Gauge of circuit status (`0=CLOSED`, `0.5=HALF_OPEN`, `1=OPEN`).
5.  `escalations_total`: Tracking human handoff rates by reason.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.9 or 3.11
*   Docker & Docker Compose

### 1. Build Environment
```bash
# Clone the repository
git clone https://github.com/simranjeet97/AndrejKarpathy_2026_FocusProjects.git
cd AndrejKarpathy_2026_FocusProjects/failsafe-agent

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```env
ANTHROPIC_API_KEY=your_key
STRIPE_API_KEY=your_key
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/failsafe
```

### 3. Spin Up Infrastructure
```bash
docker-compose up -d
```
This launches **Redis**, **PostgreSQL**, **Prometheus**, and **Grafana** configured out-of-the-box.

---

## 🧪 Testing

The framework includes a comprehensive test suite (Unit, Integration, and Chaos tests).

```bash
# Run the entire test suite
python3 -m pytest

# Run only Chaos Tests
python3 -m pytest tests/chaos/

# Run only Integration Tests
python3 -m pytest tests/integration/
```

---

## 🔌 API Documentation

When running locally (`uvicorn src.main:app`), visit http://localhost:8000/docs for the Swagger UI.

### Key Endpoints:
*   `POST /conversations`: Start a conversation session (includes PII scrubbing and rate limit checking).
*   `POST /conversations/{id}/messages`: Append message to history and resume agent graph.
*   `GET /conversations/{id}/audit`: Fetch the tamper-evident cryptographic log with verified integrity check.
*   `GET /metrics`: Scraped by Prometheus for Grafana visualizations.
