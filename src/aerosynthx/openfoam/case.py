"""Build a complete OpenFOAM case directory from a ``DesignIntent``.

The case directory layout produced by :func:`build_case` is:

::

    <output_dir>/
        0/
            U, p, k, omega, nut
        constant/
            transportProperties
            turbulenceProperties
            triSurface/airfoil.dat (or wing.stl)
        system/
            controlDict, fvSchemes, fvSolution, blockMeshDict, snappyHexMeshDict (if 3D)
        Allrun
        Allclean
        aerosynthx_manifest.json

The manifest records the exact intent, derived flow state, template
identity, and a SHA-256 digest of every emitted file so that downstream
stages can verify reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    select_autoescape,
)

from aerosynthx.geometry import generate_wing
from aerosynthx.geometry.custom import custom_airfoil
from aerosynthx.geometry.exporters import to_selig_dat
from aerosynthx.geometry.naca4 import naca4
from aerosynthx.geometry.naca5 import naca5
from aerosynthx.intent.schemas import DesignIntent
from aerosynthx.meshing.snappy import generate_snappy_dict
from aerosynthx.meshing.stl_exporter import export_wing_to_stl
from aerosynthx.openfoam.errors import (
    CaseExistsError,
    EnvelopeViolationError,
    TemplateRenderError,
)
from aerosynthx.openfoam.flow_state import FlowState, derive_flow_state

TEMPLATE_NAME_2D: Final[str] = "incompressible_simple_komegaSST"
TEMPLATE_VERSION: Final[str] = "0.5.0"

# Far-field box in multiples of chord, centred on the leading edge.
_DOMAIN_UPSTREAM_CHORDS: Final[float] = 10.0
_DOMAIN_DOWNSTREAM_CHORDS: Final[float] = 20.0
_DOMAIN_HALF_HEIGHT_CHORDS: Final[float] = 10.0
_DOMAIN_THICKNESS_CHORDS: Final[float] = 0.1  # 2D slab
_DOMAIN_NX: Final[int] = 60
_DOMAIN_NY: Final[int] = 40

_TEMPLATE_FILES_2D: Final[tuple[tuple[str, str], ...]] = (
    ("0/U.jinja", "0/U"),
    ("0/p.jinja", "0/p"),
    ("0/k.jinja", "0/k"),
    ("0/omega.jinja", "0/omega"),
    ("0/nut.jinja", "0/nut"),
    ("constant/transportProperties.jinja", "constant/transportProperties"),
    ("constant/turbulenceProperties.jinja", "constant/turbulenceProperties"),
    ("system/controlDict.jinja", "system/controlDict"),
    ("system/fvSchemes.jinja", "system/fvSchemes"),
    ("system/fvSolution.jinja", "system/fvSolution"),
    ("system/blockMeshDict.jinja", "system/blockMeshDict"),
    ("Allrun.jinja", "Allrun"),
    ("Allclean.jinja", "Allclean"),
)

_EXECUTABLE_FILES: Final[frozenset[str]] = frozenset({"Allrun", "Allclean"})

_TEMPLATES_ROOT_2D: Final[Path] = Path(__file__).parent / "templates" / TEMPLATE_NAME_2D


@dataclass(frozen=True, slots=True)
class CaseManifest:
    """Reproducibility manifest written into the generated case."""

    template_name: str
    template_version: str
    created_at_iso: str
    intent: dict[str, Any]
    flow_state: dict[str, Any]
    files: dict[str, str]  # relative path -> sha256 hex digest

    def to_json(self) -> str:
        """Render as a stable, sorted JSON string."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _make_env(templates_root: Path) -> Environment:
    if not templates_root.is_dir():  # pragma: no cover - defensive
        raise TemplateRenderError(
            f"template directory missing: {templates_root}",
            code="openfoam.template.missing",
        )
    return Environment(
        loader=FileSystemLoader(str(templates_root)),
        undefined=StrictUndefined,
        autoescape=select_autoescape(default=False),
        keep_trailing_newline=True,
    )


