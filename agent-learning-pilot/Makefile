.PHONY: install test lint format run-mock run-pilot evaluate plots clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install package in development mode
	pip install -e ".[dev]"

test: ## Run all tests
	pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests only
	pytest tests/integration/ -v --tb=short

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=agent_learning --cov-report=term-missing

lint: ## Run linting
	ruff check src/ tests/
	mypy src/agent_learning/

format: ## Auto-format code
	ruff format src/ tests/
	ruff check --fix src/ tests/

run-mock: ## Run full experiment with mock model
	python -m agent_learning --config configs/pilot.yaml --mock

run-pilot: ## Run pilot experiment with local model
	python -m agent_learning --config configs/pilot.yaml

run-single: ## Run a single task (usage: make run-single TASK=dm_01)
	python -m agent_learning --config configs/pilot.yaml --task $(TASK) --mock

evaluate: ## Run evaluation on existing results
	python scripts/run_evaluation.py --results-dir results/

plots: ## Generate all figures
	python scripts/generate_plots.py --results-dir results/

splits: ## Regenerate task splits
	python scripts/generate_splits.py --seed 42

clean: ## Remove build artifacts and results
	rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
