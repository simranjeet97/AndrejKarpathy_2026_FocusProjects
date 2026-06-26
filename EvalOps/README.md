# EvalOps

EvalOps is an LLM regression testing platform designed to run evaluations offline and local-first.

## Tech Stack & Architecture

- **LLM Inference**: Ollama (local running models like `llama3`, `phi3`, etc.)
- **Orchestration**: Google Agent SDK (Python task execution and agent flow coordination)
- **IDE / Environment**: Project IDX or similar cloud/local setups
- **Storage**: SQLite (zero-configuration file-based database)
- **API**: FastAPI (web endpoints for triggering evals and fetching results)
- **Dashboard**: Jinja2 HTML rendering + Chart.js (clean UI with no build step)
- **CI / Watcher**: Watchdog (monitoring local files/datasets for automatic evaluations)

## Project Structure

```
evalops/
  __init__.py
  config.py          # settings dataclass, loads from .env
  models.py          # SQLite schema dataclasses
  runner.py          # task execution skeleton
  scorer.py          # scoring skeleton
  judge.py           # LLM-as-judge skeleton
  comparator.py      # pairwise comparison skeleton
  metrics.py         # latency/cost tracking skeleton
  storage.py         # SQLite CRUD skeleton
  api.py             # FastAPI app skeleton
  dashboard.py       # HTML rendering skeleton

tests/
  conftest.py
  test_runner.py
  test_scorer.py

golden_datasets/
  example_dataset.json

scripts/
  setup_ollama.sh
  seed_db.py
```

## Getting Started

### 1. Installation
Install the required packages using the Makefile:
```bash
make install
```

### 2. Configure Environment
Copy `.env.example` to `.env` and adjust the variables:
```bash
cp .env.example .env
```

### 3. Setup Ollama
Make sure Ollama is running and pull the default model:
```bash
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
```

### 4. Seed Database
Seed the SQLite database with the golden dataset tasks:
```bash
python scripts/seed_db.py
```

### 5. Running the Application
Start the FastAPI server:
```bash
make run
```

### 6. Run Tests
Run the pytest test suite:
```bash
make test
```
