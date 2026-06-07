# QueryForge

## 1. What it does
QueryForge is a local, offline-first multi-tool research agent that integrates natural language querying with structured databases, files, and third-party SaaS APIs. Powered by the Google Agents SDK, it orchestrates complex workflows by executing specialized, narrow-scope tools in a dependency-aware sequence. The agent leverages a local Ollama instance for planning, execution validation, and high-fidelity output synthesis.

## 2. Architecture
```
User Query
    │
    ▼
[QueryForgeAgent](file:///Users/simranjeetsingh/Downloads/AI_Projects/AndrejKarpathy_2026_FocusProjects/queryforge/src/agent/queryforge_agent.py)
    │
    ▼
[ToolRegistry](file:///Users/simranjeetsingh/Downloads/AI_Projects/AndrejKarpathy_2026_FocusProjects/queryforge/src/agent/tool_registry.py) (Tool Router)
    │
    ├─► DB Tools (SQLite: churn, MRR, LTV metrics)
    ├─► Web Tools (DuckDuckGo: industry benchmarks, search)
    ├─► PDF Tools (PyMuPDF: summarization, parsing)
    ├─► Chart Tools (Matplotlib: trends, comparisons, bar/pie charts)
    └─► API Tools (Stripe billing/MRR, Local Markdown KB)
    │
    ▼
Ollama Synthesis (LLM response formatting & key findings extraction)
    │
    ▼
AgentResponse (Answer text, key findings list, sources, and chart file paths)
```

## 3. Tool Design Philosophy
* **Security & Injection Mitigation:** Narrow, parameterized tools isolate database and system execution from user input, preventing prompt injection attacks (such as raw SQL injection or directory traversal) that arise from exposing generic query executors.
* **Deterministic LLM Execution:** Providing the planner model with highly specialized, single-purpose function schemas reduces reasoning overhead, prevents argument hallucination, and ensures reliable dependency mapping.
* **Performance & Resource Optimization:** Focused tools target and retrieve minimal necessary datasets, preventing database connection saturation and saving context window tokens during synthesis.

## 4. Prerequisites
* **Python:** `>= 3.9` (fully compatible with Python 3.9, 3.10, and 3.11+)
* **Ollama:** A running local Ollama instance hosting the orchestrator LLM (e.g. `qwen2.5:7b`) and embedding model (e.g. `nomic-embed-text`)
* **SQLite:** Local command-line tool (for managing standard relational database tables)
* **Dragonfly / Redis:** *Optional* (QueryForge automatically detects missing instances and falls back to a high-fidelity local `InMemoryRedisClient` in RAM)
* **Docker & Docker Compose:** *Optional* (only required if running Dragonfly/Redis cache containers)

## 5. Quick Start
Follow these steps to set up and run QueryForge:

1. **Pull the required models in Ollama:**
   ```bash
   ollama pull qwen2.5:7b
   ollama pull nomic-embed-text
   ```

2. **Launch the application using the integrated shell script:**
   The repository includes a launch script that automatically frees port 8000, initializes the SQLite database if it's missing, selects the correct Python interpreter (3.9+), and starts the server with hot-reloading:
   ```bash
   ./run.sh
   ```

   *Alternatively, to spin up backing cache services in Docker, run:*
   ```bash
   docker compose up -d
   ```

3. **Send a research query to the agent:**
   ```bash
   curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Find our highest churn customer segment and compare with industry trends"}'
   ```


## 6. Example Queries
The agent can process and route the following natural language requests:
* *"Find our highest churn customer segment and compare with industry trends"*
* *"What is our current monthly recurring revenue (MRR) for the Enterprise segment compared to last month?"*
* *"Generate a chart of customer counts by segment for the past 6 months"*
* *"Summarize the key takeaways and customer risks from the uploaded contract PDF"*
* *"Search the local knowledge base for security policies matching GDPR compliance"*

## 7. Adding a New Tool
1. **Implement the Function:** Write a typed Python function in the appropriate category subdirectory under `src/tools/` (e.g., `src/tools/database/` or `src/tools/api/`). Ensure it has detailed docstrings and explicit type hints.
2. **Register in ToolRegistry:** Import your tool function in [tool_registry.py](file:///Users/simranjeetsingh/Downloads/AI_Projects/AndrejKarpathy_2026_FocusProjects/queryforge/src/agent/tool_registry.py) and add it to the corresponding registration method (e.g., `_register_api_tools()`), setting its `PermissionLevel` and authorization requirements.
3. **Expose Dependencies (Optional):** If the tool requires settings, database pools, or the LLM client, pass them via the registry class constructor.
4. **Verify Safety Rules:** Write unit tests in the `tests/` directory to verify that the tool rejects invalid parameters, throws appropriate errors, and prevents malicious payloads.

## 8. .env Reference Table
Create a `.env` file in the root directory if you wish to override any of the default configurations:

| Variable Name | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | `str` | `sqlite+aiosqlite:///queryforge.db` | Connection string for database query tools. |
| `STRIPE_API_KEY` | `str` | `mock_stripe_api_key` | API key for accessing customer billing records. |
| `STRIPE_WEBHOOK_SECRET` | `str` | `mock_stripe_webhook_secret` | Signature key used to verify incoming Stripe webhook events. |
| `NOTION_API_KEY` | `str` | `mock_notion_api_key` | Integration token for external knowledge base sync. |
| `NOTION_DATABASE_ID` | `str` | `mock_notion_database_id` | Target database ID within the connected workspace. |
| `OLLAMA_BASE_URL` | `str` | `http://localhost:11434` | Host URL for the local Ollama daemon service. |
| `OLLAMA_AGENT_MODEL` | `str` | `qwen2.5:7b` | Local model to execute agent reasoning and tool sequence planning. |
| `OLLAMA_EMBED_MODEL` | `str` | `nomic-embed-text` | Local model used for document vector embeddings. |
| `DRAGONFLY_URL` | `str` | `redis://localhost:6379` | Connection URI for Dragonfly/Redis caching service (*Optional fallback to RAM*). |
| `CHARTS_OUTPUT_DIR` | `str` | `data/charts` | Absolute or relative path where generated charts are exported. |
| `MAX_PDF_PAGES` | `int` | `50` | Limits the maximum number of pages read from a PDF document. |
| `MAX_TOOL_RETRIES` | `int` | `3` | Maximum retry limit for temporary tool execution failures. |
| `LOG_LEVEL` | `str` | `INFO` | Logging verbosity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

