# VentureMind

VentureMind is a serverless multi-agent due diligence pipeline that automates venture capital startup analysis by scraping, parsing, and synthesizing qualitative and quantitative signals. The system coordinates domain-specialist agents to assess market opportunity, competitive positioning, financial health, and legal compliance. It persists analyzed results in a local SQLite database and compiles structured diligence reports in Markdown and Microsoft Word (docx) formats.

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
                       │     ReportRenderer     │ ──▶ [Markdown / Docx Reports]
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
*   Ollama running locally on `localhost:11434`

### Quick Start
1.  **Install dependencies** (run in python environment):
    ```bash
    pip install -e ".[dev]"
    ```
2.  **Pull required local models** from Ollama:
    ```bash
    ollama pull mistral:7b
    ollama pull codellama:13b
    ollama pull nomic-embed-text
    ```
3.  **Configure Environment Variables** in a `.env` file in the root workspace folder:
    ```env
    DATABASE_URL=sqlite:///data/reports.db
    DRAGONFLY_URL=sqlite:///data/shared_memory.db
    ```
4.  **Run test suite** to verify setup:
    ```bash
    pytest
    ```

---

## 5. Programmatic Execution Example

You can run the diligence pipeline programmatically using python:

```python
import asyncio
from src.api.dependencies import get_orchestrator

async def main():
    orchestrator = get_orchestrator()
    report = await orchestrator.run("Stripe")
    print(f"Startup: {report.startup_name}")
    print(f"Investment Score: {report.investment_score}/10")
    print(f"Summary Summary: {report.summary[:150]}...")

if __name__ == "__main__":
    asyncio.run(main())
```

### Truncated Output Example
```markdown
# VentureMind Due Diligence Report: Stripe

**Generated On:** June 11, 2026
**Investment Recommendation:** ⭐ 9.2/10 — EXCEPTIONAL OPPORTUNITY

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Risk Assessment](#risk-assessment)
...

### Executive Summary
Stripe is a market-leading payment processing infrastructure company showing high market opportunity and strong financial metrics. Operating in a massive addressable market with over $10T global payments volume, the company has built a reliable moat...
```

---

## 6. Adding a New Agent

Follow these five steps to extend VentureMind with a new domain specialist agent:

1.  **Define Domain Models**: Add the new agent's structured output data model in `src/models/domain.py` (inheriting from `pydantic.BaseModel`).
2.  **Implement Scraper Tools**: Create the necessary data gathering/search tool functions under `src/tools/` (e.g., in a new or existing module).
3.  **Implement Agent Class**: Write the agent class in `src/agents/your_domain/agent.py`. Inherit or follow the constructor pattern `(ollama_client, tools, settings)` and implement the async `run(self, startup: StartupProfile) -> AgentResult` method.
4.  **Register in Orchestrator**:
    *   Import the new agent class in `src/orchestrator/orchestrator.py`.
    *   Add the agent's key identifier to the parallel execution plan group in `_plan_execution()` and compile its results inside `_assemble_report()`.
5.  **Expose in Dependencies & API**: Add the getter function `get_your_domain_agent()` in `src/api/dependencies.py` and register it inside the `agents` dictionary built by `get_orchestrator()`.

---

## 7. Environment Variables Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | Connection path for the SQLite report database. | *Required* |
| `DRAGONFLY_URL` | Connection path for the SQLite shared memory database. | *Required* |
| `OLLAMA_BASE_URL` | Base URL of the Ollama server. | `http://localhost:11434` |
| `OLLAMA_ORCHESTRATOR_MODEL` | Ollama model name used by orchestrator for profile extraction. | `mistral:7b` |
| `OLLAMA_ANALYST_MODEL` | Ollama model name used by domain specialist agents. | `codellama:13b` |
| `OLLAMA_SUMMARY_MODEL` | Ollama model name used by the summarization agent. | `mistral:7b` |
| `OLLAMA_EMBED_MODEL` | Ollama model name used for embedding generation. | `nomic-embed-text` |
| `REPORTS_OUTPUT_DIR` | Output directory for generated PDF and Markdown files. | `data/reports` |
| `MAX_SEARCH_RESULTS` | Max search results retrieved per DuckDuckGo query. | `10` |
| `MAX_PDF_PAGES` | Max pages parsed from a source PDF document. | `50` |
| `AGENT_TIMEOUT_SECONDS` | Execution timeout limit per agent run in seconds. | `120` |
| `PARALLEL_AGENT_LIMIT` | Max concurrent specialist agent executions. | `4` |
| `LOG_LEVEL` | Logger level for system output. | `INFO` |
