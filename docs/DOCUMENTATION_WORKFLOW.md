# AeroSynthX — Documentation Workflow

Documentation is a first-class deliverable. A phase is not complete until
its documentation is updated.

---

## 1. Documentation Structure

```
docs/
├── FEASIBILITY.md            # one-time pre-implementation analysis
├── ROADMAP.md                # phase plan, source of truth for sequencing
├── ARCHITECTURE.md           # system architecture (filled in Phase 1)
├── ENGINEERING_WORKFLOW.md   # how we develop
├── DOCUMENTATION_WORKFLOW.md # this file
├── GITHUB_WORKFLOW.md        # branching, PR, CI/CD, releases
├── VERSIONING.md             # SemVer + release process
├── RISKS.md                  # living risk register
├── decisions/                # Architecture Decision Records (ADRs)
│   └── ADR-0001-<slug>.md
├── phases/                   # per-phase checklists & acceptance criteria
│   ├── PHASE_0.md
│   ├── PHASE_1.md
│   └── ...
└── reference/                # generated API docs, schemas, manifests (later)
```

Top-level (repo root):
- `README.md` — what AeroSynthX is, how to set up locally, links into
  `docs/`.
- `CHANGELOG.md` — Keep a Changelog format.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`.

---

## 2. Document Types

- **Reference** — APIs, schemas, file formats. Generated where possible.
- **Explanation** — architecture, design rationale, ADRs.
- **How-to** — task-oriented guides (e.g., "Run a NACA case end-to-end").
- **Tutorial** — onboarding, "first run" walk-through.

Each document states its type at the top in a single line.

---

## 3. Architecture Decision Records (ADRs)

Non-trivial technical decisions are recorded as ADRs in
`docs/decisions/`. Format:

```
# ADR-<NNNN>: <Title>

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded by ADR-XXXX | Rejected

## Context

## Decision

## Consequences
```

ADRs are immutable once accepted. Reversals create a new ADR that
supersedes the old one.

Examples of decisions that warrant an ADR:
- Choice of LLM provider abstraction.
- Choice of persistence layer.
- Choice of templating engine for OpenFOAM cases.
- Whether to embed solver execution in the platform.

---

## 4. When Docs Must Be Updated

| Change type | Required updates |
|---|---|
| New public function/module | API docstring + reference page |
| New CLI command/flag | README usage section + CLI reference |
| New env var | `.env.example` + config reference |
| New dependency | Justification in PR; if non-trivial, ADR |
| New architectural choice | ADR |
| Behavior change | Relevant how-to + `CHANGELOG.md` |
| Phase milestone reached | Phase checklist ticked + `CHANGELOG.md` |

PRs that touch behavior without updating docs are rejected.

---

## 5. Style Conventions

- US English.
- One sentence per line in source Markdown is **not** required; favor
  readability.
- Code samples must be runnable or clearly marked otherwise.
- Always state units when referring to physical quantities.
- No marketing language. This is engineering documentation.

---

## 6. Living Documents

These documents are updated continuously, not just at phase boundaries:

- `ROADMAP.md` (status column)
- `RISKS.md` (status, new risks)
- `CHANGELOG.md` (`[Unreleased]` section)
- Phase checklist files (ticking items)

These documents are updated at phase boundaries:

- `ARCHITECTURE.md` (when boundaries shift)
- `README.md` (when user-facing surface changes)
- ADRs (when decisions are made or revised)
