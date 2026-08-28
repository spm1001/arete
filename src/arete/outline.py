"""Reading a human's list into an outline.

The input is whatever someone had on their clipboard: a Markdown list, a
paste from Notes, lines typed into a scratch file. Hierarchy is carried by
leading whitespace, and the unit of indentation is whatever that particular
list happens to use.
"""

from __future__ import annotations

import re
from typing import Iterable, List, NamedTuple, Sequence

# One leading bullet or numbering marker. Only the first is stripped: in
# "- 1. dedupe" the dash is decoration but the "1." is probably the author's
# own numbering, and eating it would silently change what they wrote.
_MARKER = re.compile(r"^\s*(?:[-*+•–—]|\d+[.)]|[a-zA-Z][.)])\s+")
# A heading, title optional: MindNode exports an untitled node as bare "###".
_HEADING = re.compile(r"^(#{1,6})(?:\s+(.*))?$")
# A line of nothing but marker or rule characters — "-", "---", "***",
# a Setext underline. A separator in the source, never a node.
_RULE = re.compile(r"^\s*[-*+_=•–—]+\s*$")


class Row(NamedTuple):
    """One line of the list, with its indent expressed in whole levels."""

    depth: int
    text: str


def _indent_columns(line: str, tab_stop: int) -> int:
    columns = 0
    for char in line:
        if char == "\t":
            columns += tab_stop
        elif char == " ":
            columns += 1
        else:
            break
    return columns


def _clean(line: str) -> str:
    return _MARKER.sub("", line).strip()


def parse(text: str, tab_stop: int = 4) -> List[Row]:
    """Read a list into rows whose depth counts levels, not columns.

    The indent unit is inferred as the smallest gap between two indent widths
    that actually occur, so tab-, 2-space- and 4-space-indented lists all come
    out with the same depths. Mixed indentation in one list works too, which
    matters because that is exactly what a paste from two sources looks like.
    """
    # Markdown headings carry hierarchy of their own, and a heading's level is
    # absolute where an indent is relative. MindNode's own Markdown export uses
    # both — #/##/### for the upper levels, then indented bullets — so a parser
    # that ignored heading level would flatten a whole map to two levels.
    measured: list[tuple[int, int, str]] = []  # (heading level or 0, columns, text)
    for line in text.splitlines():
        if not line.strip() or _RULE.match(line):
            continue
        heading = _HEADING.match(line.strip())
        if heading:
            # An untitled heading is kept, not dropped: its level is what holds
            # its children in place, and discarding it would silently re-parent
            # a whole subtree one level up — plausible-looking and wrong.
            measured.append((len(heading.group(1)), 0,
                             _clean(heading.group(2) or "")))
            continue
        cleaned = _clean(line)
        if cleaned:
            measured.append((0, _indent_columns(line, tab_stop), cleaned))

    if not measured:
        return []

    indents = sorted({columns for level, columns, _ in measured if not level})
    steps = [b - a for a, b in zip(indents, indents[1:])]
    unit = min(steps) if steps else 1

    rows: list[Row] = []
    base = 0  # depth that an unindented bullet sits at, set by the last heading
    for level, columns, title in measured:
        if level:
            rows.append(Row(level - 1, title))
            base = level
        else:
            rows.append(Row(base + columns // unit, title))
    return rows


# Known limit: an empty bullet ("-" with nothing after it) is indistinguishable
# from a horizontal rule, so an untitled *leaf* is dropped. Untitled headings are
# kept because their level carries structure; untitled leaves carry none.


def lift_single_root(rows: Sequence[Row]) -> List[Row]:
    """Drop a sole leading depth-0 row and lift the rest up one level.

    MindNode's Markdown export names the map in an H1, which parses as the only
    row at depth 0. Importing that text puts it back as a bullet *under* a new
    centre node minted from the filename, so the map gains a level on every
    round trip. Dropping it matches what `markdown.render` does — the root
    belongs in the title, not in the list.

    Anything else is returned untouched: several depth-0 rows is a flat list,
    which is exactly what should import as several branches.
    """
    tops = [row for row in rows if row.depth == 0]
    if len(tops) == 1 and rows and rows[0].depth == 0:
        return [row._replace(depth=row.depth - 1) for row in rows[1:]]
    return list(rows)


def depth_counts(rows: Iterable[Row]) -> dict[int, int]:
    """How many rows sit at each depth — used for the CLI's summary line."""
    counts: dict[int, int] = {}
    for row in rows:
        counts[row.depth] = counts.get(row.depth, 0) + 1
    return counts
