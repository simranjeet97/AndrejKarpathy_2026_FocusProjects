# Can a Coding Agent Learn From Feedback?

> **Research Prototype & Experiment Suite**
> Accompanying companion prototype for the Medium article investigating whether AI coding agents actually learn from feedback.

---

## 1. Research Question

> **When a coding agent improves after receiving feedback, does that improvement persist and transfer after the original feedback is removed?**

This repository operationalizes system-level behavioral learning across five core properties:
1. **Persistence** — Improvement remains after original task context and feedback are removed.
2. **Transfer** — Improvement appears on previously unseen tasks in the same domain.
3. **Cross-Family Transfer** — Improvement generalizes to a distinct class of coding problems.
4. **Retention** — Improvement survives intervening unrelated tasks.
5. **Non-Regression** — Previously solved capabilities do not deteriorate.

```text
feedback
   ↓
agent state changes
   ↓
feedback removed
   ↓
unseen evaluation
   ↓
transfer?
```

---

## 2. Experimental Conditions

The pilot compares four compute-matched agent conditions:

1. **Baseline**: Standard coding agent (code → test → retry). Retains no state between tasks.
2. **Reflection**: Explicit reflection step on failure. Intra-task reflection only; no cross-task state.
3. **Memory**: Creates and retrieves external structured memories (failure pattern, diagnosis, strategy, constraint) persistent across tasks.
4. **Workflow Modification**: Proposes constrained structural modifications to its problem-solving pipeline sequence (e.g. `inspect_tests -> plan -> code -> test`). Workflow persists across tasks.

---

## 3. What This Experiment Does NOT Establish

* It does **NOT** demonstrate parameter-level learning or model weight updates.
* It does **NOT** prove internal representation changes or consciousness.
* It does **NOT** establish universal conclusions about all LLM coding agents.
* It measures **behavioral/system-level learning** in a controlled pilot setting.

---

## 4. Quick Start & Installation

```bash
# 1. Clone repository
git clone https://github.com/your-username/agent-learning-pilot.git
cd agent-learning-pilot

# 2. Set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 5. Local Model Setup

The experiment supports any OpenAI-compatible inference server (e.g., Ollama, vLLM, llama.cpp).

Example with Ollama:
```bash
ollama run codellama:7b
```

Config in `configs/pilot.yaml`:
```yaml
model:
  provider: local
  endpoint: http://localhost:11434/v1
  model: codellama:7b
  temperature: 0.0
```

---

## 6. Running Experiments

### Run Unit & Integration Tests (No GPU/LLM Required)
```bash
pytest
```

### Run Pilot with Mock Model (Fast CI / Verification)
```bash
make run-mock
```

### Run Full Experiment with Local LLM
```bash
make run-pilot
```

### Generate Results & Figures
```bash
make evaluate
make plots
```

---

## 7. Project Structure

```text
agent-learning-pilot/
├── configs/                # Experiment configs and splits
├── data/tasks/             # 48 hand-crafted coding tasks across 4 families
├── docs/                   # Experiment design, methodology, limitations
├── examples/               # Article code snippets & demos
├── results/                # Raw logs, aggregated CSVs, generated figures
├── scripts/                # Evaluation & plot generation scripts
├── src/agent_learning/     # Main package source code
└── tests/                  # Unit and integration test suite
```

---

## 8. Limitations & Research Integrity

* **Controlled Pilot**: 48 tasks are designed for controlled pilot analysis and are not statistically definitive.
* **Compute Matching**: Tracked per-task via model call and token accounting limits.
* **No Pre-Determined Outcome**: Baseline, Reflection, Memory, or Workflow can win depending on the underlying model and task setup.
* **Research Integrity**: *No experimental result is reported unless it was produced by actually running the code.*
