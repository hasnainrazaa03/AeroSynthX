# AeroSynthX — Architecture (placeholder)

Status: **To be finalized in Phase 1.**

This document will describe:

- Module boundaries (`physics`, `geometry`, `intent`, `openfoam`,
  `workflow`, `api`, `ui`).
- Data contracts between modules (Pydantic models).
- Internal canonical SI representation and unit handling.
- Error model and exception taxonomy.
- Persistence layout (DB schema, artifact store).
- LLM provider abstraction.
- OpenFOAM template targeting strategy.
- Deployment topology.

It will be authored as the first deliverable of Phase 1. Any architectural
decisions made earlier (e.g., choosing the build backend in Phase 0) are
recorded as ADRs in `docs/decisions/` and will be summarized here when
Phase 1 begins.
