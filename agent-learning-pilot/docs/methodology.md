# Methodology & Reproduction Guide

## 1. Environment Setup
```bash
git clone https://github.com/your-username/agent-learning-pilot.git
cd agent-learning-pilot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Reproducing Task Splits
```bash
PYTHONPATH=src python3 scripts/generate_splits.py --seed 42
```

## 3. Running the Mock Benchmark
```bash
PYTHONPATH=src python3 -m agent_learning --config configs/pilot.yaml --mock
```

## 4. Evaluating & Plotting
```bash
PYTHONPATH=src python3 scripts/run_evaluation.py
PYTHONPATH=src python3 scripts/generate_plots.py
```
Outputs are written to `results/aggregated/` and `results/figures/`.
