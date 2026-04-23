PYTHON ?= python3

.PHONY: help setup dev docker-build docker-run clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

setup: ## Create venv and install dependencies
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r requirements.txt

dev: ## Start dev server with reload
	$(PYTHON) -m uvicorn src.backend.main:app --reload --host 0.0.0.0 --port 8001

docker-build: ## Build Docker image
	docker build -t wc-simulator:latest .

docker-run: ## Run Docker container
	docker run -p 8001:8000 -v wc-sim-data:/app/data wc-simulator:latest

clean: ## Delete caches and DB
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f data/wc_simulator.db
