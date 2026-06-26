# EvalOps

**CI/CD for your prompts and AI agents.**

EvalOps is a local-first LLM regression testing platform that catches prompt regressions before they hit production. Run golden-dataset evaluations against any Ollama model, score outputs with LLM-as-judge, detect regressions automatically, and review results in a live dashboard — all offline, all free.

---

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Install Ollama and pull models (llama3, mistral, phi3)
make setup-ollama

# 3. Seed the database with golden dataset tasks
make seed

# 4. Start the API server (terminal 1)
make run

# 5. Run an evaluation batch (terminal 2)
make eval

# 6. View the dashboard
open http://localhost:8000/dashboard

# 7. Print the latest report to terminal
make report
```

---

## Architecture

EvalOps is built as a **5-layer pipeline** where each layer feeds into the next:

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: DATA — Golden Datasets                                │
│  JSON files with input prompts, expected outputs, and tags      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: INFERENCE — Ollama Client + EvalRunner                │
│  Sends prompts to local Ollama models, records latency/tokens   │
│  Orchestrated via Google Agent SDK (agentic task runner)        │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: SCORING — EvalScorer + LLMJudge                       │
│  Deterministic scoring (Jaccard, exact match, composite) plus   │
│  LLM-as-judge for semantic evaluation and hallucination detect  │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: ANALYSIS — RegressionEngine + PairwiseComparator      │
│  Detects score drops vs baseline, compares model outputs A/B,   │
│  generates regression alerts and formatted reports              │
├─────────────────────────────────────────────────────────────────┤
│  Layer 5: REPORTING — FastAPI + Dashboard + MetricsCollector     │
│  REST API endpoints, Chart.js dashboard, latency/token/cost     │
│  metrics, human feedback loop, downloadable JSON reports        │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Concern | Choice | Why |
|---|---|---|
| LLM Inference | Ollama (local) | Free, offline, supports llama3/mistral/phi3 |
| Orchestration | Google Agent SDK | Free, open source, agentic task runner |
| Storage | SQLite | Zero infra, file-based, no cost |
| API | FastAPI | Fast, free, Python-native |
| Evaluation | Custom Python + LLM-as-judge | No paid APIs |
| Dashboard | Jinja2 HTML + Chart.js | No frontend build step |
| File Watching | Watchdog | Auto-trigger evals on dataset changes |

---

## Project Structure

```
EvalOps/
├── evalops/
│   ├── __init__.py           # Package exports + print_last_report()
│   ├── config.py             # Settings singleton (.env / env vars)
│   ├── models.py             # Dataclasses: EvalTask, EvalRun, Regression, HumanFeedback
│   ├── ollama_client.py      # Async Ollama API client (aiohttp, 120s timeout)
│   ├── storage.py            # SQLiteStorage — raw sqlite3 CRUD
│   ├── runner.py             # EvalRunner + Google Agent SDK integration
│   ├── scorer.py             # Deterministic scoring (Jaccard, exact, contains, composite)
│   ├── judge.py              # LLMJudge + HallucinationDetector
│   ├── comparator.py         # PairwiseComparator (deterministic + LLM)
│   ├── regression_engine.py  # Regression detection, reports, alerts
│   ├── metrics.py            # MetricsCollector (latency, tokens, cost, pass rate)
│   ├── api.py                # FastAPI REST API (CORS, background tasks)
│   ├── watcher.py            # Watchdog file watcher for CI triggers
│   └── utils.py              # Utility helpers
├── tests/
│   ├── conftest.py           # Fixtures (temp DB, sample data, mock Ollama)
│   ├── test_models.py        # Serialization roundtrip tests
│   ├── test_storage.py       # SQLite CRUD tests
│   ├── test_scorer.py        # Scoring algorithm tests
│   ├── test_judge.py         # LLM judge + hallucination tests
│   ├── test_regression.py    # Regression detection tests
│   ├── test_runner.py        # Runner + dataset loading tests
│   └── test_api.py           # FastAPI endpoint tests
├── templates/
│   └── dashboard.html        # Jinja2 dashboard template
├── static/
│   └── dashboard.js          # Chart.js dashboard logic
├── golden_datasets/
│   └── example_dataset.json  # 5 evaluation tasks (QA, summarization, code, etc.)
├── scripts/
│   ├── setup_ollama.sh       # Auto-install Ollama + pull models
│   ├── seed_db.py            # Seed database from golden dataset
│   └── ci_trigger.py         # CI/CD trigger (poll + exit code)
├── .github/workflows/
│   └── evalops.yml           # GitHub Actions workflow
├── requirements.txt
├── Makefile
├── .env.example
└── README.md
```

---

## Adding Eval Tasks

Golden datasets are JSON arrays of task objects. Add new tasks to `golden_datasets/` or create new dataset files:

```json
[
  {
    "id": "unique-task-id",
    "name": "Human-readable task name",
    "input_prompt": "The prompt sent to the LLM",
    "expected_output": "The golden reference output",
    "tags": ["category", "difficulty"]
  }
]
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (auto-generated if omitted) |
| `name` | string | Display name for dashboard/reports |
| `input_prompt` | string | The exact prompt sent to the model |
| `expected_output` | string | Golden reference answer for scoring |
| `tags` | string[] | Categories for filtering (e.g., `["factual", "qa"]`) |

After adding tasks, re-seed the database:

