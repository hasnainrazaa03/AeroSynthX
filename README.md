# AeroSynthX

> AI-assisted aerodynamic design and CFD orchestration platform.

**Status:** Phase 0 — repository bootstrap. No engineering functionality yet.

AeroSynthX converts natural-language aerodynamic intent into validated
engineering parameters, deterministic airfoil geometry, and OpenFOAM-ready
case files.

The LLM is restricted to interpretation and orchestration assistance.
All engineering values, geometry, and simulation configuration are produced
by deterministic, tested code paths. The platform never fabricates physics
values.

---

## Quick Links

- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Feasibility analysis: [docs/FEASIBILITY.md](docs/FEASIBILITY.md)
- Architecture (placeholder; finalized in Phase 1): [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Engineering workflow: [docs/ENGINEERING_WORKFLOW.md](docs/ENGINEERING_WORKFLOW.md)
- Documentation workflow: [docs/DOCUMENTATION_WORKFLOW.md](docs/DOCUMENTATION_WORKFLOW.md)
- GitHub workflow: [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)
- Versioning: [docs/VERSIONING.md](docs/VERSIONING.md)
- Risk register: [docs/RISKS.md](docs/RISKS.md)
- Current phase: [docs/phases/PHASE_0.md](docs/phases/PHASE_0.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

---

## What This Is (and Isn't)

**It is** an engineering platform built incrementally with production
discipline: phased delivery, documentation-first development, testing,
versioning, and CI from day one.

**It isn't** a hackathon demo, a chat wrapper around an LLM, or a tool
that lets a language model invent engineering numbers.

---

## Operating Envelope (v0.x target)

The first end-to-end vertical slice intentionally stays narrow:

- Flow: incompressible, low subsonic (Ma < 0.3).
- Geometry: NACA 4-digit airfoils.
- Domain: 2D (extruded one cell in span for OpenFOAM).
- Mesh: blockMesh-based.
- Solver: `simpleFoam` with `kOmegaSST`.
- Output: generated case files only; solver execution is out of scope
  for v0.x.

Anything outside this envelope is explicitly rejected with a clear error.
See [docs/FEASIBILITY.md](docs/FEASIBILITY.md).

---

## Local Setup (Phase 0)

> Requires Python 3.11+.

```bash
# Clone
git clone <repo-url> aerosynthx
cd aerosynthx

# Create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dev dependencies (empty package — bootstrap only)
pip install -e ".[dev]"

# Run quality gates
ruff check .
ruff format --check .
mypy
pytest -q
```

There is no CLI or service to run yet. That arrives in Phase 5 / Phase 6.

---

## Repository Layout

```
.
├── docs/                       # planning, architecture, phases, ADRs
├── src/aerosynthx/             # Python package (empty in Phase 0)
├── tests/                      # tests (smoke-only in Phase 0)
├── .github/                    # CI workflows, issue/PR templates
├── pyproject.toml              # project + tooling config
├── CHANGELOG.md
└── README.md
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/ENGINEERING_WORKFLOW.md](docs/ENGINEERING_WORKFLOW.md).

Security disclosures: [SECURITY.md](SECURITY.md).

---

## License

MIT — see [LICENSE](LICENSE).
