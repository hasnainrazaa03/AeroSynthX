# Phase 20 — Run list pagination, filtering & full-text search

Version: `v1.13.0`

## Goal

Make the run history navigable at scale. The run list endpoint currently
returns only the newest `limit` rows with no way to page backwards, narrow by
status, or search the intent text. Phase 20 adds **offset pagination**,
**status filtering**, and **case-insensitive full-text search** over the stored
intent text — exposed through a single read-side query helper, the HTTP API, and
the static UI.

## Scope

### Read helper (`workflow/pipeline.py`)

- `RunListItem` (`frozen=True, slots=True`) — lightweight, ORM-free row:
  `run_id`, `status`, `intent_text`, `created_at_iso`, `completed_at_iso`.
- `RunPage` (`frozen=True, slots=True`) — `items: tuple[RunListItem, ...]`,
  `total: int`, `limit: int`, `offset: int`.
- `query_runs(db_path, *, limit=50, offset=0, status=None, q=None) -> RunPage`:
  - Clamp `limit` to `1..500`, `offset` to `>= 0`.
  - Missing DB → empty page (no crash).
  - Optional `status` exact-match filter and `q` `ILIKE %q%` filter on
    `intent_text`; `total` is the filtered count (independent of the page slice).
  - Newest-first ordering preserved.

### HTTP API (`api/app.py`)

- `GET /api/v1/runs` gains `offset`, `status` (aliased query param), and `q`.
- Responds with the same `list[RunSummary]` body (backward compatible) plus
  pagination metadata headers: `X-Total-Count`, `X-Limit`, `X-Offset`.
- Drops the inline SQLAlchemy query in favour of `query_runs`.

### Static UI (`api/static/`)

- Add a search box + status filter and Prev/Next paging controls that drive the
  new query params and read `X-Total-Count` for page math.

## Quality gates

- 100% line + branch coverage on the new helper and endpoint branches.
- ruff (+format), mypy strict, pytest green.

## Out of scope

- Cursor/keyset pagination, sort controls, saved searches.
