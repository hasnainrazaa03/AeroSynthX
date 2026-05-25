# Phase 5 — Workflow Orchestrator + Persistence

Target release: `v0.5.0`.
Status: Planned.

## Deliverables (summary)

- `src/aerosynthx/workflow/`: staged pipeline (`parse → validate →
  compute → geometry → case → package → persist`), per-stage logging,
  resumable reruns, run manifest with content hashes.
- SQLite-backed run/project store (SQLAlchemy).
- Filesystem artifact store, content-addressed.
- CLI: `aerosynthx run --intent "<text>" --out <dir>`.
