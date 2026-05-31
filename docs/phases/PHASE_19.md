# Phase 19 — Automatic retention & cleanup policy

**Version:** `v1.12.0`
**Theme:** Bound disk growth automatically. Prune old runs by age and/or
count, then garbage-collect store blobs no longer referenced by any
surviving run. Zero new runtime deps.

## Motivation

Runs accumulate forever: each writes a full case tree under
`runs/<run_id>/` and a row in the SQLite store, while Phase 18's
content-addressed store keeps a blob for every distinct case file ever
seen. Deleting a single run (Phase 14) is manual and never touches the
shared blob store, so blobs from deleted runs linger indefinitely. An
operator needs a policy-driven way to cap history and reclaim the space
their deleted runs left behind.

## Design

New module `src/aerosynthx/workflow/retention.py`:

- `@dataclass(frozen=True, slots=True) PruneResult` — outcome of a prune
  pass: `deleted: tuple[str, ...]` (run ids removed, newest-first order
  preserved) and `kept: int`. `count` property = `len(deleted)`.
- `@dataclass(frozen=True, slots=True) GarbageCollectResult` — outcome of a
  blob GC pass: `collected: int`, `freed_bytes: int`, `kept: int`.
- Two unlabelled counters: `aerosynthx_runs_pruned_total` and
  `aerosynthx_blobs_collected_total`, so retention activity is observable.

Store helpers (`artifacts.py`), so the store stays self-contained:

- `iter_digests() -> Iterator[str]` — yield the digest of every blob on
  disk (the file name in each shard).
- `delete_blob(digest) -> int` — remove a blob, returning the bytes freed
  (`0` if it was already absent). Best-effort, idempotent.

Pipeline integration (`pipeline.py`):

- `prune_runs(*, max_age_days=None, max_count=None, now=None) -> PruneResult`
  — load every run ordered newest-first by `created_at_iso`, then mark for
  deletion any run that (a) is older than `now - max_age_days`, or (b) falls
  outside the newest `max_count`. The two predicates union. Each marked run
  is removed via the existing `delete_run` (cascades stages + removes the
  run dir). `now` is injectable for deterministic tests; defaults to
  `datetime.now(UTC)`. Calling with neither bound is a no-op.
- `collect_garbage() -> GarbageCollectResult` — compute the set of digests
  still referenced by surviving runs (read each run's
  `aerosynthx_manifest.json` `files` map), then delete every store blob
  whose digest is not in that set, summing freed bytes.

CLI (`workflow/cli.py`): new `prune` subcommand —
`aerosynthx prune --out DIR [--max-age-days D] [--max-count N] [--gc]`.
Prints how many runs were pruned and, when `--gc` is given, how many blobs
were collected and bytes freed.

API (`api/app.py`): new `POST /api/v1/maintenance/prune` (requires `run`
scope) accepting `{"max_age_days"?, "max_count"?, "gc"?}` and returning
`{"pruned", "kept", "collected", "freed_bytes"}`.

## Invariants / safety

- GC only ever removes blobs not referenced by a *surviving* run, computed
  after pruning, so a kept run can never lose a file it serves.
- `delete_run` is reused unchanged; pruning is just a selection policy over
  it. Run-dir layout, manifest digests, and the file API are untouched.
- All operations are idempotent: re-running prune/GC with the same bounds
  on an already-trimmed store deletes nothing.
- `now` and the run list are read once; deletion order does not matter.

## Tests

`tests/workflow/test_retention.py`:
- `PruneResult.count` / dataclass defaults; `GarbageCollectResult` fields.
- prune by `max_count` keeps the N newest; prune by `max_age_days` removes
  only runs older than the cutoff; both bounds together union.
- prune with no bounds is a no-op; pruning an empty store is a no-op.
- `collect_garbage` removes blobs orphaned by a deleted run while keeping
  blobs still referenced by a survivor; freed-byte total is correct;
  GC on a fresh store collects nothing.
- store `iter_digests` / `delete_blob` round-trip incl. missing-digest `0`.
- metric counters increment for pruned runs and collected blobs.

`tests/api/test_app.py`: `POST /maintenance/prune` trims runs + GCs blobs;
`run` scope enforced (reader → 403, runner → 200).
