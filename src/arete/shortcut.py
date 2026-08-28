"""Reaching MindNode's own exporter through a Shortcut.

`arete --extract` normally decodes MindNode's base snapshot, which is fast and
needs nothing installed — but a snapshot is only a base, so it cannot see a map
whose content still lives in the operation log (see `library.Document`).

MindNode's App Intents can: `ExportDocumentIntent` runs MindNode's own exporter
against the live document. There is no supported way to invoke an app intent
straight from a shell, so the route is a Shortcut built once by hand, which
`shortcuts run` can then drive. `docs/export-shortcut.md` says how to build it.

The contract with that Shortcut is deliberately minimal: it takes the map's name
as text on stdin and returns the exported Markdown as text.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

DEFAULT_NAME = "Arete Export"


class ShortcutError(RuntimeError):
    """The Shortcut is missing, or failed while running."""


def available() -> Optional[List[str]]:
    """Every Shortcut on this machine, or None if Shortcuts cannot be listed."""
    try:
        done = subprocess.run(
            ["shortcuts", "list"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def installed(name: str = DEFAULT_NAME) -> bool:
    names = available()
    return bool(names) and name in names


def export(document_name: str, name: str = DEFAULT_NAME, timeout: float = 120.0) -> str:
    """Run the export Shortcut for one map and return the Markdown it produced."""
    names = available()
    if names is None:
        raise ShortcutError(
            "could not list Shortcuts — is the `shortcuts` command available?"
        )
    if name not in names:
        raise ShortcutError(f"no Shortcut named {name!r} on this machine")

    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch) / "name.txt"
        target = Path(scratch) / "out.md"
        source.write_text(document_name, encoding="utf-8")
        try:
            done = subprocess.run(
                ["shortcuts", "run", name,
                 "--input-path", str(source),
                 "--output-path", str(target)],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as expired:
            raise ShortcutError(
                f"{name!r} did not finish within {timeout:g}s"
            ) from expired
        except OSError as error:
            raise ShortcutError(f"could not run {name!r}: {error}") from error

        if done.returncode != 0:
            detail = (done.stderr or done.stdout or "").strip() or "no output"
            raise ShortcutError(f"{name!r} failed: {detail}")
        if not target.exists():
            raise ShortcutError(
                f"{name!r} produced no output — its last action must return "
                "the exported text"
            )
        text = target.read_text(encoding="utf-8", errors="replace")

    if not text.strip():
        raise ShortcutError(f"{name!r} returned nothing for {document_name!r}")
    return text
