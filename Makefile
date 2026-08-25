.PHONY: install test lint format docker-build compose-delitos compose-aire run-cluster clean

install:
	pip install -e .
	pip install pytest pytest-asyncio ruff

test:
	pytest -q tests/

lint:
	ruff check .

format:
	ruff check --fix .
	ruff format .

docker-build:
	docker build -t civicmesh:latest .

compose-delitos:
	docker compose --profile delitos up --build

compose-aire:
	docker compose --profile aire up --build

run-cluster:
	sbatch scripts/slurm/run_cluster.slurm

clean:
	rm -rf __pycache__ .pytest_cache civicmesh/__pycache__ tests/__pycache__
