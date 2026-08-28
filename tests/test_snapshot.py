"""Reading snapshots, and refusing to read ones we cannot trust.

Fixtures are synthesised rather than copied from a real library, so these
tests say nothing about whether MindNode's own files still match — that is
what `read` against a real map checks, and what its invariants guard.
"""

import pytest

from arete import snapshot
from arete.snapshot import SnapshotError
from tests.test_wire import msg, num


def node_record(node_id: bytes, title: str) -> bytes:
    title_block = msg(11, msg(1, msg(4, msg(1, title.encode()))))
    return msg(2, msg(1, node_id) + msg(2, title_block))


def edge(child: bytes, parent: bytes | None, order: int | None) -> bytes:
    body = msg(1, child)
    if parent is not None:
        body += msg(2, parent)
    if order is not None:
        body += msg(4, msg(1, num(2, order)))
    return msg(2, body)


def build(nodes, edges, version=10, with_hierarchy=True):
    """nodes: [(id, title)]; edges: [(child, parent|None, order|None)]"""
    holder = msg(1, b"\x00" * 16)
    for node_id, title in nodes:
        holder += node_record(node_id, title)
    if with_hierarchy:
        hierarchy = msg(1, b"\xff" * 16)
        for child, parent, order in edges:
            hierarchy += edge(child, parent, order)
        holder += msg(3, hierarchy)
    body = b""
    if version is not None:
        body += num(snapshot.MAGIC_VERSION, version)
    return body + msg(snapshot.MAGIC_DOCUMENT, msg(1, holder))


ROOT = b"\x01" * 16
A = b"\x02" * 16
B = b"\x03" * 16
C = b"\x04" * 16


def test_reads_a_simple_tree():
    data = build(
        [(ROOT, "Centre"), (A, "alpha"), (B, "beta")],
        [(ROOT, None, 200), (A, ROOT, 200), (B, ROOT, 400)],
    )
    root = snapshot.read(data)
    assert root.title == "Centre"
    assert [k.title for k in root.children] == ["alpha", "beta"]


def test_sort_keys_order_siblings_not_insertion_order():
    data = build(
        [(ROOT, "Centre"), (A, "second"), (B, "third"), (C, "first")],
        [(ROOT, None, 200), (A, ROOT, 400), (B, ROOT, 600), (C, ROOT, 200)],
    )
    assert [k.title for k in snapshot.read(data).children] == [
        "first", "second", "third",
    ]


def test_nesting_is_recovered():
    data = build(
        [(ROOT, "Centre"), (A, "branch"), (B, "leaf")],
        [(ROOT, None, 200), (A, ROOT, 200), (B, A, 200)],
    )
    root = snapshot.read(data)
    assert [(d, n.title) for d, n in root.walk()] == [
        (0, "Centre"), (1, "branch"), (2, "leaf"),
    ]


def test_len_counts_the_whole_tree():
    data = build(
        [(ROOT, "Centre"), (A, "a"), (B, "b")],
        [(ROOT, None, 200), (A, ROOT, 200), (B, A, 200)],
    )
    assert len(snapshot.read(data)) == 3


def test_version_is_reported():
    # version() reads the marker without decoding the tree, so a bare root is fine.
    assert snapshot.version(build([(ROOT, "x")], [(ROOT, None, 0)])) == 10


def test_missing_version_marker_is_refused():
    data = build([(ROOT, "x")], [(ROOT, None, 0)], version=None)
    with pytest.raises(SnapshotError, match="no version marker"):
        snapshot.read(data)


def test_unverified_version_is_refused():
    # A newer MindNode could reorganise the layout; guessing would risk
    # emitting a confidently wrong tree.
    data = build([(ROOT, "x")], [(ROOT, None, 0)], version=99)
    with pytest.raises(SnapshotError, match="version 99 has not been verified"):
        snapshot.read(data)


@pytest.mark.parametrize("version", snapshot.KNOWN_VERSIONS)
def test_every_known_version_is_accepted(version):
    data = build(
        [(ROOT, "x"), (A, "y")],
        [(ROOT, None, 0), (A, ROOT, 200)],
        version=version,
    )
    assert snapshot.read(data).title == "x"


def test_a_childless_root_is_refused():
    # Every MindNode document whose content lives outside the snapshot ships a
    # ~324-byte base holding one childless node titled "Mind Map". Emitting it
    # would report a populated map as empty, which is what happened to
    # "My Areas of Focus" on 2026-08-28 before this guard existed.
    data = build([(ROOT, "Mind Map")], [(ROOT, None, 200)])
    with pytest.raises(SnapshotError, match="single node with no children"):
        snapshot.read(data)


def test_a_childless_root_is_refused_whatever_it_is_called():
    # The default title is localised, so the guard keys on shape not wording.
    data = build([(ROOT, "Carte heuristique")], [(ROOT, None, 200)])
    with pytest.raises(SnapshotError, match="single node with no children"):
        snapshot.read(data)


def test_missing_hierarchy_is_refused():
    data = build([(ROOT, "x")], [], with_hierarchy=False)
    with pytest.raises(SnapshotError, match="no hierarchy section"):
        snapshot.read(data)


def test_no_nodes_is_refused():
    data = build([], [], with_hierarchy=True)
    with pytest.raises(SnapshotError, match="no nodes found"):
        snapshot.read(data)


def test_two_roots_are_refused():
    data = build(
        [(ROOT, "one"), (A, "two")],
        [(ROOT, None, 200), (A, None, 400)],
    )
    with pytest.raises(SnapshotError, match="exactly one root"):
        snapshot.read(data)


def test_an_unreachable_node_is_refused():
    # A node with no hierarchy entry would silently vanish from the output.
    data = build(
        [(ROOT, "Centre"), (A, "attached"), (B, "orphan")],
        [(ROOT, None, 200), (A, ROOT, 200)],
    )
    with pytest.raises(SnapshotError, match="not reachable"):
        snapshot.read(data)


def test_a_cycle_is_refused_rather_than_looping():
    # Two nodes parenting each other leaves no root at all.
    data = build(
        [(A, "a"), (B, "b")],
        [(A, B, 200), (B, A, 200)],
    )
    with pytest.raises(SnapshotError):
        snapshot.read(data)


def test_an_empty_title_is_kept_not_dropped():
    data = build(
        [(ROOT, "Centre"), (A, "")],
        [(ROOT, None, 200), (A, ROOT, 200)],
    )
    assert [k.title for k in snapshot.read(data).children] == [""]


def test_unicode_titles_survive():
    data = build(
        [(ROOT, "Café 🎯"), (A, "Ångström")],
        [(ROOT, None, 200), (A, ROOT, 200)],
    )
    root = snapshot.read(data)
    assert root.title == "Café 🎯"
    assert root.children[0].title == "Ångström"


def test_not_a_snapshot_at_all_is_refused():
    with pytest.raises(SnapshotError):
        snapshot.read(b"this is not protobuf at all, not even close")
