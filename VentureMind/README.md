# VentureMind

VentureMind is a **serverless multi-agent due diligence pipeline** that automates venture capital startup analysis by scraping, parsing, and synthesizing qualitative and quantitative signals. The system coordinates domain-specialist agents to assess market opportunity, competitive positioning, financial health, and legal compliance — all powered by **locally running Ollama models** (zero API costs).

It persists analyzed results in a local SQLite database and compiles structured diligence reports in **Markdown**, **HTML**, and **Microsoft Word (DOCX)** formats.

---

## 1. Multi-Agent Architecture

The orchestration workflow manages parallel data collection followed by a sequential synthesis pass:

```
                       [User Input: Startup Name]
                                   │
                                   ▼
                       ┌──────────────────────┐
                       │DiligenceOrchestrator │◀───────── [Shared Memory]
                       └──────────┬───────────┘
                                  │
      ┌───────────────────────────┼───────────────────────────┬──────────────────────────┐
      ▼                           ▼                           ▼                          ▼
┌──────────────┐            ┌───────────┐               ┌───────────┐              ┌───────────┐
│MarketResearch│            │Competitor │               │ Financial │              │   Legal   │
│    Agent     │            │   Agent   │               │   Agent   │              │   Agent   │
└──────┬───────┘            └─────┬─────┘               └─────┬─────┘              └─────┬─────┘
       │                          │                           │                          │
       └──────────────────────────┼───────────────────────────┴──────────────────────────┘
                                  │ (Sync Join / Wait for All to Complete)
                                  ▼
                       ┌────────────────────────┐
                       │  Summarization Agent   │
                       └──────────┬─────────────┘
                                  │
                                  ▼
                       ┌────────────────────────┐
                       │     ReportRenderer     │ ──▶ [Markdown / HTML / DOCX]
                       └────────────────────────┘
```

---

## 2. Why Parallel Agents Beat One Monolithic Agent

*   **Error Isolation and Fault Tolerance**: A failure or timeout in a single specialist agent (e.g., due to an external scraper rate-limit or network timeout) does not crash the entire pipeline; other agents continue executing, and the summarizer synthesizes a report using the available data.
*   **Concurrent Execution Efficiency**: Fetching data from multiple rate-limited external APIs and parsing large documents in parallel reduces the overall wall-clock pipeline duration from multiple minutes to the maximum duration of the slowest agent (typically ~10–15 seconds).
*   **Reduced Context Prompt Bloat**: Specialist agents use compact, highly specific system prompts and tool registries, avoiding the prompt bloat, token consumption, and steering degradation associated with feeding a monolithic LLM all raw data sources simultaneously.

---

## 3. Data Sources Used

| Source | Data Type | Free/Paid | Used By |
| :--- | :--- | :--- | :--- |
| **DuckDuckGo Search** | Web News, Scrapes, and General Links | Free | All specialist agents (via Search tools) |
| **SEC EDGAR** | SEC Regulatory and Financial Filings | Free | Financial Agent |
| **Wikipedia & Wikidata** | Industry Overview, Trends, and Market Stats | Free | Market Research Agent |
| **OpenCorporates** | Corporate Registries and Incorporation Status | Free | Competitor Agent, Legal Agent |
| **USPTO & Google Patents** | Patent holdings, Trademarks, and IP logs | Free | Legal Agent |

---

## 4. Prerequisites & Quick Start

