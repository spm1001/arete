"""Rendering a node tree as Markdown."""

from __future__ import annotations

from arete.snapshot import Node


def render(root: Node, heading: bool = True, bullet: str = "-") -> str:
    """Render a tree as nested Markdown bullets.

    The root's *children* always start at the left margin, and the root itself
    appears only as the optional H1. That is what makes extract and import
    inverses of each other: MindNode mints the centre node from the document
    name on import, so a root emitted as a bullet would come back one level
    deeper every round trip.

    With `heading=False` the output feeds straight back in:

        arete --extract X --plain | arete --stdin --title X
    """
    lines: list[str] = []
    if heading:
        lines += [f"# {root.title}".rstrip(), ""]
    for kid in root.children:
        _bullets(kid, 0, lines, bullet)
    return "\n".join(lines) + "\n"


def _bullets(node: Node, depth: int, lines: list[str], bullet: str) -> None:
    lines.append(f"{'  ' * depth}{bullet} {node.title}".rstrip())
    for kid in node.children:
        _bullets(kid, depth + 1, lines, bullet)
