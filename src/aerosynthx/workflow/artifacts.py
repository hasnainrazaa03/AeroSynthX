"""Content-addressed artifact store for de-duplicating run case files.

Every pipeline run writes a full OpenFOAM case tree under
``runs/<run_id>/case/``. Across runs those bytes are highly redundant, so
this module archives each file once into a shared, filesystem-backed blob
store keyed by the file's SHA-256 digest. Identical files produced by later
runs map to the same blob and are not stored again.

The :class:`aerosynthx.openfoam.case.CaseManifest` ``files`` mapping is
already a content-addressed index (``relative_path -> sha256``), so the
store reuses those digests directly as blob keys — no re-hashing.

Scope: this is a *side-effect-only*, additive layer. It never alters the
run directory layout, the manifest digest, the database, or the
file-serving API; those keep reading the real files from ``case_dir``.
Blobs are sharded by the first two hex characters of their digest
(``root/<aa>/<digest>``) and written atomically (temp file + ``os.replace``)
so concurrent or aborted runs never leave a half-written blob.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from aerosynthx.observability import METRICS

_CAS_BLOBS = METRICS.counter(
    "aerosynthx_cas_blobs_total",
    "Case files seen by the artifact store, labelled by outcome.",
    label_names=("outcome",),
)


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    """Outcome of archiving one case directory into the store.

    Attributes:
        stored: Number of files written to the store as new blobs.
        deduplicated: Number of files already present (not rewritten).
        bytes_stored: Total bytes written for the newly stored blobs.
    """

    stored: int
    deduplicated: int
    bytes_stored: int

    @property
    def total(self) -> int:
        """Total files considered (``stored + deduplicated``)."""
        return self.stored + self.deduplicated


@dataclass(frozen=True, slots=True)
class StoreStats:
    """Aggregate size of a whole store.

    Attributes:
        blobs: Number of distinct blobs on disk.
        bytes: Total bytes occupied by all blobs.
    """

    blobs: int = 0
    bytes: int = 0


class ContentAddressedStore:
    """A filesystem blob store keyed by SHA-256 digest."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        """The directory under which blobs are stored."""
        return self._root

    def path_for(self, digest: str) -> Path:
        """Return the on-disk path a blob with ``digest`` would occupy."""
        return self._root / digest[:2] / digest

    def has(self, digest: str) -> bool:
        """Return ``True`` if a blob with ``digest`` already exists."""
        return self.path_for(digest).is_file()

    def read_blob(self, digest: str) -> bytes:
        """Return the bytes of the blob ``digest``.

        Raises:
            KeyError: If no blob with that digest is present.
        """
        path = self.path_for(digest)
        if not path.is_file():
            raise KeyError(digest)
        return path.read_bytes()

    def archive_case(self, case_dir: Path, files: Mapping[str, str]) -> ArchiveResult:
        """Archive each file in ``files`` into the store, de-duplicating.

        Args:
            case_dir: Directory containing the case files.
            files: Mapping of ``relative_path -> sha256`` (a
                :attr:`CaseManifest.files` map).

        Returns:
            An :class:`ArchiveResult` summarising stored vs de-duplicated
            files.
        """
        stored = 0
        deduplicated = 0
        bytes_stored = 0
        for rel_path, digest in files.items():
            if self.has(digest):
                deduplicated += 1
                _CAS_BLOBS.inc(outcome="deduplicated")
                continue
            payload = (case_dir / rel_path).read_bytes()
            self._write_blob(digest, payload)
            stored += 1
            bytes_stored += len(payload)
            _CAS_BLOBS.inc(outcome="stored")
        return ArchiveResult(stored=stored, deduplicated=deduplicated, bytes_stored=bytes_stored)

    def stats(self) -> StoreStats:
        """Scan the store and return its blob count and total byte size."""
        if not self._root.is_dir():
            return StoreStats()
        blobs = 0
        total = 0
        for path in self._root.rglob("*"):
            if path.is_file():
                blobs += 1
                total += path.stat().st_size
        return StoreStats(blobs=blobs, bytes=total)

    def iter_digests(self) -> Iterator[str]:
        """Yield the digest of every blob currently on disk."""
        if not self._root.is_dir():
            return
        for path in self._root.rglob("*"):
            if path.is_file():
                yield path.name

    def delete_blob(self, digest: str) -> int:
        """Remove the blob ``digest`` and return the bytes freed.

        Idempotent: returns ``0`` if no such blob exists.
        """
        path = self.path_for(digest)
        if not path.is_file():
            return 0
        size = path.stat().st_size
        path.unlink()
        return size

    def _write_blob(self, digest: str, payload: bytes) -> None:
        target = self.path_for(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / f".{digest}.{uuid.uuid4().hex}.tmp"
        tmp.write_bytes(payload)
        os.replace(tmp, target)
