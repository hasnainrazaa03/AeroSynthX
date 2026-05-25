# Phase 4 — OpenFOAM Case Generation

Target release: `v0.4.0`.
Status: Planned. Detailed checklist authored when Phase 3 closes.

## Deliverables (summary)

- `src/aerosynthx/openfoam/`:
  - Jinja2 template set targeting a pinned OpenFOAM version.
  - First template: 2D incompressible RANS (`simpleFoam`, `kOmegaSST`)
    with blockMesh-based domain.
  - Envelope guard rejecting out-of-envelope intents.
  - Case packaging with manifest.
