.PHONY: install test lint run-api run-frontend build-index collect-data docker-build docker-up clean

# --- Setup ---
install:
	pip install -r requirements.txt

# --- Development ---
run-api:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	streamlit run frontend/app.py --server.port 8501

# --- Data ---
collect-data:
	python scripts/collect_logs.py

build-index:
	python scripts/build_index.py

# --- Testing ---
test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/

lint-fix:
	ruff check src/ tests/ --fix

# --- Docker ---
docker-build:
	docker build -t devops-copilot .

docker-up:
	docker-compose -f docker/docker-compose.yml up --build

docker-down:
	docker-compose -f docker/docker-compose.yml down

# --- Cleanup ---
clean:
	rm -rf __pycache__ .pytest_cache htmlcov .coverage mlruns
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