def _envelope_guard(intent: DesignIntent) -> None:
    if intent.airfoil:
        if intent.airfoil.family not in ("naca4", "naca5", "custom"):
            raise EnvelopeViolationError(
                f"only NACA 4-digit, 5-digit, and custom airfoils are supported, got {intent.airfoil.family!r}",
            )
    elif intent.wing:
        pass # Wing logic handles its own airfoil families
    else:
        raise EnvelopeViolationError("intent must carry either airfoil or wing")

    if intent.flow.velocity_m_s is None and intent.flow.mach is None:
        raise EnvelopeViolationError(
            "intent must carry either velocity_m_s or mach",
        )


def _format_float(value: float) -> str:
    return f"{value:.10g}"


def _template_context(intent: DesignIntent, state: FlowState) -> dict[str, str]:
    if intent.airfoil:
        chord = float(intent.airfoil.chord_m)
    else:
        assert intent.wing is not None
        chord = float(intent.wing.root_airfoil.chord_m)

    xmin = -_DOMAIN_UPSTREAM_CHORDS * chord
    xmax = _DOMAIN_DOWNSTREAM_CHORDS * chord
    ymin = -_DOMAIN_HALF_HEIGHT_CHORDS * chord
    ymax = _DOMAIN_HALF_HEIGHT_CHORDS * chord
    zmin = -0.5 * _DOMAIN_THICKNESS_CHORDS * chord
    zmax = 0.5 * _DOMAIN_THICKNESS_CHORDS * chord
    ux, uy, uz = state.velocity_vector_m_s
    return {
        "ux": _format_float(ux),
        "uy": _format_float(uy),
        "uz": _format_float(uz),
        "k": _format_float(state.k_m2_s2),
        "omega": _format_float(state.omega_1_s),
        "nu": _format_float(state.kinematic_viscosity_m2_s),
        "xmin": _format_float(xmin),
        "xmax": _format_float(xmax),
        "ymin": _format_float(ymin),
        "ymax": _format_float(ymax),
        "zmin": _format_float(zmin),
        "zmax": _format_float(zmax),
        "nx": str(_DOMAIN_NX),
        "ny": str(_DOMAIN_NY),
        "end_time": "2000",
        "write_interval": "100",
    }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_text(path: Path, content: str, *, executable: bool) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)
    return _sha256_text(content)


