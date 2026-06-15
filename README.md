# AeroSynthX

> AI-assisted aerodynamic design and CFD orchestration platform.

**Status:** Phase 25 — XFOIL integration for fast analysis.

AeroSynthX converts natural-language aerodynamic intent into validated
engineering parameters, deterministic airfoil geometry, and simulation-ready
case files for OpenFOAM or rapid analysis with XFOIL.

The LLM is restricted to interpretation and orchestration assistance.
All engineering values, geometry, and simulation configuration are produced
by deterministic, tested code paths. The platform never fabricates physics
values.

---

## Quick Links

- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Engineering Workflow: [docs/ENGINEERING_WORKFLOW.md](docs/ENGINEERING_WORKFLOW.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

---

## Core Features

- **Multi-Fidelity Analysis**: Choose between high-fidelity CFD with OpenFOAM or rapid, low-fidelity analysis with the integrated XFOIL solver.
- **Flexible Geometry Engine**: Supports standard NACA 4-digit and 5-digit airfoils, or provide your own custom airfoil coordinates.
- **Intent-Driven Workflow**: Describe your desired simulation in natural language (e.g., "NACA 23012 at Mach 0.2, 5 degrees alpha, 10km altitude").
- **Deterministic Core**: The engineering core is fully deterministic and tested, ensuring reproducibility.
- **REST API & Web UI**: A clean, modern API and a simple web interface for running and managing simulations.

---

## Operating Envelope

- **Flow**: Incompressible, low subsonic (Ma < 0.3).
- **Geometry**:
    - NACA 4-digit airfoils
    - NACA 5-digit airfoils (non-reflex)
    - Custom user-supplied coordinates
- **Analysis Modes**:
    - **`openfoam`**: Generates a 2D (extruded) case for `simpleFoam` with `kOmegaSST`.
    - **`xfoil`**: Provides rapid Cl, Cd, and Cm estimates (requires `xfoil` in `PATH`).
- **Output**: Generated case files or aerodynamic coefficients.

---

## Local Setup

> Requires Python 3.11+ and optionally, `xfoil` installed and in your `PATH`.

```bash
# Clone
git clone <repo-url> aerosynthx
cd aerosynthx

# Create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run quality gates
ruff check .
ruff format --check .
mypy
pytest -q
```

### Running the CLI

```bash
# Run a high-fidelity OpenFOAM case generation
aerosynthx run --intent "NACA 0012 at 30 m/s, 2 deg alpha" --out ./work

# Run a fast XFOIL analysis
aerosynthx run --intent "NACA 0012 at 30 m/s, 2 deg alpha" --out ./work --mode xfoil
```

### Running the Web UI

```bash
# Start the FastAPI server
aerosynthx serve --out ./work
```
Navigate to `http://127.0.0.1:8000` in your browser.

---

## Repository Layout

```
.
├── docs/                       # Planning, architecture, phases, ADRs
├── src/aerosynthx/             # Python package
├── tests/                      # Test suite
├── .github/                    # CI workflows, issue/PR templates
├── pyproject.toml              # Project + tooling config
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
