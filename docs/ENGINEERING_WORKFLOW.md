# AeroSynthX — Engineering Workflow

This document defines how engineering work is performed day-to-day.

---

## 1. Branching Model

We use a lightweight trunk-based model with short-lived feature branches.

- `main` — always green, always releasable. Protected.
- `feat/<short-topic>` — new functionality.
- `fix/<short-topic>` — bug fixes.
- `docs/<short-topic>` — documentation-only changes.
- `chore/<short-topic>` — tooling, CI, dependency bumps.
- `refactor/<short-topic>` — non-behavioral refactors.

Long-lived branches are not used. If work is too large for one PR, split it
into incremental PRs behind a feature flag or in a disabled module.

---

## 2. Commit Convention

Conventional Commits. The type prefix is mandatory and is what the
changelog tool keys off.

```
<type>(<scope>): <subject>

<body>

<footer>
```

Allowed types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`,
`ci`, `chore`, `revert`.

Scopes are package names (`physics`, `geometry`, `intent`, `openfoam`,
`workflow`, `api`, `ui`, `infra`, `docs`).

Examples:
- `feat(physics): add ISA atmosphere model`
- `fix(geometry): close NACA trailing edge within tolerance`
- `docs(roadmap): add phase 4 acceptance criteria`

Breaking changes are marked with `!` after the type or with a
`BREAKING CHANGE:` footer.

---

## 3. Pull Request Workflow

1. Open a branch from `main`.
2. Make focused changes. One logical change per PR.
3. Update tests in the same PR as the code.
4. Update docs in the same PR if behavior or interfaces change.
5. Update `CHANGELOG.md` under `## [Unreleased]`.
6. Open a PR using the PR template. Link to the relevant phase checklist
   item if applicable.
7. CI must be green.
8. At least one review approval required once the project has more than
   one contributor. Solo phase: self-review with a 24h cool-off for
   non-trivial PRs is encouraged.
9. Squash-merge with the PR title used as the commit subject.

---

## 4. Code Quality Bar

Every PR must satisfy:

- Formatter clean (`ruff format` / Prettier).
- Linter clean (`ruff check` / ESLint).
- Type checker clean (`mypy` strict on touched modules; TS strict).
- Tests added or updated; existing tests pass.
- Public functions have docstrings stating units, preconditions, and
  failure modes.
- No `# type: ignore`, `any`, or silent excepts without a written reason.
- No new top-level dependencies without justification in the PR
  description.

---

## 5. Testing Strategy

- **Unit tests** — pure-function level. Fast. Run on every push.
- **Property tests** — for physics and geometry (e.g., Hypothesis).
- **Golden-file tests** — for geometry coordinates and emitted case
  files. Snapshots committed.
- **Integration tests** — orchestrator end-to-end on a fixed intent.
- **Solver tests** — opt-in, gated behind a CI label / nightly job. Not
  required for PR merge.

Coverage gate: rising. Each phase declares its target.

---

## 6. Determinism Discipline

The engineering core must be deterministic. Anywhere randomness exists
(only justified for non-engineering concerns), it must:

- Accept an explicit `seed`.
- Default to a fixed seed.
- Be excluded from physics/geometry paths.

LLM calls are non-deterministic by nature; they are confined to the
intent-parsing layer and are required to produce schema-valid output.
Anything they emit that affects engineering values must be re-validated
or recomputed deterministically downstream.

---

## 7. Error Model

- Typed exceptions per package: `PhysicsError`, `GeometryError`,
  `IntentError`, `EnvelopeError`, `OpenFOAMError`.
- Boundary code converts exceptions to structured API errors with a
  stable `code` field.
- Never swallow exceptions silently. Log with context, then re-raise or
  convert.

---

## 8. Configuration & Secrets

- All runtime configuration via env vars, loaded through a single typed
  settings module.
- Secrets never committed. `.env.example` documents required variables.
- Pre-commit secret scanning enabled.

---

## 9. Dependencies

- Pin direct dependencies in `pyproject.toml` / `package.json` with
  conservative version ranges; lock with `uv.lock` / `package-lock.json`
  committed.
- Adding a dependency requires a one-line justification in the PR.
- Prefer the standard library and well-maintained, narrow libraries over
  large frameworks.

---

## 10. Definition of Done (per task)

A task is done when:

1. Code merged to `main`.
2. Tests cover the new behavior.
3. Docs reflect the new behavior.
4. `CHANGELOG.md` `[Unreleased]` updated.
5. Relevant phase checklist item ticked.
6. No new lint/type/test debt introduced.
