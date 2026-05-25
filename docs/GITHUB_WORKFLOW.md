# AeroSynthX — GitHub Workflow

How we use GitHub as the system of record for code, reviews, releases, and
automation.

---

## 1. Repository Settings (target)

These are the desired settings once the repo is pushed:

- Default branch: `main`.
- Branch protection on `main`:
  - Require PR before merging.
  - Require status checks (`ci`) to pass.
  - Require linear history (squash merges).
  - Disallow force-pushes.
  - Disallow direct deletion.
- Merge strategy: **squash only**.
- Automatically delete head branches after merge.
- Issues enabled. Discussions optional.
- Dependabot enabled for `pip` and `github-actions`.
- Secret scanning + push protection enabled.

---

## 2. Issues

- Use issue templates:
  - `bug_report.md` — reproducible defect.
  - `feature_request.md` — capability addition.
  - `task.md` — internal engineering work tied to a phase checklist.
- Labels:
  - Type: `type:bug`, `type:feat`, `type:docs`, `type:chore`,
    `type:refactor`, `type:test`, `type:security`.
  - Phase: `phase:0` … `phase:7`.
  - Area: `area:physics`, `area:geometry`, `area:intent`,
    `area:openfoam`, `area:workflow`, `area:api`, `area:ui`,
    `area:infra`.
  - Priority: `prio:p0`, `prio:p1`, `prio:p2`, `prio:p3`.
- Every PR references at least one issue (`Closes #N` / `Refs #N`).

---

## 3. Pull Requests

- Use the PR template.
- Title follows Conventional Commits.
- Description states: what changed, why, how it was tested, doc impact.
- Link the phase checklist item being advanced.
- PR must be green on CI before review.
- Squash-merge with the PR title as the resulting commit subject.

---

## 4. CI/CD

GitHub Actions is the CI provider.

Workflows live under `.github/workflows/`:

- `ci.yml` — runs on push to `main` and on every PR:
  - lint (`ruff check`)
  - format check (`ruff format --check`)
  - type check (`mypy`)
  - tests (`pytest -q`)
  - coverage report (informational in Phase 0; enforced from Phase 1).
- `release.yml` — runs on pushing a tag matching `v*.*.*`:
  - builds artifacts
  - generates release notes from `CHANGELOG.md`
  - publishes a GitHub Release
  - (later) publishes container images.
- `docs.yml` — runs link checking and Markdown lint on docs changes.
- `codeql.yml` — security scanning (added in Phase 7 or earlier if cheap).

CI must run on a pinned OS version and pinned Python version per a build
matrix defined in `ci.yml`.

---

## 5. Releases & Tags

- Tags follow SemVer: `vMAJOR.MINOR.PATCH` (see `VERSIONING.md`).
- A release is created by:
  1. Updating `CHANGELOG.md`: move items from `[Unreleased]` into a new
     dated, versioned section.
  2. Bumping the version in `pyproject.toml`.
  3. Committing on `main` via PR (`chore(release): vX.Y.Z`).
  4. Tagging the merge commit: `git tag vX.Y.Z && git push --tags`.
  5. `release.yml` builds artifacts and publishes the Release.

No release is cut directly from a feature branch.

---

## 6. Security

- `SECURITY.md` documents how to report vulnerabilities.
- Dependabot PRs are reviewed weekly.
- Secret scanning + push protection on.
- No secrets in code, in CI logs, or in test fixtures.

---

## 7. Project Management

- GitHub Projects board with columns: `Backlog`, `Ready`, `In Progress`,
  `In Review`, `Done`.
- Phase checklist files (`docs/phases/PHASE_<N>.md`) are the source of
  truth for what "done" looks like for each phase; issues track *who* is
  doing *what* now.

---

## 8. Bot & Automation Etiquette

- Bots may open PRs (Dependabot). They must still pass CI.
- Auto-merge is disabled. A human merges every PR.
- Release notes are generated from the changelog, not from commit titles
  directly — the changelog is the curated source.
