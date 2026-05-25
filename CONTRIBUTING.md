# Contributing to AeroSynthX

Thanks for your interest. Before contributing, please read:

- [docs/ENGINEERING_WORKFLOW.md](docs/ENGINEERING_WORKFLOW.md)
- [docs/DOCUMENTATION_WORKFLOW.md](docs/DOCUMENTATION_WORKFLOW.md)
- [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)
- [docs/VERSIONING.md](docs/VERSIONING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## TL;DR

1. Branch from `main`: `feat/<topic>`, `fix/<topic>`, etc.
2. Make one focused change. Add or update tests and docs in the same PR.
3. Update `CHANGELOG.md` under `## [Unreleased]`.
4. Use Conventional Commits in the PR title.
5. Open a PR using the template. Wait for green CI.
6. A PR that touches behavior without updating docs will not be merged.

## Local Quality Gates

```bash
ruff check .
ruff format --check .
mypy
pytest -q
```

## Reporting Bugs / Requesting Features

Use the relevant issue template under
`.github/ISSUE_TEMPLATE/`.

## Security

Do not file public issues for security problems. See [SECURITY.md](SECURITY.md).
