# my-package

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

One or two sentences on what this project does and who it is for.

## Installation

```bash
pip install my-package
```

## Usage

```python
from my_package import greet

print(greet("World"))  # Hello, World!
```

## Development

Requires Python 3.10+.

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
make install                   # installs dev dependencies and pre-commit hooks
```

Common tasks:

| Command          | What it does                      |
| ---------------- | --------------------------------- |
| `make test`      | Run tests with coverage           |
| `make lint`      | Ruff lint and format check        |
| `make format`    | Auto-fix lint issues and format   |
| `make typecheck` | Run mypy in strict mode           |
| `make check`     | Run lint, typecheck, and tests    |

## Project structure

```
.
├── src/my_package/   # package source (src layout)
├── tests/            # pytest tests
├── docs/             # extra documentation
├── scripts/          # helper scripts
└── pyproject.toml    # packaging and tool config
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities per [SECURITY.md](SECURITY.md).

## License

Released under the [MIT License](LICENSE).
