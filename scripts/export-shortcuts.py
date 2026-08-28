#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Export arete's companion Shortcuts from the Shortcuts database.

The two Shortcuts arete drives — "Arete Export" and "Arete Append" — are
hand-built, because App Intents cannot be invoked from a shell and Shortcuts
has no scripted authoring path. That makes them the one part of this tool that
lives nowhere but one Mac. This lifts them back out.

Shortcuts stores what a shortcut actually *is* in `~/Library/Shortcuts/
Shortcuts.sqlite` — the workflow row in `ZSHORTCUT`, its actions as a binary
plist in `ZSHORTCUTACTIONS.ZDATA`. The canvas is a rendering of that and is not
authoritative: an index field never typed into shows a greyed placeholder that
is indistinguishable from a real value, while no key is stored at all.

Two files per shortcut:

  shortcuts/<Name>.plist     unsigned XML — diffable, reviewable in a PR
  shortcuts/<Name>.shortcut  signed with `shortcuts sign --mode anyone`,
                             so it imports with a double-click

The device name is dropped on the way out; nothing else in these workflows is
personal, and both are checked for stray absolute paths before writing.
"""

from __future__ import annotations

import argparse
import plistlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

LIBRARY = Path.home() / "Library/Shortcuts/Shortcuts.sqlite"
DEFAULT_NAMES = ["Arete Export", "Arete Append"]

# Anything that would leak a machine or a person into a public repo.
SUSPECT = ("/Users/", "modha", "MacBook", "@", "credential", "token", "password")


def read_database() -> sqlite3.Connection:
    """Open a copy of the live database, WAL included, read-only in effect."""
    if not LIBRARY.exists():
        sys.exit(f"no Shortcuts database at {LIBRARY}")
    scratch = Path(tempfile.mkdtemp(prefix="arete-shortcuts-"))
    for suffix in ("", "-wal", "-shm"):
        source = LIBRARY.with_name(LIBRARY.name + suffix)
        if source.exists():
            shutil.copy2(source, scratch / source.name)
    return sqlite3.connect(scratch / LIBRARY.name)


def workflow(db: sqlite3.Connection, name: str) -> dict:
    """Rebuild one shortcut as a .shortcut plist dictionary."""
    row = db.execute(
        "SELECT Z_PK, ZMINIMUMCLIENTVERSION, ZHASSHORTCUTINPUTVARIABLES, "
        "       ZINPUTCLASSESDATA, ZNOINPUTBEHAVIORDATA, ZOUTPUTCLASSESDATA "
        "FROM ZSHORTCUT WHERE ZNAME = ?", (name,)
    ).fetchone()
    if row is None:
        sys.exit(f"no shortcut named {name!r} — check `shortcuts list`")
    pk, min_version, has_input_vars, inputs, no_input, outputs = row

    actions_blob = db.execute(
        "SELECT ZDATA FROM ZSHORTCUTACTIONS WHERE ZSHORTCUT = ?", (pk,)
    ).fetchone()
    if actions_blob is None:
        sys.exit(f"{name!r} has no actions stored")

    icon = db.execute(
        "SELECT ZBACKGROUNDCOLORVALUE, ZGLYPHNUMBER FROM ZSHORTCUTICON "
        "WHERE ZWORKFLOW = ?", (pk,)
    ).fetchone()

    def unplist(blob, fallback):
        return plistlib.loads(bytes(blob)) if blob else fallback

    document = {
        "WFWorkflowMinimumClientVersion": min_version or 900,
        "WFWorkflowMinimumClientVersionString": str(min_version or 900),
        "WFWorkflowClientVersion": str(min_version or 900),
        "WFWorkflowHasShortcutInputVariables": bool(has_input_vars),
        "WFWorkflowInputContentItemClasses": unplist(inputs, []),
        "WFWorkflowOutputContentItemClasses": unplist(outputs, []),
        "WFWorkflowActions": plistlib.loads(bytes(actions_blob[0])),
        "WFWorkflowTypes": [],
        "WFQuickActionSurfaces": [],
    }
    behaviour = unplist(no_input, None)
    if behaviour:
        document["WFWorkflowNoInputBehavior"] = behaviour
    if icon:
        document["WFWorkflowIcon"] = {
            "WFWorkflowIconStartColor": icon[0],
            "WFWorkflowIconGlyphNumber": icon[1],
        }
    # ZLASTSAVEDONDEVICENAME is deliberately not carried: it names a machine
    # and a person, and nothing reads it on import.
    return document


def check_clean(document: dict, name: str) -> list[str]:
    """Anything in here that shouldn't reach a public repo."""
    text = plistlib.dumps(document).decode("utf-8", "replace")
    return sorted({s for s in SUSPECT if s in text})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", default=DEFAULT_NAMES,
                        help=f"shortcuts to export (default: {', '.join(DEFAULT_NAMES)})")
    parser.add_argument("--out", default="shortcuts", help="output directory")
    parser.add_argument("--mode", default="anyone", choices=["anyone", "people-who-know-me"],
                        help="signing mode (default: anyone, so it imports anywhere)")
    parser.add_argument("--allow-suspect", action="store_true",
                        help="write even if the leak check trips")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    db = read_database()

    for name in (args.names or DEFAULT_NAMES):
        document = workflow(db, name)
        found = check_clean(document, name)
        if found and not args.allow_suspect:
            print(f"REFUSED {name}: contains {found} — inspect before publishing",
                  file=sys.stderr)
            return 1

        plist_path = out / f"{name}.plist"
        plist_path.write_bytes(plistlib.dumps(document, fmt=plistlib.FMT_XML))

        # `shortcuts sign` gates on the EXTENSION, not the content: the same
        # bytes are rejected as .plist and accepted as .shortcut. So sign from
        # a correctly-named temporary copy and keep the readable one for git.
        signed_path = out / f"{name}.shortcut"
        with tempfile.TemporaryDirectory() as scratch:
            staged = Path(scratch) / f"{name}.shortcut"
            staged.write_bytes(plist_path.read_bytes())
            done = subprocess.run(
                ["shortcuts", "sign", "--mode", args.mode,
                 "--input", str(staged), "--output", str(signed_path)],
                capture_output=True, text=True,
            )
        if done.returncode != 0:
            detail = (done.stderr or done.stdout).strip()
            print(f"FAILED to sign {name}: {detail}", file=sys.stderr)
            return 1

        actions = len(document["WFWorkflowActions"])
        print(f"{name}: {actions} actions -> {plist_path.name}, {signed_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
