# Phase 3 — Intent Parsing Layer

Target release: `v0.3.0`.
Status: Planned. Detailed checklist authored when Phase 2 closes.

## Deliverables (summary)

- `src/aerosynthx/intent/`:
  - Pydantic schemas: `DesignIntent`, `Assumption`, `ParseResult`.
  - Provider-agnostic LLM client interface.
  - Structured-output parser with retry-on-invalid.
  - Provenance tagging (`user_provided` / `inferred`).
  - Offline deterministic fallback parser for tests (no network).
- Strict rule: LLM never emits engineering values; physics is recomputed
  downstream.
