.PHONY: install lint format typecheck test check clean web demo-data

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

web:
	python -m http.server 8080 --directory web

demo-data:
	python web/data/make_demo_field.py