### Prerequisites
*   Python 3.10+
*   [Ollama](https://ollama.com/download) running locally on `localhost:11434`

### Quick Start

**Option A — Automated Setup:**
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

**Option B — Manual Setup:**
1.  **Install dependencies** (run in a virtual environment):
    ```bash
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    ```
2.  **Pull required local models** from Ollama:
    ```bash
    ollama pull qwen2.5:7b
    ollama pull nomic-embed-text
    ```
3.  **Configure environment** — copy the example and adjust as needed:
    ```bash
    cp .env.example .env
    ```
4.  **Run health check** to verify everything is configured:
    ```bash
    python scripts/health_check.py
    ```
5.  **Run the pipeline**:
    ```bash
    python run_diligence.py "Stripe"
    ```

---

## 5. Usage Examples

### CLI Pipeline
```bash
# Analyse a startup (generates Markdown, HTML, and DOCX reports)
python run_diligence.py "Linear"

# Specify a different startup
python run_diligence.py "Notion"
```

### REST API Server
```bash
# Start the API server
uvicorn src.api.app:app --reload --port 8000

# Trigger an analysis via HTTP
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"startup_name": "Stripe"}'

# List all reports
curl http://localhost:8000/api/v1/reports

# Get a specific report
curl http://localhost:8000/api/v1/reports/Stripe

# Health check
curl http://localhost:8000/api/v1/health
```

### Programmatic Python
```python
import asyncio
from src.api.dependencies import get_orchestrator

async def main():
    orchestrator = get_orchestrator()
    report = await orchestrator.run("Stripe")
    print(f"Startup: {report.startup_name}")
    print(f"Investment Score: {report.investment_score}/10")
    print(f"Summary: {report.summary[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/analyze` | Run full multi-agent due diligence pipeline |
| `GET` | `/api/v1/reports` | List recently generated reports |
| `GET` | `/api/v1/reports/{startup_name}` | Get the latest report for a startup |
| `GET` | `/api/v1/health` | System health check (Ollama, DB, memory) |

---

## 7. Adding a New Agent

Follow these five steps to extend VentureMind with a new domain specialist agent:

1.  **Define Domain Models**: Add the new agent's structured output data model in `src/models/domain.py` (inheriting from `pydantic.BaseModel`).
2.  **Implement Scraper Tools**: Create the necessary data gathering/search tool functions under `src/tools/` (e.g., in a new or existing module).
3.  **Implement Agent Class**: Write the agent class in `src/agents/your_domain/agent.py`. Follow the constructor pattern `(ollama_client, tools, settings)` and implement the async `run(self, startup: StartupProfile) -> AgentResult` method.
4.  **Register in Orchestrator**:
    *   Import the new agent class in `src/orchestrator/orchestrator.py`.
    *   Add the agent's key identifier to the parallel execution plan group in `_plan_execution()` and compile its results inside `_assemble_report()`.
5.  **Expose in Dependencies & API**: Add the getter function `get_your_domain_agent()` in `src/api/dependencies.py` and register it inside the `agents` dictionary built by `get_orchestrator()`.

---

## 8. Environment Variables Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | SQLite connection path for the report database. | *Required* |
| `DRAGONFLY_URL` | SQLite connection path for shared memory. | *Required* |
| `OLLAMA_BASE_URL` | Base URL of the Ollama server. | `http://localhost:11434` |
| `OLLAMA_ORCHESTRATOR_MODEL` | Model for orchestrator profile extraction. | `qwen2.5:7b` |
| `OLLAMA_ANALYST_MODEL` | Model for domain specialist agents. | `qwen2.5:7b` |
| `OLLAMA_SUMMARY_MODEL` | Model for the summarization agent. | `qwen2.5:7b` |
| `OLLAMA_EMBED_MODEL` | Model for embedding generation. | `nomic-embed-text` |
| `REPORTS_OUTPUT_DIR` | Output directory for generated reports. | `data/reports` |
| `MAX_SEARCH_RESULTS` | Max search results retrieved per query. | `10` |
| `MAX_PDF_PAGES` | Max pages parsed from a source PDF. | `50` |
| `AGENT_TIMEOUT_SECONDS` | Timeout per agent run (seconds). | `180` |
| `PARALLEL_AGENT_LIMIT` | Max concurrent agent executions. | `4` |
| `LOG_LEVEL` | Logging level. | `INFO` |

---

## 9. Project Structure

```
VentureMind/
├── run_diligence.py            # CLI entry point
├── pyproject.toml              # Dependencies & project metadata
├── .env.example                # Environment variable template
├── prompts/                    # LLM prompt templates
│   ├── market_analysis.txt
│   ├── financial_analysis.txt
│   ├── competitor_positioning.txt
│   └── profile_extraction.txt
├── scripts/
│   ├── setup.sh                # Automated setup script
│   └── health_check.py         # Pre-flight system health check
├── src/
│   ├── agents/                 # Domain specialist agents
│   │   ├── market_research/
│   │   ├── competitor/
│   │   ├── financial/
│   │   ├── legal/
│   │   └── summarization/
│   ├── api/
│   │   ├── app.py              # FastAPI application
│   │   └── dependencies.py     # DI factories
│   ├── config/
│   │   └── settings.py         # Pydantic Settings
│   ├── llm/
│   │   ├── ollama_client.py    # Pooled async Ollama client
│   │   └── adk_bridge.py       # Google ADK model bridge
│   ├── memory/
│   │   ├── shared_memory.py    # Inter-agent KV store (SQLite)
│   │   └── database.py         # Report persistence (SQLite)
│   ├── models/
│   │   ├── domain.py           # Pydantic domain models
│   │   └── orchestration.py    # Workflow & task models
│   ├── orchestrator/
│   │   └── orchestrator.py     # Pipeline orchestrator
│   ├── report/
│   │   └── renderer.py         # Markdown/HTML/DOCX renderer
│   ├── tools/                  # External data scrapers
│   │   ├── document/
│   │   ├── financial/
│   │   ├── legal/
│   │   └── search/
│   └── utils/
│       └── prompt_loader.py    # Template loading utility
├── tests/
│   ├── unit/
│   └── integration/
└── data/
    └── reports/                # Generated report outputs
```

---

## 10. License

MIT