def _render_templates(env: Environment, ctx: Mapping[str, str], output_dir: Path, template_files: tuple[tuple[str, str], ...]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for src_rel, dst_rel in template_files:
        try:
            template = env.get_template(src_rel)
            rendered = template.render(**ctx)
        except TemplateError as exc:
            raise TemplateRenderError(
                f"failed to render {src_rel}: {exc}",
                code="openfoam.template.render_failed",
            ) from exc
        digest = _write_text(
            output_dir / dst_rel,
            rendered,
            executable=dst_rel in _EXECUTABLE_FILES,
        )
        digests[dst_rel] = digest
    return digests


def _write_airfoil(intent: DesignIntent, output_dir: Path) -> str:
    assert intent.airfoil is not None
    if intent.airfoil.family == "custom":
        airfoil = custom_airfoil(
            intent.airfoil.coordinates,
            chord_m=float(intent.airfoil.chord_m),
        )
    elif intent.airfoil.family == "naca5":
        airfoil = naca5(
            intent.airfoil.designation,
            chord_m=float(intent.airfoil.chord_m),
        )
    else:  # naca4
        airfoil = naca4(
            intent.airfoil.designation,
            chord_m=float(intent.airfoil.chord_m),
        )
    content = to_selig_dat(airfoil)
    return _write_text(
        output_dir / "constant" / "triSurface" / "airfoil.dat",
        content,
        executable=False,
    )


def _write_wing_stl(intent: DesignIntent, output_dir: Path) -> str:
    assert intent.wing is not None
    wing = generate_wing(intent.wing)
    stl_content = export_wing_to_stl(wing)
    return _write_text(
        output_dir / "constant" / "triSurface" / "wing.stl",
        stl_content,
        executable=False,
    )


def _write_snappy_dict(intent: DesignIntent, output_dir: Path) -> str:
    assert intent.wing is not None
    wing = generate_wing(intent.wing)
    dict_content = generate_snappy_dict(wing)
    return _write_text(
        output_dir / "system" / "snappyHexMeshDict",
        dict_content,
        executable=False,
    )


def _flow_state_dict(state: FlowState) -> dict[str, Any]:
    data = asdict(state)
    # Convert the velocity vector tuple to a list for JSON friendliness.
    vec = data["velocity_vector_m_s"]
    data["velocity_vector_m_s"] = list(vec)
    return data


def _ensure_target(output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise CaseExistsError(
                f"case directory already exists: {output_dir}",
            )
        if not output_dir.is_dir():
            raise CaseExistsError(
                f"target path exists and is not a directory: {output_dir}",
                code="openfoam.case.not_a_directory",
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)


def build_case(
    intent: DesignIntent,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> CaseManifest:
    """Render the OpenFOAM case for ``intent`` into ``output_dir``.

    Args:
        intent: A validated :class:`DesignIntent`.
        output_dir: Destination directory. Created if missing.
        overwrite: If ``True``, replace any existing case directory.

    Returns:
        A :class:`CaseManifest` describing the generated case.

    Raises:
        EnvelopeViolationError: The intent is outside the supported
            envelope.
        CaseExistsError: ``output_dir`` exists and ``overwrite`` is
            false.
        TemplateRenderError: A bundled template failed to render.
    """
    _envelope_guard(intent)
    state = derive_flow_state(intent)

    _ensure_target(output_dir, overwrite=overwrite)

    ctx = _template_context(intent, state)
    digests = {}

    if intent.airfoil:
        # 2D Case
        env = _make_env(_TEMPLATES_ROOT_2D)
        digests = _render_templates(env, ctx, output_dir, _TEMPLATE_FILES_2D)
        digests["constant/triSurface/airfoil.dat"] = _write_airfoil(intent, output_dir)
        template_name = TEMPLATE_NAME_2D
    else:
        # 3D Case
        # For this phase, we reuse 2D templates and append the 3D specific ones.
        # In a real implementation, a dedicated 3D template set would be used.
        env = _make_env(_TEMPLATES_ROOT_2D)
        digests = _render_templates(env, ctx, output_dir, _TEMPLATE_FILES_2D)

        # Override with 3D specific files
        digests["constant/triSurface/wing.stl"] = _write_wing_stl(intent, output_dir)
        digests["system/snappyHexMeshDict"] = _write_snappy_dict(intent, output_dir)

        # Modify Allrun to include snappyHexMesh
        allrun_content = (output_dir / "Allrun").read_text(encoding="utf-8")
        allrun_content = allrun_content.replace("simpleFoam", "snappyHexMesh -overwrite\nsimpleFoam")
        digests["Allrun"] = _write_text(output_dir / "Allrun", allrun_content, executable=True)

        template_name = "incompressible_simple_komegaSST_3D_mesh"

    manifest = CaseManifest(
        template_name=template_name,
        template_version=TEMPLATE_VERSION,
        created_at_iso=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        intent=intent.model_dump(mode="json"),
        flow_state=_flow_state_dict(state),
        files=dict(sorted(digests.items())),
    )
    (output_dir / "aerosynthx_manifest.json").write_text(
        manifest.to_json() + "\n", encoding="utf-8"
    )
    return manifest


def expected_case_files() -> Iterable[str]:
    """Return the relative paths every generated case must contain."""
    return (
        *(dst for _, dst in _TEMPLATE_FILES_2D),
        "constant/triSurface/airfoil.dat",
        "aerosynthx_manifest.json",
    )
