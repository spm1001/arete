"""Command line entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from arete import __version__, library, markdown
from arete.mindnode import import_opml
from arete.opml import render as render_opml
from arete.outline import depth_counts, parse
from arete.snapshot import SnapshotError, read as read_snapshot

DESCRIPTION = """\
Move lists in and out of MindNode.

In: MindNode will not paste a multi-line list as separate nodes, but it does
import OPML. Indentation makes the hierarchy — tabs, two spaces or four, the
unit is worked out from the list itself. Bullets and numbering are stripped.
MindNode names the centre node after the document, so --title sets the centre.

Out: --extract reads a map back as Markdown, straight from MindNode's library.
"""

EPILOG = """\
examples:
  arete                              the clipboard, into a new map
  arete --title "Q3 themes"          name the centre node
  arete notes.md                     a file instead of the clipboard
  arete --opml > themes.opml         just the OPML, do not open MindNode
  arete --list                       what MindNode holds, and what can be read
  arete --extract "Q3 themes"        that map, as Markdown
  arete --extract X --plain | arete --stdin --title X    round-trip
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
    # Piped into without --stdin: do the obvious thing rather than read the
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
    out = parser.add_argument_group("reading maps back out")
    out.add_argument(
        "--list", action="store_true", dest="list_documents",
        help="list MindNode's documents and whether each can be read",
    )
    out.add_argument(
        "--extract", metavar="NAME",
        help="write this map to stdout as Markdown (name, part of a name, or ID)",
    )
    out.add_argument(
        "--plain", action="store_true",
        help="with --extract: bullets only, no heading, so it feeds back into arete",
    )
    parser.add_argument("--version", action="version", version=f"arete {__version__}")
    return parser


def _no_library() -> int:
    print(
        "arete: cannot read MindNode's library at\n"
        f"       {library.LIBRARY}\n"
        "       Is MindNode installed? A newer version may have moved it.",
        file=sys.stderr,
    )
    return 1


def do_list() -> int:
    documents = library.documents()
    if documents is None:
        return _no_library()
    if not documents:
        print("arete: MindNode's library holds no documents.", file=sys.stderr)
        return 1
    width = max(len(d.title) for d in documents)
    for document in documents:
        if document.snapshot_is_authoritative:
            note = "readable"
        else:
            note = f"needs MindNode's own export ({document.operation_count} unfolded edits)"
        print(f"{document.title:<{width}}  {note}")
    return 0


def do_extract(name: str, plain: bool) -> int:
    matches = library.find(name)
    if not matches:
        if library.documents() is None:
            return _no_library()
        print(f"arete: no map matching {name!r}. Try --list.", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print(f"arete: {name!r} matches several maps:", file=sys.stderr)
        for document in matches:
            print(f"         {document.title}", file=sys.stderr)
        print("       Use a longer name, or the exact title.", file=sys.stderr)
        return 1

    document = matches[0]
    if not document.snapshot_is_authoritative:
        print(
            f"arete: {document.title!r} cannot be read from the library.\n"
            f"       Its content lives in {document.operation_count} operations that have not\n"
            "       been folded into a snapshot, and arete reads only snapshots.\n"
            "       Reading the snapshot alone would report an almost empty map,\n"
            "       so it refuses instead of answering wrongly.\n"
            "       Use MindNode's own export: File > Export > Markdown Text.",
            file=sys.stderr,
        )
        return 1

    data = library.snapshot_bytes(document.document_id)
    if data is None:
        print(
            f"arete: {document.title!r} has no snapshot file in the library.",
            file=sys.stderr,
        )
        return 1
    try:
        root = read_snapshot(data)
    except SnapshotError as error:
        print(
            f"arete: could not read {document.title!r}: {error}\n"
            "       The snapshot format is undocumented, so arete refuses rather\n"
            "       than emit a tree it cannot stand behind. Use MindNode's own\n"
            "       export: File > Export > Markdown Text.",
            file=sys.stderr,
        )
        return 1

    sys.stdout.write(markdown.render(root, heading=not plain))
    print(f"{len(root)} nodes from “{document.title}”", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_documents:
        return do_list()
    if args.extract:
        return do_extract(args.extract, args.plain)

    text, default_title = _read_input(args)
    rows = parse(text, args.tab_stop)
    if not rows:
        print("arete: no non-blank lines on input", file=sys.stderr)
        return 1

    title = args.title or default_title
    opml = render_opml(rows, title)

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
