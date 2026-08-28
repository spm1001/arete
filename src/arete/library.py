"""Reading MindNode's document library.

Used for two things: verifying that an import actually landed, and finding a
document's base snapshot so a map can be extracted back out.

MindNode's importer fails silently — fire two imports back to back and the
second one simply never appears, with no error, no dialog and no log line. The
only way to tell an import from a no-op is to look at the library afterwards.

Everything here is best-effort and read-only. If MindNode moves or changes its
library, these functions return None and the caller degrades to "unknown"
rather than failing; verification must never be able to break the import it
is checking.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, Set

LIBRARY = (
    Path.home()
    / "Library/Containers/com.ideasoncanvas.mindnode/Data/Library"
    / "Application Support/MindNode/production-v1_0"
    / "MindNode Library.mindnodelibrary"
)


@dataclass(frozen=True)
class Document:
    document_id: str
    title: str
    serialization_version: Optional[int]
    operation_count: int

    @property
    def snapshot_is_authoritative(self) -> bool:
        """Whether the base snapshot alone represents the current document.

        A map created by import gets a complete snapshot and no operations. A
        map typed in the app accumulates operations against an all-but-empty
        base snapshot, so reading only the snapshot would report a map with
        one blank node — a confidently wrong answer about someone's work.
        """
        return self.operation_count == 0


def _query(sql: str, parameters: Sequence[Any] = ()) -> Optional[List[tuple]]:
    """Run a read-only query against a copy of the library database.

    The database is copied before reading — along with its write-ahead log,
    without which a just-finished import is invisible — so we never hold a
    lock on a library the app is actively writing to.
    """
    database = LIBRARY / "Content.sqlite3"
    if not database.exists():
        return None
    try:
        with tempfile.TemporaryDirectory() as scratch:
            local = Path(scratch) / database.name
            for suffix in ("", "-wal", "-shm"):
                source = database.with_name(database.name + suffix)
                if source.exists():
                    shutil.copy2(source, local.with_name(local.name + suffix))
            connection = sqlite3.connect(local)
            try:
                return connection.execute(sql, parameters).fetchall()
            finally:
                connection.close()
    except (sqlite3.Error, OSError):
        return None


def document_ids() -> Optional[Set[str]]:
    """The IDs MindNode currently holds, or None if the library is unreadable."""
    rows = _query("SELECT documentID FROM document WHERE trashDate IS NULL")
    return None if rows is None else {row[0] for row in rows}


def title_of(document_id: str) -> Optional[str]:
    """The title MindNode settled on, which may differ from the one asked for.

    MindNode appends a counter when a name is taken, so a map requested as
    "Themes" can land as "Themes 2". Reporting the real name saves the reader
    hunting for a document that is not called what they typed.
    """
    rows = _query(
        "SELECT title FROM document WHERE documentID = ?", (document_id,)
    )
    return rows[0][0] if rows else None


def documents() -> Optional[List[Document]]:
    """Every document MindNode holds, newest last, or None if unreadable."""
    rows = _query(
        "SELECT d.documentID, d.title, d.serializationVersion, "
        "       (SELECT COUNT(*) FROM operation o "
        "        WHERE o.documentID = d.documentID) "
        "FROM document d WHERE d.trashDate IS NULL ORDER BY d.rowid"
    )
    return None if rows is None else [Document(*row) for row in rows]


def find(name_or_id: str) -> List[Document]:
    """Documents matching an ID, an exact title, or a case-insensitive part."""
    everything = documents() or []
    exact = [d for d in everything
             if d.document_id == name_or_id or d.title == name_or_id]
    if exact:
        return exact
    needle = name_or_id.casefold()
    return [d for d in everything if needle in d.title.casefold()]


def snapshot_bytes(document_id: str) -> Optional[bytes]:
    """The document's base snapshot, or None if there is no asset for it."""
    try:
        return (LIBRARY / "Assets" / document_id).read_bytes()
    except OSError:
        return None
