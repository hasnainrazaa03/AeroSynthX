# Phase 5 -- Workflow Orchestrator + Persistence

Target release: `v0.5.0`.
Status: **In progress.**
Goal: Stitch the physics, intent, geometry, and OpenFOAM layers into a
single staged pipeline driven from a CLI, with persistent run history
in SQLite and resumable execution keyed by intent content.

---

## Acceptance Criteria

- [x] `aerosynthx.workflow` package implemented:
  - [x] `errors` -- typed exceptions rooted under `AeroSynthXError`.
  - [x] `stages` -- ordered stage enum (`parse`, `compute`, `geometry`,
        `case`, `persist`) and helpers.
  - [x] `db` -- SQLAlchemy 2.0 models (`RunRow`, `StageRow`) +
        `open_session(path)` context manager + `init_db(path)`.
  - [x] `pipeline` -- `Pipeline.run(intent_text)` executes every stage,
        captures per-stage status, timing, and output digest, and
        writes a final run manifest. Resume re-uses completed runs
        keyed by SHA-256 of normalised intent text.
  - [x] `cli` -- `aerosynthx run --intent "<text>" --out <dir>` and
        `aerosynthx show <run_id> --out <dir>` subcommands.
- [x] CLI installed as a console script (`[project.scripts]`).
- [x] Persistent run store at `<out_dir>/aerosynthx.db`.
- [x] Per-run output at `<out_dir>/runs/<run_id>/case/...` plus a
      `run.json` snapshot of the full :class:`RunResult`.
- [x] Coverage gate met on `aerosynthx.workflow`.
- [x] All quality gates green; tagged `v0.5.0`.

---

## Public Surface

```python
class StageName(str, Enum):
    PARSE = "parse"
    COMPUTE = "compute"
    GEOMETRY = "geometry"
    CASE = "case"
    PERSIST = "persist"

@dataclass(frozen=True, slots=True)
class StageResult:
    name: str
    status: Literal["ok", "skipped", "failed"]
    duration_ms: int
    output_digest: str | None
    error: str | None

@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: str
    intent_text: str
    status: Literal["completed", "failed"]
    intent: DesignIntent | None
    flow_state: FlowState | None
    case_dir: Path | None
    manifest_digest: str | None
    stages: tuple[StageResult, ...]

class Pipeline:
    def __init__(
        self,
        *,
        out_root: Path,
        db_path: Path | None = None,
    ) -> None: ...
    def run(self, intent_text: str, *, resume: bool = True) -> RunResult: ...

def main(argv: list[str] | None = None) -> int: ...
```

## Out of Scope

- LLM-backed parsing in the CLI -- v0.5 uses the deterministic offline
  parser. LLM wiring lives in Phase 6/7.
- Actually executing OpenFOAM. The pipeline writes the case directory
  and stops there.
- Concurrency / multi-run scheduling. One run per CLI invocation.
- A web UI -- that is Phase 6.
