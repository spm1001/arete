"""Reading a MindNode snapshot into a tree of nodes.

MindNode publishes no schema for this, so every field number below was
recovered by walking the wire format and checking the result against maps
whose contents were known in advance. The layout, for MindNode 2026.4.4
writing serialization versions 9 and 10:

    12345   varint    serialization version
    678910            document
      .1              holder
        .1            canvas meta (16-byte id)
        .2   repeated node record
          .1          node id, 16 bytes
          .2          payload
            .11 .1 .4 .1   title string
        .3            hierarchy
          .1          document id, 16 bytes
          .2 repeated entry
            .1        child node id
            .2        parent node id (absent for the root)
            .4 .1 .2  sort key among siblings — a fractional index,
                      typically 200, 400, 600 … so a node can be
                      reordered without renumbering its siblings

Because those numbers are inferred rather than documented, `read` checks
structural invariants and raises instead of returning a tree it cannot
stand behind. A wrong tree presented confidently is worse than an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Dict, List, Optional

from arete import wire

MAGIC_VERSION = 12345
MAGIC_DOCUMENT = 678910
KNOWN_VERSIONS = (9, 10)


class SnapshotError(ValueError):
    """The snapshot could not be read into a tree we trust."""


@dataclass
class Node:
    title: str
    node_id: str
    children: List["Node"] = dataclass_field(default_factory=list)

    def walk(self, depth: int = 0):
        yield depth, self
        for kid in self.children:
            yield from kid.walk(depth + 1)

    def __len__(self) -> int:
        return sum(1 for _ in self.walk())


def version(data: bytes) -> Optional[int]:
    return wire.scalar(data, MAGIC_VERSION)


def _titles(holder: bytes) -> Dict[str, str]:
    titles: Dict[str, str] = {}
    for record in wire.repeated(holder, 2):
        node_id = wire.child(record, 1)
        if node_id is None:
            continue
        raw = wire.path(record, 2, 11, 1, 4, 1)
        titles[node_id.hex()] = raw.decode("utf-8", "replace") if raw else ""
    return titles


def _edges(holder: bytes):
    """(child_id, parent_id or None, sort_key) for each hierarchy entry."""
    hierarchy = wire.child(holder, 3)
    if hierarchy is None:
        raise SnapshotError("no hierarchy section — snapshot layout has changed")
    out = []
    for entry in wire.repeated(hierarchy, 2):
        child_id = wire.child(entry, 1)
        if child_id is None:
            continue
        parent_id = wire.child(entry, 2)
        order_holder = wire.path(entry, 4, 1)
        order = wire.scalar(order_holder, 2) if order_holder else None
        out.append((child_id.hex(), parent_id.hex() if parent_id else None, order))
    return out


def read(data: bytes) -> Node:
    """Read a snapshot into its root node.

    Raises SnapshotError rather than guessing whenever the structure does not
    match what we verified — an unknown serialization version, a missing
    section, no single root, or nodes the hierarchy does not account for.
    """
    found = version(data)
    if found is None:
        raise SnapshotError("no version marker — not a MindNode snapshot")
    if found not in KNOWN_VERSIONS:
        raise SnapshotError(
            f"serialization version {found} has not been verified "
            f"(known: {', '.join(map(str, KNOWN_VERSIONS))})"
        )

    holder = wire.path(data, MAGIC_DOCUMENT, 1)
    if holder is None:
        raise SnapshotError("no document section — snapshot layout has changed")

    titles = _titles(holder)
    if not titles:
        raise SnapshotError("no nodes found — snapshot layout has changed")

    nodes = {nid: Node(title, nid) for nid, title in titles.items()}
    order: Dict[str, int] = {}
    roots: List[str] = []

    for child_id, parent_id, sort_key in _edges(holder):
        if child_id not in nodes:
            continue  # an entry for something that is not a titled node
        order[child_id] = sort_key if sort_key is not None else 0
        if parent_id in nodes:
            nodes[parent_id].children.append(nodes[child_id])
        else:
            roots.append(child_id)

    if len(roots) != 1:
        raise SnapshotError(
            f"expected exactly one root node, found {len(roots)}"
        )

    root = nodes[roots[0]]
    for node in nodes.values():
        node.children.sort(key=lambda n: (order.get(n.node_id, 0), n.title))

    reachable = len(root)
    if reachable != len(nodes):
        raise SnapshotError(
            f"{len(nodes) - reachable} of {len(nodes)} nodes are not reachable "
            "from the root — the hierarchy did not decode cleanly"
        )
    if not root.children:
        # A new MindNode document ships a ~324-byte base snapshot holding one
        # childless node titled "Mind Map". Every document whose content lives
        # outside the snapshot looks exactly like this, so a childless tree is
        # never worth reporting: there is nothing to extract either way, and
        # emitting it would claim a populated map is empty.
        raise SnapshotError(
            "the snapshot holds a single node with no children, which is what "
            "an unfolded base snapshot looks like"
        )
    return root
