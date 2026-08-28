"""Rendering Markdown, and the invariant that makes extract and import inverses."""

from arete import markdown
from arete.outline import parse
from arete.snapshot import Node


def tree():
    return Node("Centre", "r", [
        Node("first", "a", [Node("one", "a1"), Node("two", "a2")]),
        Node("second", "b"),
    ])


def test_heading_names_the_root_and_children_start_at_the_margin():
    assert markdown.render(tree()) == (
        "# Centre\n"
        "\n"
        "- first\n"
        "  - one\n"
        "  - two\n"
        "- second\n"
    )


def test_plain_output_omits_the_heading():
    assert markdown.render(tree(), heading=False) == (
        "- first\n"
        "  - one\n"
        "  - two\n"
        "- second\n"
    )


def test_the_root_is_never_a_bullet():
    # MindNode mints the centre node from the document name on import, so a
    # root emitted as a bullet comes back one level deeper each round trip.
    assert "- Centre" not in markdown.render(tree(), heading=False)
    assert "- Centre" not in markdown.render(tree())


def test_round_trip_through_the_list_parser_preserves_the_shape():
    # The invariant behind: arete --extract X --plain | arete --stdin --title X
    root = tree()
    rows = parse(markdown.render(root, heading=False))
    expected = [(d, n.title) for kid in root.children for d, n in kid.walk()]
    assert [(r.depth, r.text) for r in rows] == expected


def test_bullet_character_is_configurable():
    assert markdown.render(tree(), heading=False, bullet="*").startswith("* first")


def test_a_root_with_no_children_renders_just_the_heading():
    assert markdown.render(Node("Lonely", "r")) == "# Lonely\n\n"


def test_empty_titles_do_not_leave_trailing_space():
    out = markdown.render(Node("Centre", "r", [Node("", "a")]), heading=False)
    assert out == "-\n"


def test_deep_nesting_indents_two_spaces_per_level():
    node = Node("leaf", "x")
    for depth in range(4):
        node = Node(f"level{depth}", str(depth), [node])
    root = Node("Centre", "r", [node])
    lines = markdown.render(root, heading=False).splitlines()
    assert lines[-1].startswith(" " * 8 + "- leaf")
