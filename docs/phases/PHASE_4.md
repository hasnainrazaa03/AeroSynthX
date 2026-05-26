# Phase 4 -- OpenFOAM Case Generation

Target release: `v0.4.0`.
Status: **In progress.**
Goal: Convert a validated `DesignIntent` into a structurally complete,
reproducible OpenFOAM case directory targeting incompressible 2D RANS
(`simpleFoam` + `kOmegaSST`), without ever shelling out to OpenFOAM
during tests.

---

## Acceptance Criteria

- [x] `aerosynthx.openfoam` package implemented:
  - [x] `errors` -- typed exceptions rooted under `AeroSynthXError`.
  - [x] `flow_state` -- deterministic mapping
        `DesignIntent + ISA -> FlowState` (velocity vector, density,
        kinematic viscosity, turbulence k/omega, Reynolds number).
  - [x] `case` -- `build_case(intent, output_dir, *, overwrite=False)`
        renders the bundled Jinja2 template set and writes the
        manifest.
  - [x] `validators` -- `validate_case_structure(path)` returns a
        list of structural issues without running OpenFOAM.
- [x] Template `incompressible_simple_komegaSST`:
  - [x] `0/U`, `0/p`, `0/k`, `0/omega`, `0/nut`.
  - [x] `constant/transportProperties`, `constant/turbulenceProperties`.
  - [x] `system/controlDict`, `system/fvSchemes`, `system/fvSolution`,
        `system/blockMeshDict`.
  - [x] `Allrun`, `Allclean`.
- [x] Airfoil geometry exported to
      `constant/triSurface/airfoil.dat` for downstream meshers.
- [x] Envelope guard re-validates intent at the OpenFOAM boundary and
      rejects compressible / non-NACA4 cases with a typed error.
- [x] Case manifest (`aerosynthx_manifest.json`) records inputs,
      derived flow state, template name + version, and a file list
      with SHA-256 digests.
- [x] Coverage gate met on `aerosynthx.openfoam`.
- [x] All quality gates green; tagged `v0.4.0`.

---

## Public Surface

```python
@dataclass(frozen=True, slots=True)
class FlowState:
    velocity_m_s: float
    velocity_vector_m_s: tuple[float, float, float]
    mach: float
    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    kinematic_viscosity_m2_s: float
    reynolds_chord: float
    turbulence_intensity: float
    turbulence_length_scale_m: float
    k_m2_s2: float
    omega_1_s: float

def derive_flow_state(intent: DesignIntent) -> FlowState: ...

@dataclass(frozen=True, slots=True)
class CaseManifest:
    template_name: str
    template_version: str
    created_at_iso: str
    intent: dict[str, Any]
    flow_state: dict[str, float]
    files: dict[str, str]   # relative path -> sha256

def build_case(
    intent: DesignIntent,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> CaseManifest: ...

def validate_case_structure(case_dir: Path) -> list[str]: ...

class OpenFoamError(AeroSynthXError): ...
class EnvelopeViolationError(OpenFoamError): ...
class CaseExistsError(OpenFoamError): ...
class TemplateRenderError(OpenFoamError): ...
```

## Out of Scope

- Generating a body-fitted mesh around the airfoil. The Phase 4 case
  ships a rectangular far-field `blockMesh` only; the airfoil surface
  geometry is exported alongside the case for a downstream mesher
  (snappyHexMesh / cfMesh / external) to consume in Phase 5+.
- Executing `simpleFoam` -- tests never run OpenFOAM. The case is
  validated structurally only.
- Compressible flow, transient flow, 3D wings, multi-component cases.
