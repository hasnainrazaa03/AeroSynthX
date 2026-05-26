# Deferred Items & Phase 8 Backlog

This document collects every "out of scope" or "deferred" item carried
forward from Phases 1-7. Each entry lists the originating phase, a short
description, and a rough priority. Phase 8 will pick from the **P1**
items first.

## Priority key

- **P1** — Strong product value, unblocks new use-cases, scheduled next.
- **P2** — Nice-to-have or accuracy improvements; ship opportunistically.
- **P3** — Long-horizon; only after a clear customer / contributor ask.

## Open items

### Physics (Phase 1)
- **P2** Altitudes above 20 km (mesosphere model).
- **P2** Humidity / moist-air corrections to density and viscosity.
- **P2** Compressibility beyond ideal-gas (real-gas / high-Mach corrections).

### Geometry (Phase 2)
- **P2** NACA 5-digit airfoil family generator.

### Intent (Phase 3)
- **P1** LLM provider adapters (`aerosynthx.intent.llm`):
  - OpenAI / Azure / Ollama back-ends behind the existing protocol.
  - Deterministic offline fallback already exists; LLM path only adds
    coverage for ambiguous prose.
  - Configurable via env vars; no network calls by default.

### Workflow + CLI (Phase 5)
- **P1** LLM mode wired into `aerosynthx run --use-llm`.
- **P3** Executing OpenFOAM solvers (requires `simpleFoam` /
  `pisoFoam` availability and meshing; for now we only generate the
  case directory).
- **P2** Concurrency: parallel pipeline execution and per-run locking
  in the SQLite store.

### API + UI (Phase 6)
- **P1** Authentication / API keys.
- **P2** WebSocket / SSE streaming of stage progress.
- **P3** Multi-tenant scoping (per-user run isolation).
- **P3** SPA tooling (React/Vue) once UI complexity outgrows the
  current vanilla-JS bundle.

### Hardening / release (Phase 7)
- **P2** Container signing (cosign) and SBOM publication
  (CycloneDX / Syft).
- **P1** Auth / RBAC (paired with the Phase 6 auth item).
- **P1** LLM providers (paired with the Phase 3 item).
- **P2** WebSocket streaming (paired with the Phase 6 item).

## Phase 8 candidate

The highest-leverage P1 item is **LLM provider adapters with an opt-in
`aerosynthx run --use-llm` flag**, because it:

1. Unlocks the long-promised "natural-language to CFD case" promise
   for ambiguous prose that the offline parser cannot handle.
2. Is self-contained: it slots behind the existing `IntentParser`
   protocol without changing public APIs.
3. Pairs naturally with API auth (next), since LLM calls are the
   first place we genuinely need secret-management discipline.

Phase 8 plan will live at `docs/phases/PHASE_8.md`.
