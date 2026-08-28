"""Rendering outline rows as FreeMind XML.

MindNode imports both OPML and FreeMind, and they differ in one way that
matters: **FreeMind import parses trailing `#word` tokens into real tags,
OPML does not.** So this is the format to use when a list carries tags.

It cuts both ways, which is why `arete` makes it opt-in. MindNode consumes a
trailing *run* of tag tokens and nothing else — measured 2026-08-28 against
MindNode 2026.4.8:

    "ends with #tag"          -> "ends with"          + tag: tag
    "two trailing #one #two"  -> "two trailing"       + tags: one, two
    "digits only #42"         -> "digits only"        + tag: 42
    "tag then word #one and"  -> unchanged, no tags
    "#leading tag"            -> unchanged, no tags
    "C# programming"          -> unchanged, no tags

The middle of that list is the hazard: a list item reading "issue #42" loses
its number to a tag. Under OPML the same text survives verbatim.

Unlike OPML, the root node comes from this XML rather than from the filename,
and the document's name still comes from the filename — so the two are
independent and both are set from the title.
"""

from __future__ import annotations

from typing import Sequence
from xml.sax.saxutils import escape as _escape

from arete.outline import Row

# FreeMind 1.0.1 is what MindNode's importer expects to see declared.
VERSION = "1.0.1"


def _attr(text: str) -> str:
    """Escape for use inside a double-quoted XML attribute."""
    return _escape(text, {'"': "&quot;", "'": "&apos;"})


def render(rows: Sequence[Row], title: str) -> str:
    """Render rows as a FreeMind map whose single root carries `title`."""
    lines = [f'<map version="{VERSION}">', f'  <node TEXT="{_attr(title)}">']

    open_depths: list[int] = []
    for depth, text in rows:
        while open_depths and open_depths[-1] >= depth:
            open_depths.pop()
            lines.append(f'    {"  " * len(open_depths)}</node>')
        lines.append(f'    {"  " * len(open_depths)}<node TEXT="{_attr(text)}">')
        open_depths.append(depth)

    while open_depths:
        open_depths.pop()
        lines.append(f'    {"  " * len(open_depths)}</node>')

    lines += ["  </node>", "</map>", ""]
    return "\n".join(lines)
