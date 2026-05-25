# Phase 0 — Repository Bootstrap & Governance

Target release: `v0.0.1`.
Goal: Stand up a clean, opinionated repository ready for phased
development. **No engineering logic in this phase.**

---

## Acceptance Criteria

- [ ] Repository structure laid out (`docs/`, `src/aerosynthx/`,
      `tests/`, `.github/`).
- [ ] Python tooling configured: `pyproject.toml`, `ruff`, `mypy`,
      `pytest` — runnable against empty packages.
- [ ] Pre-commit hooks configured.
- [ ] GitHub Actions `ci.yml` runs lint + type-check + tests on push/PR
      and passes against the scaffold.
- [ ] Governance docs present: `README.md`, `CONTRIBUTING.md`,
      `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`.
- [ ] Issue templates + PR template under `.github/`.
- [ ] `CHANGELOG.md` initialized in Keep-a-Changelog format.
- [ ] All planning docs in place (`FEASIBILITY`, `ROADMAP`,
      `ENGINEERING_WORKFLOW`, `DOCUMENTATION_WORKFLOW`, `GITHUB_WORKFLOW`,
      `VERSIONING`, `RISKS`).
- [ ] `.gitignore`, `.gitattributes`, `.editorconfig` in place.
- [ ] `.env.example` placeholder created.
- [ ] Git initialized; identity verified (`git var GIT_AUTHOR_IDENT`);
      initial commit on `main`; tag `v0.0.1` prepared (push deferred to
      first GitHub push).

---

## Task Checklist

### Repo skeleton
- [ ] Create `docs/`, `docs/decisions/`, `docs/phases/`.
- [ ] Create `src/aerosynthx/__init__.py` (empty package, version stub).
- [ ] Create `tests/__init__.py` and a placeholder `tests/test_smoke.py`
      that asserts the package imports.

### Python tooling
- [ ] Author `pyproject.toml` with project metadata, build backend, and
      tool configs for `ruff`, `mypy`, `pytest`.
- [ ] Pin a target Python version (3.11+).
- [ ] Add `requirements-dev.txt` or rely solely on PEP 621 optional
      dependencies (`[project.optional-dependencies].dev`). **Decision:
      PEP 621 extras.**
- [ ] Verify `ruff check`, `ruff format --check`, `mypy`, `pytest -q`
      pass locally on the scaffold.

### Pre-commit
- [ ] Add `.pre-commit-config.yaml` with: `ruff`, `ruff-format`,
      `mypy` (optional locally), trailing whitespace, EOF fixer, YAML
      check, secret scan (`detect-secrets` or `gitleaks`).

### GitHub
- [ ] `.github/workflows/ci.yml` — lint + type + tests on push/PR.
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md`.
- [ ] `.github/ISSUE_TEMPLATE/feature_request.md`.
- [ ] `.github/ISSUE_TEMPLATE/task.md`.
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`.
- [ ] `.github/dependabot.yml`.

### Governance docs
- [ ] `README.md` — what AeroSynthX is, status banner, setup, links.
- [ ] `CONTRIBUTING.md` — points to engineering workflow doc.
- [ ] `CODE_OF_CONDUCT.md` — Contributor Covenant.
- [ ] `SECURITY.md` — reporting channel and policy.
- [ ] `LICENSE` — chosen license (default proposal: **MIT**; subject to
      user confirmation before push).
- [ ] `CHANGELOG.md` — Keep a Changelog skeleton with `[Unreleased]`.

### Configuration
- [ ] `.gitignore` — Python, venv, IDE, OS, OpenFOAM artifacts.
- [ ] `.gitattributes` — text/eol policy.
- [ ] `.editorconfig` — indent + EOL rules.
- [ ] `.env.example` — placeholder for future env vars.

### Git
- [ ] `git init -b main`.
- [ ] Confirm local identity matches user-memory preference
      (`hasnainrazaa03`).
- [ ] Initial commit: `chore(repo): phase 0 bootstrap`.
- [ ] Prepare annotated tag `v0.0.1` (push deferred until remote exists).

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

## Exit Review

When all boxes are checked:

1. Add a Phase 0 entry to `CHANGELOG.md` under a new `[0.0.1]` section.
2. Confirm CI green on `main`.
3. Tag `v0.0.1`.
4. Move on to Phase 1.
