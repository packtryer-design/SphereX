.PHONY: install lint format typecheck test check clean serve web objects warm host

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

# The whole app (API + front end) on http://localhost:8000
serve:
	python -m uvicorn api.main:app --reload --port 8000

# Host the API for the public site from this computer (docs/HOSTING.md). Ctrl+C to stop
host:
	python scripts/host.py

# Front end only (catalog and About work; images need `make serve`)
web:
	python -m http.server 8080 --directory web

# Rebuild web/data/objects.json from SIMBAD + IRSA
objects:
	python scripts/build_objects.py

# Pre-build images for every catalog object so the demo never waits on IRSA
warm:
	python scripts/warm_cache.py
