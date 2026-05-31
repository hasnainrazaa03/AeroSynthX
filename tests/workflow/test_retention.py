from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aerosynthx.observability import render_prometheus
from aerosynthx.workflow.artifacts import ContentAddressedStore
from aerosynthx.workflow.db import RunRow, open_session
from aerosynthx.workflow.pipeline import Pipeline
from aerosynthx.workflow.retention import GarbageCollectResult, PruneResult


def _intent(velocity: int) -> str:
    return f"NACA 2412 at {velocity} m/s, alpha 3 deg, chord 1.0 m."


def _metric(name: str) -> float:
    for line in render_prometheus().splitlines():
        if line.startswith(f"{name} "):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def _set_created(pipe: Pipeline, run_id: str, when: datetime) -> None:
    with open_session(pipe.db_path) as session:
        row = session.get(RunRow, run_id)
        assert row is not None
        row.created_at_iso = when.isoformat()


def test_prune_result_count_and_gc_defaults() -> None:
    pruned = PruneResult(deleted=("a", "b"), kept=3)
    assert pruned.count == 2
    gc = GarbageCollectResult()
    assert (gc.collected, gc.freed_bytes, gc.kept) == (0, 0, 0)


def test_prune_by_max_count_keeps_newest(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids: list[str] = []
    for index, velocity in enumerate((50, 55, 60, 65)):
        result = pipe.run(_intent(velocity))
        _set_created(pipe, result.run_id, base + timedelta(days=index))
        ids.append(result.run_id)

    pruned = pipe.prune_runs(max_count=2)

    assert pruned.kept == 2
    assert set(pruned.deleted) == {ids[0], ids[1]}
    assert not (tmp_path / "runs" / ids[0]).exists()
    with open_session(pipe.db_path) as session:
        assert session.get(RunRow, ids[2]) is not None
        assert session.get(RunRow, ids[3]) is not None
        assert session.get(RunRow, ids[0]) is None


def test_prune_by_max_age_removes_old(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    now = datetime(2026, 6, 1, tzinfo=UTC)
    old = pipe.run(_intent(50))
    _set_created(pipe, old.run_id, now - timedelta(days=10))
    fresh = pipe.run(_intent(60))
    _set_created(pipe, fresh.run_id, now - timedelta(days=1))

    pruned = pipe.prune_runs(max_age_days=5, now=now)

    assert pruned.deleted == (old.run_id,)
    assert pruned.kept == 1


def test_prune_unions_age_and_count(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    now = datetime(2026, 6, 1, tzinfo=UTC)
    ids: list[str] = []
    for index, velocity in enumerate((50, 55, 60)):
        result = pipe.run(_intent(velocity))
        _set_created(pipe, result.run_id, now - timedelta(days=10 - index))
        ids.append(result.run_id)

    pruned = pipe.prune_runs(max_age_days=9, max_count=1, now=now)

    assert set(pruned.deleted) == {ids[0], ids[1]}
    assert pruned.kept == 1


def test_prune_no_bounds_is_noop(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_intent(50))

    pruned = pipe.prune_runs()

    assert pruned.deleted == ()
    assert pruned.kept == 1
    with open_session(pipe.db_path) as session:
        assert session.get(RunRow, result.run_id) is not None


def test_prune_empty_store_is_noop(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)

    pruned = pipe.prune_runs(max_count=5)

    assert pruned.deleted == ()
    assert pruned.kept == 0


def test_collect_garbage_removes_orphaned_blobs(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    keep = pipe.run(_intent(50))
    drop = pipe.run(_intent(60))
    assert keep.case_dir is not None
    before = pipe.artifact_store.stats().blobs
    assert before > 0

    pipe.delete_run(drop.run_id)
    gc = pipe.collect_garbage()

    assert gc.collected >= 1
    assert gc.freed_bytes > 0
    manifest = json.loads((keep.case_dir / "aerosynthx_manifest.json").read_text())
    referenced = set(manifest["files"].values())
    for digest in referenced:
        assert pipe.artifact_store.has(digest)
    assert gc.kept == len(referenced)
    assert pipe.artifact_store.stats().blobs == before - gc.collected


def test_collect_garbage_keeps_referenced(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_intent(50))

    gc = pipe.collect_garbage()

    assert gc.collected == 0
    assert gc.freed_bytes == 0
    assert gc.kept == pipe.artifact_store.stats().blobs


def test_collect_garbage_fresh_store_is_noop(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)

    assert pipe.collect_garbage() == GarbageCollectResult(collected=0, freed_bytes=0, kept=0)


def test_collect_garbage_ignores_failed_and_missing_manifest(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    failed = pipe.run("totally unparseable gibberish")
    assert failed.status == "failed"
    assert failed.case_dir is None
    good = pipe.run(_intent(50))
    assert good.case_dir is not None
    (good.case_dir / "aerosynthx_manifest.json").unlink()

    gc = pipe.collect_garbage()

    assert gc.kept == 0
    assert gc.collected >= 1


def test_store_iter_and_delete_blob(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "blobs")
    assert list(store.iter_digests()) == []
    assert store.delete_blob("deadbeef") == 0

    case = tmp_path / "case"
    case.mkdir()
    (case / "f").write_bytes(b"hello")
    digest = hashlib.sha256(b"hello").hexdigest()
    store.archive_case(case, {"f": digest})

    assert list(store.iter_digests()) == [digest]
    assert store.delete_blob(digest) == len(b"hello")
    assert list(store.iter_digests()) == []


def test_retention_metrics_increment(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_intent(50))
    drop = pipe.run(_intent(60))
    pipe.delete_run(drop.run_id)
    pruned_before = _metric("aerosynthx_runs_pruned_total")
    collected_before = _metric("aerosynthx_blobs_collected_total")

    pipe.prune_runs(max_count=0)
    gc = pipe.collect_garbage()

    assert _metric("aerosynthx_runs_pruned_total") == pruned_before + 1
    assert _metric("aerosynthx_blobs_collected_total") == collected_before + gc.collected
    assert gc.collected >= 1
