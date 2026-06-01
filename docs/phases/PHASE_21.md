# Phase 21 — Relink run directories to store blobs

Version: `v1.14.0`

## Goal

Phase 18 archives every case file into a content-addressed blob store, but the
original run directories still hold full, duplicated copies — so identical
bytes live on disk twice (once in `runs/<id>/case/...`, once in `blobs/`).
Phase 21 reclaims that space by **replacing run-directory files with hard
links** into the store. After relinking, a run file and its store blob share a
single inode, so the redundant on-disk copy disappears while every existing
path keeps reading the exact same bytes.

Relinking is an explicit, idempotent **maintenance** operation (symmetric with
Phase 19 pruning) — it never runs inside the hot pipeline path, so it cannot
interfere with case building or solving. `build_case` always `rmtree`s a run's
directory before rewriting it, so re-running a relinked run safely breaks the
link first; the shared blob is never mutated in place.

## Scope

### Store (`workflow/artifacts.py`)

- `RelinkResult` (`frozen=True, slots=True`): `linked`, `bytes_reclaimed`,
  `skipped` (all default `0`).
- `ContentAddressedStore.link_case(case_dir, files) -> RelinkResult`: for each
  `relative_path -> digest`, hard-link the run file to its blob via an atomic
  temp-link + `os.replace`. Skips files whose blob is missing, whose run copy is
  missing, or that already share the blob's inode (idempotent).
- New unlabelled `aerosynthx_run_files_linked_total` counter.

### Pipeline (`workflow/pipeline.py`)

- `Pipeline.relink_runs() -> RelinkResult`: relink every surviving run's case
  files (aggregated), reusing each run's `aerosynthx_manifest.json` `files` map.
- `_iter_run_cases()` helper yields `(case_dir, files)` for runs with a manifest.

### CLI (`workflow/cli.py`)

- `aerosynthx relink --out DIR` → prints
  `linked N file(s); B bytes reclaimed; S skipped`.

### HTTP API (`api/app.py`)

- `POST /api/v1/maintenance/relink` (requires the `run` scope, no body) →
  `{linked, bytes_reclaimed, skipped}`.

## Quality gates

- 100% line + branch coverage; ruff (+format), mypy strict, pytest green.

## Out of scope

- Automatic relinking inside `run`; symlink mode; cross-filesystem fallback.
