# Phase 6 — HTTP API + Web UI

Target release: `v0.6.0`.
Status: In progress.

## Goal

Expose the Phase 5 `Pipeline` over HTTP and ship a minimal browser UI
so a user can submit an intent, watch it parse, and browse the
generated OpenFOAM case files from a desktop browser — all running
fully offline against a local backend.

## Architectural decisions

- **Web framework: FastAPI + Uvicorn.** Standard Python choice, native
  Pydantic-v2 integration (we already depend on Pydantic), built-in
  OpenAPI, and zero JavaScript-build coupling on the server side.
- **UI framework: none — vanilla HTML + CSS + JS.** A Node toolchain
  (Vite/Webpack/React) would dominate CI cost and contradict the
  "engineering grade, no excessive frameworks" rule in
  `docs/ENGINEERING_WORKFLOW.md`. A single-file `index.html` + small
  `app.js` + `styles.css` is enough to demonstrate Phase 6's scope.
- **Service layer is stateless.** The FastAPI app holds only a
  `Pipeline` instance bound to a configured `out_root`. All durable
  state lives in the SQLite store from Phase 5.
- **App factory pattern.** `create_app(*, out_root: Path) -> FastAPI`
  so tests can use isolated tmp dirs.

## Public surface

```python
# aerosynthx.api
from aerosynthx.api import create_app          # FastAPI app factory
from aerosynthx.api import RunRequest          # POST /api/v1/runs body
from aerosynthx.api import RunSummary          # list item DTO
```

### Endpoints (versioned under `/api/v1`)

| Method | Path                              | Purpose                                |
|--------|-----------------------------------|----------------------------------------|
| GET    | `/healthz`                        | Liveness probe                         |
| GET    | `/api/v1/version`                 | `{name, version}`                      |
| POST   | `/api/v1/runs`                    | Execute pipeline; body `RunRequest`    |
| GET    | `/api/v1/runs`                    | List run summaries (newest first)      |
| GET    | `/api/v1/runs/{run_id}`           | Full `RunResult` payload (404 if none) |
| GET    | `/api/v1/runs/{run_id}/files`     | List relative file paths under case/   |
| GET    | `/api/v1/runs/{run_id}/files/{p}` | Download a single case file            |
| GET    | `/`                               | Serve the static web UI                |

### CLI

```
aerosynthx serve --out <dir> [--host 127.0.0.1] [--port 8000]
```

## Security guardrails

- File-download endpoint resolves the requested path under the run's
  case dir with `Path.resolve()` and rejects any path that escapes
  (`HTTP 400`).
- Reads only; no destructive endpoints. No CORS by default
  (offline / localhost use-case).

## Out of scope (deferred to Phase 7)

- Authentication / sessions.
- WebSocket progress streaming (stages are sub-second offline anyway).
- Multi-tenant project model.
- Bundled JS framework / SPA tooling.
- Containerization & deployment (Phase 7 hardening).

## Done when

- [x] `aerosynthx.api` package with `create_app` factory and routes.
- [x] Static UI shipped under `src/aerosynthx/api/static/`.
- [x] `aerosynthx serve` CLI subcommand.
- [x] Tests cover every endpoint + path-traversal guard at 100% line+branch.
- [x] All gates green (`ruff`, `ruff format --check`, `mypy`, `pytest`).
- [x] Version bumped to `0.6.0`, CHANGELOG updated, tag pushed.
