.PHONY: install run test eval watch clean

install:
	pip install -r requirements.txt

run:
	uvicorn evalops.api:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

eval:
	python -m evalops.runner

watch:
	python -c "import sys; print('Watching golden_datasets/ for changes... (stub)')"
	# Placeholder for starting watchdog file watcher
	# python -m evalops.watcher

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f evalops.db
