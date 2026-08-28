"""Reading a human's list into an outline.

The input is whatever someone had on their clipboard: a Markdown list, a
paste from Notes, lines typed into a scratch file. Hierarchy is carried by
leading whitespace, and the unit of indentation is whatever that particular
list happens to use.
"""

from __future__ import annotations

import re
from typing import Iterable, List, NamedTuple

# One leading bullet or numbering marker. Only the first is stripped: in
# "- 1. dedupe" the dash is decoration but the "1." is probably the author's
# own numbering, and eating it would silently change what they wrote.
_MARKER = re.compile(r"^\s*(?:[-*+•–—]|\d+[.)]|[a-zA-Z][.)])\s+")
_HEADING = re.compile(r"^#+\s+")
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
    return _HEADING.sub("", _MARKER.sub("", line).strip()).strip()


def parse(text: str, tab_stop: int = 4) -> List[Row]:
    """Read a list into rows whose depth counts levels, not columns.

    The indent unit is inferred as the smallest gap between two indent widths
    that actually occur, so tab-, 2-space- and 4-space-indented lists all come
    out with the same depths. Mixed indentation in one list works too, which
    matters because that is exactly what a paste from two sources looks like.
    """
    measured = []
    for line in text.splitlines():
        if not line.strip() or _RULE.match(line):
            continue
        cleaned = _clean(line)
        if cleaned:
            measured.append((_indent_columns(line, tab_stop), cleaned))

    if not measured:
        return []

    widths = sorted({columns for columns, _ in measured})
    steps = [b - a for a, b in zip(widths, widths[1:])]
    unit = min(steps) if steps else 1
    return [Row(columns // unit, text) for columns, text in measured]


def depth_counts(rows: Iterable[Row]) -> dict[int, int]:
    """How many rows sit at each depth — used for the CLI's summary line."""
    counts: dict[int, int] = {}
    for row in rows:
        counts[row.depth] = counts.get(row.depth, 0) + 1
    return counts