```bash
make seed
# or for a custom dataset:
python scripts/seed_db.py --dataset golden_datasets/my_custom.json
```

---

## API Reference

All endpoints are available at `http://localhost:8000`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check (Ollama + DB status) |
| `GET` | `/tasks` | List tasks (`?tags=factual,qa` to filter) |
| `POST` | `/tasks` | Create a new task |
| `POST` | `/run` | Trigger evaluation batch (background) |
| `GET` | `/runs/{run_id}` | Full report for a run |
| `GET` | `/runs/{run_id}/regressions` | Regression alerts for a run |
| `GET` | `/runs/{run_id}/compare?baseline_run_id=X` | Pairwise comparison |
| `POST` | `/feedback` | Submit human feedback (1-5 stars + notes) |
| `GET` | `/dashboard` | HTML dashboard |
| `GET` | `/runs` | List all unique run IDs |
| `GET` | `/report/{run_id}` | Download report as JSON |

### Trigger an Evaluation Run

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"dataset_path": "golden_datasets/example_dataset.json", "model": "llama3"}'
```

Response:
```json
{"run_id": "abc-123-...", "status": "started"}
```

---

## Running in CI

### GitHub Actions

The project includes a workflow at `.github/workflows/evalops.yml`. It runs on push/PR and uses `scripts/ci_trigger.py` to trigger evaluations and gate on regressions.

### Manual CI Script

```bash
# Set environment variables
export EVALOPS_API_URL=http://localhost:8000
export EVALOPS_MODEL=llama3
export EVALOPS_DATASET=golden_datasets/example_dataset.json

# Run CI trigger — exits 0 if all pass, exits 1 if regressions found
python scripts/ci_trigger.py
```

The CI script:
1. POSTs to `/run` to trigger an evaluation
2. Polls `/runs/{run_id}` every 5 seconds until completion (timeout: 300s)
3. Checks for regressions — if any found, exits with code 1 (CI failure)
4. Prints a formatted regression report to stdout

---

## Key Concepts

### Golden Datasets
Curated sets of input/output pairs that define expected model behavior. These are the "test cases" for your LLM.

### LLM-as-Judge
Uses a local Ollama model to semantically evaluate outputs beyond simple string matching. Returns a score (0-1), a reason, and a hallucination flag. Falls back to deterministic composite scoring if the judge model is unavailable.

### Pairwise Comparison
Compares two model runs head-to-head — either deterministically (score/latency/tokens) or via LLM judge ("Which output is better?"). Useful for A/B testing models or prompt versions.

### Regression Detection
Automatically compares each task's score against its historical baseline (the most recent passing run). If the score drops by ≥ 0.1 (configurable `REGRESSION_THRESHOLD`), a regression is flagged, saved to the database, and surfaced in the dashboard.

### Human Feedback Loop
Reviewers can rate individual task outputs (1-5 stars) with notes via the dashboard or API. This creates an audit trail and captures cases where automated scoring disagrees with human judgment.

### Scoring Pipeline

EvalOps uses a multi-signal scoring approach:

| Scorer | Weight | Description |
|---|---|---|
| Token Overlap (Jaccard) | 50% | Word-level similarity between output and expected |
| Contains Match | 30% | Whether expected output appears in model output |
| Length Penalty | 20% | Penalizes if output length deviates >50% from expected |

The **composite score** combines all three. The **LLM judge** provides a semantic score on top, with hallucination detection.

---

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `DB_PATH` | `./evalops.db` | SQLite database file path |
| `DEFAULT_MODEL` | `llama3` | Model for evaluations |
| `JUDGE_MODEL` | `llama3` | Model for LLM-as-judge scoring |
| `JUDGE_THRESHOLD` | `0.7` | Minimum score to count as "passing" |
| `MOCK_OLLAMA` | `false` | Set to `true` for testing without Ollama |

---

## Running Tests

```bash
# Run full test suite (uses mock Ollama, no server needed)
make test

# Run with verbose output
MOCK_OLLAMA=true pytest tests/ -v --tb=long

# Run a specific test file
MOCK_OLLAMA=true pytest tests/test_scorer.py -v
```

The test suite includes 26 tests across 7 modules:
- **test_models** — Serialization roundtrip for all dataclasses
- **test_storage** — SQLite CRUD, baseline retrieval, tag filtering
- **test_scorer** — Exact match, Jaccard, length penalty, composite
- **test_judge** — LLM judge mock, fallback on error, hallucination detection
- **test_regression** — No baseline, above/below threshold, report generation
- **test_runner** — Dataset loading, single task, full batch execution
- **test_api** — Health endpoint, task CRUD, feedback submission

---

## Makefile Targets

| Target | Command | Description |
|---|---|---|
| `make install` | `pip install -r requirements.txt` | Install Python dependencies |
| `make setup-ollama` | `./scripts/setup_ollama.sh` | Install Ollama + pull models |
| `make run` | `uvicorn evalops.api:app --reload` | Start API server on port 8000 |
| `make test` | `pytest tests/ -v --tb=short` | Run test suite |
| `make eval` | `python -m evalops.runner ...` | Run evaluation batch |
| `make watch` | `python -m evalops.watcher` | Watch for file changes |
| `make seed` | `python scripts/seed_db.py` | Seed DB with golden dataset |
| `make report` | `python -c "import evalops; ..."` | Print latest report |
| `make clean` | `rm -f evalops.db ...` | Clean generated files |

---

## License

MIT
