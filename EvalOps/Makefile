.PHONY: install setup-ollama run test eval watch seed report clean

# ─── Install ──────────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

# ─── Ollama Setup ─────────────────────────────────────────────────────────────
setup-ollama:
	chmod +x scripts/setup_ollama.sh
	./scripts/setup_ollama.sh

# ─── Run API Server ───────────────────────────────────────────────────────────
run:
	uvicorn evalops.api:app --reload --port 8000

# ─── Run Tests ────────────────────────────────────────────────────────────────
test:
	MOCK_OLLAMA=true pytest tests/ -v --tb=short

# ─── Run Evaluation ───────────────────────────────────────────────────────────
eval:
	mkdir -p results
	python3 -m evalops.runner --dataset golden_datasets/example_dataset.json --model qwen2.5:7b --output results/latest.json

# ─── File Watcher ─────────────────────────────────────────────────────────────
watch:
	python3 -m evalops.watcher --watch-dir .

# ─── Seed Database ────────────────────────────────────────────────────────────
seed:
	python3 scripts/seed_db.py

# ─── Print Last Report ────────────────────────────────────────────────────────
report:
	python3 -c "import evalops; evalops.print_last_report()"

# ─── Clean ────────────────────────────────────────────────────────────────────
clean:
	rm -f evalops.db
	rm -f results/*.json
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache
