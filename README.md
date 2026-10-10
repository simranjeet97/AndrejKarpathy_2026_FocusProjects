<![CDATA[<div align="center">

# 🧠 Andrej Karpathy 2026 — AI Systems Engineering

**From flashy demos → production-grade autonomous systems**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-000000?logo=ollama&logoColor=white)](https://ollama.com)
[![Google ADK](https://img.shields.io/badge/Google_ADK-Agent_SDK-4285F4?logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*8 production-grade projects • 33,600+ lines of Python • 437 source files • All local, all free*

</div>

---

## 🎯 What Is This?

A hands-on engineering curriculum inspired by [Andrej Karpathy's 2026 roadmap](https://x.com/karpathy) focused on the **boring things that actually compound** in modern AI systems:

| Skill | Where You Learn It |
|---|---|
| **Context Engineering** | CodeLensAI — deciding *what* context matters for a PR review |
| **Tool Design** | QueryForge — building narrow, safe, composable tools |
| **Agent Orchestration** | VentureMind — coordinating 5 specialist agents |
| **Eval Discipline** | EvalOps — CI/CD for prompts with regression detection |
| **Agent Learning** | Agent Learning Pilot — measuring if agents improve with feedback |
| **Reliability Engineering** | FailSafe Agent — circuit breakers, fallback models, audit trails |
| **Harness Engineering** | AutoForge — sandboxed code execution with verification loops |
| **Full-Stack AI Ops** | SentinelOps — all of the above in one capstone system |

Every project runs **100% locally** using Ollama — no paid API keys required.

---

## 📐 Architecture Overview

```mermaid
graph TB
    subgraph "Project 1: EvalOps"
        E1["Golden Datasets"] --> E2["Eval Runner"]
        E2 --> E3["LLM-as-Judge + Scoring"]
        E3 --> E4["Regression Engine"]
        E4 --> E5["Dashboard :8000"]
    end

    subgraph "Project 2: QueryForge"
        Q1["Natural Language Query"] --> Q2["Tool Router"]
        Q2 --> Q3["SQL / Web / PDF / API"]
        Q3 --> Q4["Result Synthesis"]
        Q4 --> Q5["Dashboard :8001"]
    end

    subgraph "Project 3: VentureMind"
        V1["Startup Name"] --> V2["Orchestrator"]
        V2 --> V3["Market + Competitor + Finance + Legal + Summary Agents"]
        V3 --> V4["Due Diligence Report"]
        V4 --> V5["Dashboard :8002"]
    end

    subgraph "Project 4: CodeLensAI"
        C1["PR / Code Diff"] --> C2["Context Packer"]
        C2 --> C3["Review Agent"]
        C3 --> C4["Feedback + Scores"]
        C4 --> C5["Dashboard :8003"]
    end

    subgraph "Project 5: Agent Learning Pilot"
        A1["Benchmark Tasks"] --> A2["Agent + Feedback Loop"]
        A2 --> A3["Retention + Transfer Analysis"]
        A3 --> A4["Dashboard :8004"]
    end

    subgraph "Project 6: FailSafe Agent"
        F1["Support Request"] --> F2["Circuit Breaker"]
        F2 --> F3["Primary / Fallback LLM"]
        F3 --> F4["SHA-256 Audit Ledger"]
        F4 --> F5["Dashboard :8005"]
    end

    subgraph "Project 7: AutoForge"
        AF1["GitHub Issue"] --> AF2["Code Agent"]
        AF2 --> AF3["Sandbox Execution"]
        AF3 --> AF4["Test + Verify"]
        AF4 --> AF5["Dashboard :8006"]
    end

    subgraph "Project 8: SentinelOps ★"
        S1["Incident Alert"] --> S2["Multi-Agent Orchestrator"]
        S2 --> S3["Log + Metrics + Runbook Tools"]
        S3 --> S4["Resolution + Escalation"]
        S4 --> S5["Dashboard :8007"]
    end
```

---

## 🗂️ Project Catalog

### 1️⃣ EvalOps — LLM Regression Testing Platform

> **CI/CD for your prompts and AI agents.**

| | |
|---|---|
| **Port** | `8000` |
| **Core Skill** | Eval Discipline |
| **Key Features** | Golden datasets, LLM-as-judge, pairwise comparison, regression detection, human feedback loop |
| **Tech** | FastAPI, Ollama, SQLite, Chart.js, Watchdog |
| **Lines** | 3,301 across 25 files |

**What it does:** Run benchmark evaluations against any local LLM model. Score outputs with both deterministic scoring (Jaccard, exact match) and LLM-as-judge. Detect regressions automatically when prompt changes degrade quality. Review everything in a live dashboard.

```bash
cd EvalOps && pip install -r requirements.txt
make seed && make run    # → http://localhost:8000/dashboard
```

---

### 2️⃣ QueryForge — Multi-Tool Research Agent

> **Ask a question, the agent picks the tools.**

| | |
|---|---|
| **Port** | `8001` |
| **Core Skill** | Tool Design |
| **Key Features** | SQL query generation, web search, PDF summarization, chart rendering, tool selection reasoning |
| **Tech** | Google ADK, FastAPI, Ollama, aiosqlite, matplotlib |
| **Lines** | 3,821 across 34 files |

**What it does:** Type a natural language question like *"Find our highest churn customer segment and compare it with industry trends."* The agent decides which tools to call (SQL, web search, PDF reader, API), executes them in the right order, and synthesizes a coherent answer.

```bash
cd queryforge && pip install -e ".[dev]"
uvicorn src.api.main:app --port 8001 --reload  # → http://localhost:8001
```

---

### 3️⃣ VentureMind — Startup Due Diligence Multi-Agent System

> **5 specialist agents analyze a startup before investment.**

| | |
|---|---|
| **Port** | `8002` |
| **Core Skill** | Agent Orchestration |
| **Key Features** | Parallel agent execution, market research, competitor analysis, financial modeling, legal review, report synthesis |
| **Tech** | Google ADK, FastAPI, Ollama, aiosqlite |
| **Lines** | 6,605 across 51 files |

**What it does:** Provide a startup name and description. Five specialized agents (Market Research, Competitor Analysis, Financial Analysis, Legal Review, Summarization) run in parallel, share findings, and produce a comprehensive due diligence report.

```bash
cd VentureMind && pip install -e ".[dev]"
python scripts/seed_demo_samples.py
uvicorn src.api.app:app --port 8002 --reload  # → http://localhost:8002
```

---

### 4️⃣ CodeLensAI — Autonomous PR Review Agent

> **AI reviewer that knows what context matters.**

| | |
|---|---|
| **Port** | `8003` |
| **Core Skill** | Context Engineering |
| **Key Features** | Code diff analysis, context compression, review scoring, security/performance flags, review history |
| **Tech** | FastAPI, Ollama, SQLite |
| **Lines** | 4,238 across 34 files |

**What it does:** Paste a code diff or connect a repo. The agent analyzes changed files, retrieves relevant architecture docs and coding standards, compresses context to fit the model window, and produces a detailed code review with scores for correctness, security, and maintainability.

```bash
cd CodeLensAI && pip install -e ".[dev]"
python codelens/scripts/seed_demo_reviews.py
uvicorn codelens.src.api.main:app --port 8003 --reload  # → http://localhost:8003
```

---

### 5️⃣ Agent Learning Pilot — Can Agents Learn From Feedback?

> **A controlled experiment measuring agent improvement over time.**

| | |
|---|---|
| **Port** | `8004` |
| **Core Skill** | Agent Learning & Evaluation |
| **Key Features** | Controlled A/B experiments, retention curves, transfer learning analysis, cost-vs-capability tracking |
| **Tech** | FastAPI, Ollama, pandas, matplotlib |
| **Lines** | 4,759 across 189 files |

**What it does:** Runs controlled experiments to measure whether coding agents genuinely improve when given structured feedback. Tracks retention (do improvements stick?), transfer (do improvements generalize?), and cost-effectiveness across experiment conditions.

```bash
cd agent-learning-pilot && pip install -e ".[dev]"
python scripts/serve_results.py 8004  # → http://localhost:8004
```

---

### 6️⃣ FailSafe Agent — Resilient AI Support Agent

> **When the model fails, the system doesn't.**

| | |
|---|---|
| **Port** | `8005` |
| **Core Skill** | Reliability Engineering |
| **Key Features** | Circuit breakers, fallback LLM chains, retry with exponential backoff, SHA-256 audit ledger, human escalation |
| **Tech** | FastAPI, Ollama, SQLite, hashlib |
| **Lines** | 5,317 across 54 files |

**What it does:** A customer support agent that handles refund requests, policy lookups, and payment actions — but with production-grade resilience. If the primary LLM times out, a circuit breaker trips and falls back to a smaller model. Every action is logged in a cryptographic audit ledger with SHA-256 hash chaining.

```bash
cd failsafe-agent && pip install -e ".[dev]"
uvicorn src.main:app --port 8005 --reload  # → http://localhost:8005
```

---

### 7️⃣ AutoForge — Autonomous Software Engineering Sandbox

> **Agent writes code, sandbox runs it, tests verify it.**

| | |
|---|---|
| **Port** | `8006` |
| **Core Skill** | Harness Engineering |
| **Key Features** | Issue-to-PR pipeline, sandboxed code execution, test verification loops, artifact logging, rollback |
| **Tech** | FastAPI, Ollama, SQLite, subprocess isolation |
| **Lines** | 4,747 across 41 files |

**What it does:** Feed it a GitHub issue description. The agent generates code, runs it in an isolated sandbox, validates outputs against tests, and produces a verified artifact. If tests fail, it iterates. The surrounding harness (sandboxing, verification, artifact logging) matters more than the model itself.

```bash
cd autoforge && pip install -e ".[dev]"
python scripts/seed_demo_tasks.py
uvicorn src.main:app --port 8006 --reload  # → http://localhost:8006
```

---

### 8️⃣ SentinelOps — AI DevOps Incident Response ★ Capstone

> **Everything from projects 1–7, combined into one production system.**

| | |
|---|---|
| **Port** | `8007` |
| **Core Skill** | Full-Stack AI Systems Engineering |
| **Key Features** | Multi-agent investigation, log analysis, metrics querying, runbook search, escalation logic, cryptographic audit ledger |
| **Tech** | FastAPI, Ollama, SQLite, SHA-256 hash chaining |
| **Lines** | 847 across 9 files |

**What it does:** Detects infrastructure incidents, then orchestrates a multi-agent investigation: one agent triages severity, another pulls logs, another queries metrics, another searches runbooks. The orchestrator synthesizes findings into a resolution plan or escalates to a human. Every step is recorded in an immutable audit ledger.

```bash
cd SentinelOps && pip install -e ".[dev]"
python scripts/seed_incidents.py
uvicorn src.main:app --port 8007 --reload  # → http://localhost:8007
```

---

## 🚀 Quick Start (All Projects)

### Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Runtime |
| **Ollama** | Latest | Local LLM inference |
| **qwen2.5:7b** | — | Default model for all projects |

### 1. Install Ollama & pull the model

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# Pull the default model
ollama pull qwen2.5:7b
```

### 2. Clone & run any project

```bash
git clone https://github.com/simranjeet97/AndrejKarpathy_2026_FocusProjects.git
cd AndrejKarpathy_2026_FocusProjects

# Pick a project, e.g. EvalOps
cd EvalOps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # or: pip install -e ".[dev]"

# Seed demo data (if available)
make seed  # or: python scripts/seed_*.py

# Start the server
make run   # or: uvicorn ... --port 8000 --reload
```

### 3. Open the dashboard

Each project serves a web dashboard on its assigned port:

| Project | URL |
|---|---|
| EvalOps | [http://localhost:8000/dashboard](http://localhost:8000/dashboard) |
| QueryForge | [http://localhost:8001](http://localhost:8001) |
| VentureMind | [http://localhost:8002](http://localhost:8002) |
| CodeLensAI | [http://localhost:8003](http://localhost:8003) |
| Agent Learning Pilot | [http://localhost:8004](http://localhost:8004) |
| FailSafe Agent | [http://localhost:8005](http://localhost:8005) |
| AutoForge | [http://localhost:8006](http://localhost:8006) |
| SentinelOps | [http://localhost:8007](http://localhost:8007) |

---

## 🏗️ Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│   HTML + CSS + Chart.js   │   FastAPI Jinja2 Templates      │
├─────────────────────────────────────────────────────────────┤
│                       API Layer                             │
│   FastAPI (async)   │   REST endpoints   │   CORS enabled   │
├─────────────────────────────────────────────────────────────┤
│                    Agent / Logic Layer                       │
│   Google ADK   │   Custom Orchestrators   │   Tool Router    │
├─────────────────────────────────────────────────────────────┤
│                     LLM Inference                           │
│   Ollama (local)   │   qwen2.5:7b   │   Fallback chains     │
├─────────────────────────────────────────────────────────────┤
│                      Storage Layer                          │
│   SQLite (zero infra)   │   SHA-256 audit ledgers           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
AndrejKarpathy_2026_FocusProjects/
├── EvalOps/                    # Project 1: LLM Regression Testing
│   ├── evalops/                #   Core library (runner, scorer, judge, etc.)
│   ├── golden_datasets/        #   Benchmark task definitions
│   ├── templates/              #   Dashboard HTML
│   └── tests/                  #   26 pytest tests
│
├── queryforge/                 # Project 2: Multi-Tool Research Agent
│   └── src/
│       ├── agent/              #   Agent logic & tool router
│       ├── tools/              #   SQL, web, PDF, chart tools
│       └── api/                #   FastAPI endpoints + dashboard
│
├── VentureMind/                # Project 3: Multi-Agent Due Diligence
│   └── src/
│       ├── agents/             #   5 specialist agents
│       ├── orchestrator/       #   Parallel coordination
│       └── report/             #   Report generation
│
├── CodeLensAI/                 # Project 4: PR Review Agent
│   └── codelens/
│       └── src/
│           ├── api/            #   Endpoints + dashboard
│           └── agents/         #   Review agent + context packer
│
├── agent-learning-pilot/       # Project 5: Agent Learning Experiments
│   └── src/
│       └── agent_learning/     #   Experiment runner + analysis
│
├── failsafe-agent/             # Project 6: Resilient Support Agent
│   └── src/
│       ├── resilience/         #   Circuit breaker, fallback LLM
│       ├── policy/             #   Support policies
│       └── observability/      #   Logging + metrics
│
├── autoforge/                  # Project 7: Autonomous SWE Sandbox
│   └── src/
│       ├── harness/            #   Sandbox execution engine
│       ├── guardrails/         #   Safety checks
│       └── agent/              #   Code generation agent
│
├── SentinelOps/                # Project 8: DevOps Incident Response ★
│   └── src/
│       ├── agents/             #   Multi-agent orchestrator
│       ├── tools/              #   Log, metrics, runbook tools
│       └── database.py         #   Audit ledger with hash chaining
│
├── .gitignore
└── README.md                   # ← You are here
```

---

## 🧭 Recommended Learning Path

```mermaid
graph LR
    A["1. EvalOps<br/>Eval Discipline"] --> B["2. QueryForge<br/>Tool Design"]
    B --> C["3. VentureMind<br/>Orchestration"]
    C --> D["4. CodeLensAI<br/>Context Engineering"]
    D --> E["5. Agent Learning<br/>Feedback Loops"]
    E --> F["6. FailSafe<br/>Reliability"]
    F --> G["7. AutoForge<br/>Harness Engineering"]
    G --> H["8. SentinelOps ★<br/>Everything Combined"]

    style H fill:#f59e0b,stroke:#d97706,color:#000
```

Each project builds on skills from the previous ones. By the time you reach SentinelOps, you've practiced every production AI engineering pattern.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with 🧠 by [Simranjeet Singh](https://github.com/simranjeet97)**

*"These projects move you from building flashy demos to building production-grade AI systems that companies actually need."*
— Andrej Karpathy

</div>
]]>
