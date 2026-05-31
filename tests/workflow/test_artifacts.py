from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aerosynthx.observability import render_prometheus
from aerosynthx.workflow.artifacts import (
    ArchiveResult,
    ContentAddressedStore,
    StoreStats,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_case(case_dir: Path, files: dict[str, bytes]) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for rel, payload in files.items():
        target = case_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        manifest[rel] = _sha256(payload)
    return manifest


def test_archive_result_total() -> None:
    assert ArchiveResult(stored=2, deduplicated=3, bytes_stored=10).total == 5


def test_store_stats_defaults() -> None:
    stats = StoreStats()
    assert stats.blobs == 0
    assert stats.bytes == 0


def test_archive_stores_then_deduplicates(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    files = _write_case(case_dir, {"0/U": b"alpha", "system/controlDict": b"beta-content"})
    store = ContentAddressedStore(tmp_path / "blobs")

    first = store.archive_case(case_dir, files)
    assert first.stored == 2
    assert first.deduplicated == 0
    assert first.total == 2
    assert first.bytes_stored == len(b"alpha") + len(b"beta-content")

    # Re-archiving the identical case stores nothing new.
    second = store.archive_case(case_dir, files)
    assert second.stored == 0
    assert second.deduplicated == 2
    assert second.bytes_stored == 0


def test_blob_round_trip_and_missing(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    files = _write_case(case_dir, {"0/p": b"pressure"})
    store = ContentAddressedStore(tmp_path / "blobs")
    store.archive_case(case_dir, files)

    digest = files["0/p"]
    assert store.root == (tmp_path / "blobs")
    assert store.has(digest) is True
    assert store.path_for(digest) == (tmp_path / "blobs" / digest[:2] / digest)
    assert store.read_blob(digest) == b"pressure"

    with pytest.raises(KeyError):
        store.read_blob("0" * 64)


def test_distinct_runs_share_blobs(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "blobs")
    shared = b"identical-airfoil-bytes"

    case_a = tmp_path / "a"
    files_a = _write_case(case_a, {"shared.dat": shared, "a-only": b"aaa"})
    case_b = tmp_path / "b"
    files_b = _write_case(case_b, {"shared.dat": shared, "b-only": b"bbb"})

    res_a = store.archive_case(case_a, files_a)
    res_b = store.archive_case(case_b, files_b)

    assert res_a.stored == 2
    # The shared blob is de-duplicated for the second run.
    assert res_b.stored == 1
    assert res_b.deduplicated == 1


def test_stats_reflects_disk(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "blobs")
    # Empty / non-existent store.
    assert store.stats() == StoreStats(blobs=0, bytes=0)

    case_dir = tmp_path / "case"
    files = _write_case(case_dir, {"0/U": b"one", "0/p": b"twotwo"})
    store.archive_case(case_dir, files)

    stats = store.stats()
    assert stats.blobs == 2
    assert stats.bytes == len(b"one") + len(b"twotwo")


def test_metric_counts_outcomes(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    files = _write_case(case_dir, {"0/U": b"metric-bytes"})
    store = ContentAddressedStore(tmp_path / "blobs")

    before = render_prometheus()
    store.archive_case(case_dir, files)
    store.archive_case(case_dir, files)
    after = render_prometheus()

    assert "aerosynthx_cas_blobs_total" in after
    assert 'outcome="stored"' in after
    assert 'outcome="deduplicated"' in after
    assert before != after
