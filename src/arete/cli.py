"""Command line entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from arete import __version__
from arete.mindnode import import_opml
from arete.opml import render
from arete.outline import depth_counts, parse

DESCRIPTION = """\
Turn a list into a MindNode map, one node per line.

MindNode will not paste a multi-line list as separate nodes, but it does
import OPML. Indentation makes the hierarchy: tabs, two spaces or four, it
works out the unit from the list itself. Bullets and numbering are stripped.

MindNode names the centre node after the document, so --title sets the
centre and every top-level line hangs off it.
"""

EPILOG = """\
examples:
  arete                              the clipboard, into a new map
  arete --title "Q3 themes"          name the centre node
  arete notes.md                     a file instead of the clipboard
  pbpaste | arete --stdin            explicit pipe
  arete --opml > themes.opml         just the OPML, do not open MindNode
"""


def _read_input(args: argparse.Namespace) -> tuple[str, str]:
    """Return the raw list text and a default title for it."""
    if args.stdin:
        return sys.stdin.read(), "Imported list"
    if args.file:
        path = Path(args.file)
        return path.read_text(encoding="utf-8"), path.stem
    if sys.stdin.isatty():
        clipboard = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return clipboard.stdout, "Pasted list"
    # Piped into without --stdin; do the obvious thing rather than read the
    # clipboard and silently ignore what the caller actually sent.
    return sys.stdin.read(), "Imported list"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arete",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", help="input file (default: the clipboard)")
    parser.add_argument("--stdin", action="store_true", help="read the list from stdin")
    parser.add_argument("--title", help="centre node and document name")
    parser.add_argument(
        "--opml", action="store_true",
        help="write OPML to stdout instead of opening MindNode",
    )
    parser.add_argument(
        "--tab-stop", type=int, default=4, metavar="N",
        help="columns a tab counts for when reading indentation (default: 4)",
    )
    parser.add_argument(
        "--timeout", type=float, default=12.0, metavar="SECONDS",
        help="how long to wait for the map to appear (default: 12)",
    )
    parser.add_argument("--version", action="version", version=f"arete {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    text, default_title = _read_input(args)
    rows = parse(text, args.tab_stop)
    if not rows:
        print("arete: no non-blank lines on input", file=sys.stderr)
        return 1

    title = args.title or default_title
    opml = render(rows, title)

    if args.opml:
        sys.stdout.write(opml)
        return 0

    result = import_opml(opml, title, timeout=args.timeout)

    counts = depth_counts(rows)
    shape = " + ".join(f"{counts[d]} at depth {d}" for d in sorted(counts))

    if result.verified is False:
        print(
            f"arete: MindNode did not import the map ({shape}).\n"
            f"       The OPML is at {result.path} — try opening it by hand.\n"
            "       MindNode drops an import fired while another is still\n"
            "       settling, and ignores one identical to an existing map.",
            file=sys.stderr,
        )
        return 1

    landed = result.title or title
    print(f"{len(rows)} nodes ({shape}) -> MindNode as “{landed}”", file=sys.stderr)
    if result.verified is None:
        print(
            "arete: could not read MindNode's library, so the import is "
            "unverified — check the app.",
            file=sys.stderr,
        )
    elif result.title and result.title != title:
        print(
            f"arete: MindNode named it “{result.title}” because “{title}” was taken.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
