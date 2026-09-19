"""Snapshot persistence: ``<root>/<label>/snapshot.json``.

One directory per label leaves room for sidecar files later (raw logs, HTML)
without changing the layout. Files are written atomically so a crash mid-write
never leaves a half snapshot behind.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from compatsentinel.models import SCHEMA_VERSION, Snapshot

SNAPSHOT_FILENAME = "snapshot.json"
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class StoreError(Exception):
    """Base class; the message is user facing."""


class SnapshotNotFoundError(StoreError):
    pass


class SnapshotExistsError(StoreError):
    pass


class SchemaVersionError(StoreError):
    pass


class InvalidLabelError(StoreError):
    pass


def validate_label(label: str) -> str:
    """Return ``label`` if it is safe to use as a directory name, else raise."""
    if not LABEL_PATTERN.match(label):
        raise InvalidLabelError(
            f"invalid label {label!r}: use letters, digits, '.', '_' or '-' (max 64 chars)"
        )
    return label


def read_snapshot(path: Path) -> Snapshot:
    """Parse a snapshot JSON file, refusing versions newer than this tool understands."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SnapshotNotFoundError(f"snapshot file not found: {path}") from None

    try:
        snapshot = Snapshot.model_validate_json(text)
    except ValidationError as exc:
        raise StoreError(f"{path}: not a valid snapshot: {exc}") from exc

    if snapshot.schema_version > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"{path}: schema version {snapshot.schema_version} is newer than "
            f"this tool supports ({SCHEMA_VERSION}); upgrade compatsentinel"
        )
    return snapshot


def write_snapshot(snapshot: Snapshot, path: Path) -> None:
    """Write ``snapshot`` to ``path`` atomically (temp file, then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


class SnapshotStore:
    """Labelled snapshots under one root directory (``./snapshots`` by default)."""

    def __init__(self, root: Path = Path("snapshots")) -> None:
        self.root = root

    def path_for(self, label: str) -> Path:
        return self.root / validate_label(label) / SNAPSHOT_FILENAME

    def exists(self, label: str) -> bool:
        return self.path_for(label).is_file()

    def save(self, snapshot: Snapshot, *, overwrite: bool = False) -> Path:
        path = self.path_for(snapshot.label)
        if path.exists() and not overwrite:
            raise SnapshotExistsError(
                f"snapshot {snapshot.label!r} already exists at {path}; "
                "choose another label or pass overwrite"
            )
        write_snapshot(snapshot, path)
        return path

    def resolve(self, ref: str | Path) -> Path:
        """Map a label, a snapshot directory or a JSON file to the JSON file path.

        Paths win over labels so ``examples/snapshots/before`` works from any
        directory, and a bare label such as ``before`` looks under the store root.
        """
        candidate = Path(ref)
        if candidate.is_file():
            return candidate
        if candidate.is_dir() and (candidate / SNAPSHOT_FILENAME).is_file():
            return candidate / SNAPSHOT_FILENAME
        try:
            return self.path_for(str(ref))
        except InvalidLabelError:
            raise SnapshotNotFoundError(f"no snapshot at {str(ref)!r}") from None

    def load(self, ref: str | Path) -> Snapshot:
        path = self.resolve(ref)
        if not path.is_file():
            raise SnapshotNotFoundError(
                f"snapshot {str(ref)!r} not found (looked for {path}); run 'capture' first"
            )
        return read_snapshot(path)

    def list_labels(self) -> list[str]:
        """Labels of every stored snapshot, sorted alphabetically.

        A label counts only when ``<root>/<label>/snapshot.json`` exists. A
        missing root simply means there are no snapshots.
        """
        if not self.root.is_dir():
            return []
        return sorted(
            entry.name for entry in self.root.iterdir() if (entry / SNAPSHOT_FILENAME).is_file()
        )
