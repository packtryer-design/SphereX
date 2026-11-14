.PHONY: install lint format typecheck test check clean

install:
	python -m pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy

test:
	pytest

check: lint typecheck test

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov *.egg-info
