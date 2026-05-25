# Phase 2 — Geometry Engine

Target release: `v0.2.0`.
Status: **In progress.**
Goal: Deterministic airfoil geometry generation, validation, export, and
visualization. Independent of the LLM and the OpenFOAM layer.

---

## Acceptance Criteria

- [x] `aerosynthx.geometry` package implemented:
  - [x] `errors` — `GeometryError` rooted under `AeroSynthXError`.
  - [x] `naca4` — NACA 4-digit profile generator with cosine spacing
        and optional closed trailing edge.
  - [x] `validators` — coordinate validators (closure, monotonicity,
        min thickness, finite values).
  - [x] `exporters` — Selig `.dat` and `.csv` writers.
  - [x] `visualize` — Matplotlib renderer to PNG/SVG (pure path-based,
        no display backend).
- [x] Golden-file tests against reference NACA 0012 / 2412 / 4412
      coordinates.
- [x] Exporter round-trip tests.
- [x] Coverage ≥ 90% line / ≥ 85% branch on `aerosynthx.geometry`,
      preserved at the package-wide level.
- [x] All quality gates green.
- [x] `CHANGELOG.md` updated.
- [x] Tagged `v0.2.0`.

---

## Public Surface (Phase 2)

```python
@dataclass(frozen=True, slots=True)
class Airfoil:
    name: str                    # e.g. "NACA2412"
    chord_m: float               # chord length (informational)
    x: tuple[float, ...]         # ordered Selig: TE -> upper -> LE -> lower -> TE
    y: tuple[float, ...]
    closed_trailing_edge: bool
    metadata: Mapping[str, str]  # generator inputs for reproducibility

# Generators
naca4(designation: str, *, n_points: int = 200, chord_m: float = 1.0,
      closed_trailing_edge: bool = True) -> Airfoil

# Validators
validate_airfoil(af: Airfoil, *, closure_tol: float = 1e-6,
                 min_thickness_frac: float = 1e-4) -> None

# Exporters
to_selig_dat(af: Airfoil) -> str
to_csv(af: Airfoil) -> str

# Visualization
render_airfoil_png(af: Airfoil, path: str | Path, *,
                   dpi: int = 150) -> None
render_airfoil_svg(af: Airfoil, path: str | Path) -> None
```

The NACA 4-digit math follows Abbott & von Doenhoff, *Theory of Wing
Sections*, sections 6.4--6.6. Points are ordered Selig-style: starting
at the trailing edge, traversing the upper surface to the leading edge,
then the lower surface back to the trailing edge.

---

## Out of Scope

- NACA 5-digit (deferred to a later phase).
- 3D geometry, wing planforms.
- Mesh generation (Phase 4).
- Any LLM coupling.
