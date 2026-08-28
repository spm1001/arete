"""Handing an OPML document to MindNode, and checking it arrived.

Two behaviours of MindNode's importer shape everything here.

The document's centre node is taken from the *filename*, not from the OPML
<head><title>, so the temporary file has to be named after the map.

And an import fired while a previous one is still settling is dropped in
silence — no error, no dialog, nothing in the log. So this waits for the
document to actually appear, and retries once if it did not.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import NamedTuple, Optional

from arete import library

# Long enough for MindNode to finish an import that is already under way.
# Measured on 2026-08-28: a retry 3s after a dropped import lands first time.
SETTLE_SECONDS = 3.0
POLL_SECONDS = 0.5


class ImportResult(NamedTuple):
    path: Path
    """Where the OPML was written, so a failed import can be opened by hand."""

    document_id: Optional[str]
    """MindNode's ID for the new document, when we could confirm one."""

    title: Optional[str]
    """The title MindNode settled on — it appends a counter if the name is taken."""

    verified: Optional[bool]
    """True if seen in the library, False if confirmed missing, None if unreadable."""


def safe_filename(title: str) -> str:
    """A filename that survives the filesystem and still reads as the title."""
    cleaned = re.sub(r"[^\w .()&,'-]", "_", title).strip(" .")
    return cleaned or "Imported list"


def _write(opml: str, title: str) -> Path:
    # Not a TemporaryDirectory: MindNode reads the file after `open` returns,
    # and the path is worth keeping so a failed import can be retried by hand.
    directory = Path(tempfile.mkdtemp(prefix="arete-"))
    path = directory / f"{safe_filename(title)}.opml"
    path.write_text(opml, encoding="utf-8")
    return path


def _open(path: Path) -> None:
    subprocess.run(["open", "-a", "MindNode", str(path)], check=True)


def _wait_for_new(before: set[str], timeout: float) -> Optional[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        now = library.document_ids()
        if now is None:
            return None
        new = now - before
        if new:
            return next(iter(new))
    return None


def import_opml(opml: str, title: str, timeout: float = 12.0) -> ImportResult:
    """Open an OPML document in MindNode, waiting for it to land.

    When the library can be read, a dropped import is detected and retried
    once. When it cannot, the import is fired blind and reported as
    unverified rather than silently assumed to have worked.
    """
    path = _write(opml, title)
    before = library.document_ids()

    if before is None:
        _open(path)
        return ImportResult(path, None, None, None)

    _open(path)
    document_id = _wait_for_new(before, timeout)

    if document_id is None:
        # Confirmed missing rather than merely slow. The usual cause is another
        # import still settling, so give MindNode room and ask exactly once more.
        time.sleep(SETTLE_SECONDS)
        _open(path)
        document_id = _wait_for_new(before, timeout)

    if document_id is None:
        return ImportResult(path, None, None, False)

    return ImportResult(path, document_id, library.title_of(document_id), True)
