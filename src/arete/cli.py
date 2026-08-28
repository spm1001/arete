"""Command line entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from arete import __version__, freemind, library, markdown, shortcut
from arete.mindnode import import_document
from arete.opml import render as render_opml
from arete.outline import depth_counts, lift_single_root, parse
from arete.shortcut import ShortcutError
from arete.snapshot import SnapshotError, read as read_snapshot

DESCRIPTION = """\
Move lists in and out of MindNode.

In: MindNode will not paste a multi-line list as separate nodes, but it does
import OPML. Indentation makes the hierarchy — tabs, two spaces or four, the
unit is worked out from the list itself. Bullets and numbering are stripped.
MindNode names the centre node after the document, so --title sets the centre.
With --tags, a trailing #tag on a line becomes a real MindNode tag.

Out: --extract reads a map back as Markdown from MindNode's library. Maps typed
in the app keep their content in an operation log the library alone cannot show,
and for those --extract calls MindNode's own exporter through a Shortcut — see
docs/export-shortcut.md for the one-off setup.
"""

EPILOG = """\
examples:
  arete                              the clipboard, into a new map
  arete --title "Q3 themes"          name the centre node
  arete notes.md                     a file instead of the clipboard
  arete --tags                       trailing #tags become real tags
  arete --opml > themes.opml         just the import file, do not open MindNode
  arete --list                       what MindNode holds, and what can be read
  arete --extract "Q3 themes"        that map, as Markdown
  arete --extract X --plain | arete --stdin --title X --tags   round-trip
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
        "--tags", action="store_true",
        help="import via FreeMind so a trailing #tag becomes a real MindNode tag "
             "(the tag text leaves the node title, so 'issue #42' loses its number)",
    )
    parser.add_argument(
        "--opml", action="store_true",
        help="write the import document to stdout instead of opening MindNode "
             "(OPML, or FreeMind XML with --tags)",
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
    out.add_argument(
        "--from-snapshot", action="store_true",
        help="read the library snapshot even if the export Shortcut exists "
             "(faster, but it can lag the app)",
    )
    out.add_argument(
        "--shortcut", default=shortcut.DEFAULT_NAME, metavar="NAME",
        help=f"Shortcut wrapping MindNode's exporter (default: {shortcut.DEFAULT_NAME!r})",
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
    exporter = shortcut.installed()
    for document in documents:
        if exporter:
            note = "MindNode's exporter"
        elif document.has_pending_operations:
            note = (f"needs the export Shortcut "
                    f"({document.operation_count} unfolded edits)")
        else:
            note = "library snapshot (may lag the app)"
        print(f"{document.title:<{width}}  {note}")
    if not exporter:
        print(
            "\narete: no export Shortcut installed, so these read from base\n"
            "       snapshots, which can lag what MindNode shows. See\n"
            "       docs/export-shortcut.md — it makes extraction exact.",
            file=sys.stderr,
        )
    return 0


def _via_shortcut(document, plain: bool, shortcut_name: str) -> int:
    """Export through MindNode's own exporter, for maps the library cannot show."""
    try:
        text = shortcut.export(document.title, name=shortcut_name)
    except ShortcutError as error:
        print(
            f"arete: MindNode's exporter could not read {document.title!r} — {error}.\n"
            "       Falling back to the library snapshot, which can lag the app.",
            file=sys.stderr,
        )
        return _from_snapshot(document, plain)

    if plain:
        # --plain promises bullets that feed back into arete, so MindNode's own
        # formatting is re-rendered through the same parser an import would use.
        rows = parse(text)
        if not rows:
            print(
                f"arete: {shortcut_name!r} returned text with no list in it.",
                file=sys.stderr,
            )
            return 1

        rows = lift_single_root(rows)

        for row in rows:
            print(f"{'  ' * row.depth}- {row.text}".rstrip())
        print(
            f"{len(rows)} nodes from “{document.title}” "
            f"via {shortcut_name!r}, re-rendered for round-tripping",
            file=sys.stderr,
        )
        return 0

    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    print(
        f"“{document.title}” exported by MindNode itself, via {shortcut_name!r}",
        file=sys.stderr,
    )
    return 0


def _from_snapshot(document, plain: bool, quiet: bool = False) -> int:
    """Decode the library's base snapshot. Fast, but it can lag the app."""
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
            f"arete: cannot read {document.title!r} from the library — {error}.\n"
            "       MindNode's own exporter would work: build the export Shortcut\n"
            "       once (docs/export-shortcut.md), or export by hand with\n"
            "       File > Export > Markdown Text.",
            file=sys.stderr,
        )
        return 1

    sys.stdout.write(markdown.render(root, heading=not plain))
    if not quiet:
        print(
            f"{len(root)} nodes from “{document.title}”, read from the library "
            "snapshot — which can lag what MindNode shows",
            file=sys.stderr,
        )
    return 0


def do_extract(name: str, plain: bool, shortcut_name: str,
               from_snapshot: bool = False) -> int:
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
    if from_snapshot:
        return _from_snapshot(document, plain)

    # MindNode's own exporter is authoritative by construction: it reads the
    # live document. The library snapshot is only a base, and nothing in the
    # library reliably says how far behind it is — so the exporter goes first
    # whenever it is available, and the snapshot is the no-setup fallback.
    if shortcut.installed(shortcut_name):
        return _via_shortcut(document, plain, shortcut_name)
    return _from_snapshot(document, plain)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_documents:
        return do_list()
    if args.extract:
        return do_extract(args.extract, args.plain, args.shortcut,
                          args.from_snapshot)

    text, default_title = _read_input(args)
    rows = parse(text, args.tab_stop)
    if not rows:
        print("arete: no non-blank lines on input", file=sys.stderr)
        return 1

    title = args.title or default_title
    if args.tags:
        # FreeMind is the only importer that turns a trailing #word into a real
        # tag. It is opt-in because the same parsing silently eats the number
        # out of a line like "issue #42", which OPML preserves verbatim.
        document, extension = freemind.render(rows, title), "mm"
    else:
        document, extension = render_opml(rows, title), "opml"

    if args.opml:
        sys.stdout.write(document)
        return 0

    result = import_document(document, title, extension, timeout=args.timeout)
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
