# Phase 18 — Content-addressed artifact store (CAS)

**Version:** `v1.11.0`
**Theme:** De-duplicate identical case files across runs with a shared,
filesystem-backed, content-addressed blob store. Zero new runtime deps.

## Motivation

Every run writes a full OpenFOAM case tree into `runs/<run_id>/case/`.
Across many runs the bytes are highly redundant (templates differ only by a
handful of numeric fields; geometry/airfoil files repeat verbatim). The
`CaseManifest.files` map is *already* a content-addressed index
(`relative_path -> sha256`), so we can archive each file's bytes once into a
shared store keyed by its digest and let later runs reference the existing
blob instead of re-storing it.

## Design

New module `src/aerosynthx/workflow/artifacts.py`:

- `@dataclass(frozen=True, slots=True) ArchiveResult` — outcome of archiving
  one case: `stored: int`, `deduplicated: int`, `bytes_stored: int`; with a
  `total` property (`stored + deduplicated`).
- `@dataclass(frozen=True, slots=True) StoreStats` — `blobs: int`,
  `bytes: int` for a whole-store scan.
- `class ContentAddressedStore`:
  - `__init__(self, root: Path)` — blobs live under `root`, sharded by the
    first two hex chars of the digest (`root/<aa>/<digest>`).
  - `has(digest) -> bool`
  - `path_for(digest) -> Path`
  - `read_blob(digest) -> bytes` (raises `KeyError` if absent)
  - `archive_case(case_dir, files: Mapping[str, str]) -> ArchiveResult` —
    for each `(rel_path, digest)`: if the blob already exists, count a
    de-duplication; otherwise read the file bytes and write the blob
    atomically (temp file + `os.replace`) within the same shard dir.
  - `stats() -> StoreStats` — count blobs and total bytes on disk.
  - Increments `aerosynthx_cas_blobs_total{outcome}` (`stored` /
    `deduplicated`) so dedup is observable in Prometheus.

Pipeline integration (`pipeline.py`):

- `Pipeline.__init__` gains `artifact_store: ContentAddressedStore | None`;
  defaults to a store rooted at `out_root / "blobs"`. Exposed as the
  read-only `artifact_store` property.
- After `build_case` succeeds in the CASE stage, archive the case into the
  store. Archiving is best-effort and side-effect only: it never changes
  `manifest_digest`, the run directory layout, `RunResult`, or the DB, so
  the file-serving API keeps reading real files from `case_dir`.

API (`api/app.py`):

- `GET /api/v1/store/stats` (requires `read` scope) → `{"blobs", "bytes"}`
  from `pipeline.artifact_store.stats()`.

CLI: none (the store is internal to runs).

## Invariants / safety

- Run directory layout, `manifest_digest`, DB schema, and the file API are
  untouched — CAS is purely additive.
- Atomic blob writes (temp + `os.replace`) so concurrent/aborted runs never
  leave half-written blobs; an existing blob is never rewritten.
- Digest is taken from the manifest (already the content hash); no re-hash.

## Tests

`tests/workflow/test_artifacts.py`:
- `ArchiveResult.total` arithmetic; `StoreStats` defaults.
- archive a case dir → all blobs stored; second archive of the same files →
  all de-duplicated; `has`/`path_for`/`read_blob` round-trip; `read_blob`
  on a missing digest raises `KeyError`.
- two distinct runs sharing some files: shared blobs stored once.
- `stats()` reflects stored blob count + byte total.
- metric counter increments for `stored` and `deduplicated`.

`tests/workflow/test_pipeline.py`:
- after a run, `pipeline.artifact_store` contains every manifest blob; a
  second `resume=False` run of the same intent de-duplicates (store blob
  count unchanged).
- injected store is honored.

`tests/api/test_app.py`:
- `GET /api/v1/store/stats` returns blob/byte counts after a run; read scope
  enforced (reader 200, runner 403).

## Ship ritual

100% line+branch coverage; ruff/format/mypy/pytest green; bump to
`1.11.0`; CHANGELOG `## [1.11.0] - 2026-05-31`; ROADMAP phase-map row 18 +
check off the CAS backlog item + update suggested-next-phase; commit +
annotated tag `v1.11.0` + push; restart server; smoke-test `/store/stats`.
