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

A second Shortcut wraps `CreateNodeIntent`, which is the only route to adding a
node to a map that already exists — OPML import always mints a new document.
Its contract is three lines of text in (map title, parent node title, new node
title) and nothing out. See `docs/append-shortcut.md`.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

DEFAULT_NAME = "Arete Export"
APPEND_NAME = "Arete Append"


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
    text = _run(name, document_name, want_output=True, timeout=timeout)
    if not text.strip():
        raise ShortcutError(f"{name!r} returned nothing for {document_name!r}")
    return text


def _run(name: str, payload: str, want_output: bool, timeout: float) -> str:
    """Run a Shortcut with `payload` as its text input.

    Shared by export and append so both report a missing or misbehaving
    Shortcut the same way — by name, with what it actually did wrong.
    """
    names = available()
    if names is None:
        raise ShortcutError(
            "could not list Shortcuts — is the `shortcuts` command available?"
        )
    if name not in names:
        raise ShortcutError(f"no Shortcut named {name!r} on this machine")

    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch) / "input.txt"
        target = Path(scratch) / "output.txt"
        source.write_text(payload, encoding="utf-8")
        argv = ["shortcuts", "run", name, "--input-path", str(source)]
        if want_output:
            argv += ["--output-path", str(target)]
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as expired:
            raise ShortcutError(f"{name!r} did not finish within {timeout:g}s") from expired
        except OSError as error:
            raise ShortcutError(f"could not run {name!r}: {error}") from error

        if done.returncode != 0:
            detail = (done.stderr or done.stdout or "").strip() or "no output"
            raise ShortcutError(f"{name!r} failed: {detail}")
        if not want_output:
            return ""
        if not target.exists():
            raise ShortcutError(
                f"{name!r} produced no output — its last action must return "
                "the exported text"
            )
        return target.read_text(encoding="utf-8", errors="replace")


def append(document_title: str, parent_title: str, node_title: str,
           name: str = APPEND_NAME, timeout: float = 60.0) -> None:
    """Add one node under `parent_title` in `document_title`.

    The payload is three lines, so a title containing a newline would shift the
    fields and attach a node somewhere unintended. That is rejected here rather
    than left to produce a plausible-looking wrong map.
    """
    for label, value in (("map title", document_title),
                         ("parent title", parent_title),
                         ("node title", node_title)):
        if "\n" in value or "\r" in value:
            raise ShortcutError(f"{label} contains a newline, which the three-line "
                                f"payload cannot carry: {value!r}")
    _run(name, f"{document_title}\n{parent_title}\n{node_title}\n",
         want_output=False, timeout=timeout)
