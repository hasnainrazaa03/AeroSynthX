# Phase 0 — Repository Bootstrap & Governance

Target release: `v0.0.1`.
Status: **Complete.**
Goal: Stand up a clean, opinionated repository ready for phased
development. **No engineering logic in this phase.**

---

## Acceptance Criteria

- [x] Repository structure laid out (`docs/`, `src/aerosynthx/`,
      `tests/`, `.github/`).
- [x] Python tooling configured: `pyproject.toml`, `ruff`, `mypy`,
      `pytest` — runnable against empty packages.
- [x] Pre-commit hooks configured.
- [x] GitHub Actions `ci.yml` runs lint + type-check + tests on push/PR
      and passes against the scaffold.
- [x] Governance docs present: `README.md`, `CONTRIBUTING.md`,
      `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`.
- [x] Issue templates + PR template under `.github/`.
- [x] `CHANGELOG.md` initialized in Keep-a-Changelog format.
- [x] All planning docs in place (`FEASIBILITY`, `ROADMAP`,
      `ENGINEERING_WORKFLOW`, `DOCUMENTATION_WORKFLOW`, `GITHUB_WORKFLOW`,
      `VERSIONING`, `RISKS`).
- [x] `.gitignore`, `.gitattributes`, `.editorconfig` in place.
- [x] `.env.example` placeholder created.
- [x] Git initialized; identity verified (`git var GIT_AUTHOR_IDENT`);
      initial commit on `main`; tag `v0.0.1` created (push deferred to
      first GitHub push).

---

## Task Checklist

### Repo skeleton
- [x] Create `docs/`, `docs/decisions/`, `docs/phases/`.
- [x] Create `src/aerosynthx/__init__.py` (empty package, version stub).
- [x] Create `tests/__init__.py` and a placeholder `tests/test_smoke.py`
      that asserts the package imports.

### Python tooling
- [x] Author `pyproject.toml` with project metadata, build backend, and
      tool configs for `ruff`, `mypy`, `pytest`.
- [x] Pin a target Python version (3.11+).
- [x] Use PEP 621 optional dependencies (`[project.optional-dependencies].dev`).
- [x] Verify `ruff check`, `ruff format --check`, `mypy`, `pytest -q`
      pass locally on the scaffold.

### Pre-commit
- [x] Add `.pre-commit-config.yaml` with: `ruff`, `ruff-format`,
      trailing whitespace, EOF fixer, YAML check, secret scan
      (`gitleaks`).

### GitHub
- [x] `.github/workflows/ci.yml` — lint + type + tests on push/PR.
- [x] `.github/ISSUE_TEMPLATE/bug_report.md`.
- [x] `.github/ISSUE_TEMPLATE/feature_request.md`.
- [x] `.github/ISSUE_TEMPLATE/task.md`.
- [x] `.github/PULL_REQUEST_TEMPLATE.md`.
- [x] `.github/dependabot.yml`.

### Governance docs
- [x] `README.md` — what AeroSynthX is, status banner, setup, links.
- [x] `CONTRIBUTING.md` — points to engineering workflow doc.
- [x] `CODE_OF_CONDUCT.md` — Contributor Covenant.
- [x] `SECURITY.md` — reporting channel and policy.
- [x] `LICENSE` — chosen license: **MIT** (default; reconfirm before push).
- [x] `CHANGELOG.md` — Keep a Changelog skeleton with `[Unreleased]` and
      `[0.0.1]` sections.

### Configuration
- [x] `.gitignore` — Python, venv, IDE, OS, OpenFOAM artifacts.
- [x] `.gitattributes` — text/eol policy.
- [x] `.editorconfig` — indent + EOL rules.
- [x] `.env.example` — placeholder for future env vars.

### Git
- [x] `git init -b main`.
- [x] Confirm local identity matches user-memory preference
      (`hasnainrazaa03`).
- [x] Initial commit: `chore(repo): phase 0 bootstrap`.
- [x] Annotated tag `v0.0.1` (push deferred until remote exists).

---

## Out of Scope for Phase 0

- Any `aerosynthx.physics`, `geometry`, `intent`, `openfoam`, `workflow`
  code.
- LLM integration of any kind.
- OpenFOAM templates.
- Web UI / FastAPI app.
- Docker / containerization.
- Coverage gates (informational only in this phase).

---

## Exit Review (completed)

1. `CHANGELOG.md` has a dated `[0.0.1]` section.
2. CI workflow defined; quality gates pass locally
   (`ruff check`, `ruff format --check`, `mypy`, `pytest -q`).
3. Tag `v0.0.1` created on the initial commit.
4. Ready to begin Phase 1.
