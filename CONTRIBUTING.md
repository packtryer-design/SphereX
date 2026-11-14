# Contributing

Thanks for taking the time to contribute.

## Ground rules

- Be respectful. See the [Code of Conduct](CODE_OF_CONDUCT.md).
- Search existing issues and pull requests before opening a new one.
- For large changes, open an issue first so we can agree on the approach.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/REPO.git
cd REPO
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
make install
```

`make install` installs the package in editable mode with dev dependencies and enables the pre-commit hooks.

## Workflow

1. Create a branch from `main`:
   ```bash
   git checkout -b feat/short-description
   ```
2. Make your changes, with tests and docs where relevant.
3. Run all checks locally:
   ```bash
   make check
   ```
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: add export option`
   - `fix: handle empty input`
   - `docs: clarify install steps`
5. Push and open a pull request against `main`.

## Code standards

- Formatting and linting: [Ruff](https://docs.astral.sh/ruff/) (`make format`)
- Types: all code in `src/` must pass `mypy --strict`
- Tests: [pytest](https://docs.pytest.org/); add tests for every bug fix and feature
- Public functions and classes need docstrings

## Pull request checklist

- [ ] Change is focused and as small as practical
- [ ] Tests added or updated
- [ ] `make check` passes
- [ ] Docs and changelog updated if behavior changed

## Security issues

Do not open a public issue. See [SECURITY.md](SECURITY.md).
