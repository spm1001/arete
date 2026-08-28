"""Rendering outline rows as OPML.

MindNode imports OPML, and that is the whole trick this package rests on:
it will not paste a multi-line list as separate nodes, but it will happily
import one.
"""

from __future__ import annotations

from typing import Sequence
from xml.sax.saxutils import escape as _escape

from arete.outline import Row


def _attr(text: str) -> str:
    """Escape for use inside a double-quoted XML attribute.

    saxutils.escape leaves quotes alone, which produces XML that looks fine
    and will not parse the moment someone's list contains a "quoted" word.
    """
    return _escape(text, {'"': "&quot;", "'": "&apos;"})


def render(rows: Sequence[Row], title: str) -> str:
    """Render rows as an OPML document.

    There is deliberately no wrapper <outline> around the list. MindNode
    creates the centre node itself, from the document name, and hangs every
    top-level <outline> off it — so wrapping the list in a root element of
    our own yields two centre nodes, one inside the other.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        "  <head>",
        f"    <title>{_attr(title)}</title>",
        "  </head>",
        "  <body>",
    ]

    open_depths: list[int] = []
    for depth, text in rows:
        while open_depths and open_depths[-1] >= depth:
            open_depths.pop()
            lines.append(f'    {"  " * len(open_depths)}</outline>')
        lines.append(f'    {"  " * len(open_depths)}<outline text="{_attr(text)}">')
        open_depths.append(depth)

    while open_depths:
        open_depths.pop()
        lines.append(f'    {"  " * len(open_depths)}</outline>')

    lines += ["  </body>", "</opml>", ""]
    return "\n".join(lines)
