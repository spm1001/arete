"""Peeking at MindNode's document library, so an import can be verified.

MindNode's importer fails silently: fire two imports back to back and the
second one simply never appears — no error, no dialog, no log line. The only
way to tell an import from a no-op is to look at the library afterwards.

Everything here is best-effort and read-only. If MindNode moves its library
in a future version, verification degrades to "unknown" and the import still
works; it must never be able to break the tool it is checking.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Set

LIBRARY = (
    Path.home()
    / "Library/Containers/com.ideasoncanvas.mindnode/Data/Library"
    / "Application Support/MindNode/production-v1_0"
    / "MindNode Library.mindnodelibrary"
)


def document_ids() -> Optional[Set[str]]:
    """The set of document IDs MindNode currently holds, or None if unreadable.

    The database is copied before reading — along with its write-ahead log,
    without which a just-finished import is invisible — so that we never hold
    a lock on a library the app is actively writing to.
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
                rows = connection.execute(
                    "SELECT documentID FROM document WHERE trashDate IS NULL"
                ).fetchall()
            finally:
                connection.close()
        return {row[0] for row in rows}
    except (sqlite3.Error, OSError):
        return None


def title_of(document_id: str) -> Optional[str]:
    """The title MindNode settled on, which may differ from the one asked for.

    MindNode appends a counter when the name is taken, so a map requested as
    "Themes" can land as "Themes 2". Reporting the real name saves the reader
    hunting for a document that is not called what they typed.
    """
    ids = document_ids()
    if ids is None or document_id not in ids:
        return None
    try:
        with tempfile.TemporaryDirectory() as scratch:
            database = LIBRARY / "Content.sqlite3"
            local = Path(scratch) / database.name
            for suffix in ("", "-wal", "-shm"):
                source = database.with_name(database.name + suffix)
                if source.exists():
                    shutil.copy2(source, local.with_name(local.name + suffix))
            connection = sqlite3.connect(local)
            try:
                row = connection.execute(
                    "SELECT title FROM document WHERE documentID = ?", (document_id,)
                ).fetchone()
            finally:
                connection.close()
        return row[0] if row else None
    except (sqlite3.Error, OSError):
        return None
