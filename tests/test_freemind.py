"""Rendering FreeMind XML — the format that carries tags into MindNode."""

import xml.etree.ElementTree as ElementTree

import pytest

from arete import freemind
from arete.outline import Row, parse


def tree(rows, title="Centre"):
    return ElementTree.fromstring(freemind.render(rows, title))


def shape(element, depth=0):
    out = []
    for child in element.findall("node"):
        out.append((depth, child.get("TEXT")))
        out.extend(shape(child, depth + 1))
    return out


def test_output_is_well_formed_xml():
    assert tree(parse("a\n\tb\n")) is not None


def test_the_map_declares_the_version_mindnode_expects():
    assert tree([Row(0, "x")]).get("version") == freemind.VERSION


def test_the_root_node_carries_the_title():
    # Unlike OPML, the root comes from this XML rather than the filename.
    root = tree([Row(0, "child")], "My centre").find("node")
    assert root.get("TEXT") == "My centre"


def test_rows_hang_under_the_root():
    root = tree(parse("a\nb\n")).find("node")
    assert [n.get("TEXT") for n in root.findall("node")] == ["a", "b"]


def test_nesting_survives_the_round_trip():
    rows = parse("a\n\tb\n\t\tc\n\td\ne\n")
    assert shape(tree(rows).find("node")) == [
        (0, "a"), (1, "b"), (2, "c"), (1, "d"), (0, "e"),
    ]


@pytest.mark.parametrize(
    "raw",
    [
        'quotes "like this"',
        "apostrophes 'like this'",
        "ampersand & more",
        "angle <brackets>",
        'everything <at> & "once" \'together\'',
    ],
)
def test_xml_hostile_characters_survive_verbatim(raw):
    root = tree([Row(0, raw)]).find("node")
    assert root.find("node").get("TEXT") == raw


def test_unicode_survives_verbatim():
    raw = "Emoji 🎯, accents — Café, naïve, Ångström"
    assert tree([Row(0, raw)]).find("node").find("node").get("TEXT") == raw


def test_the_title_is_escaped_too():
    assert tree([Row(0, "x")], 'A & B "C"').find("node").get("TEXT") == 'A & B "C"'


def test_hash_tags_are_passed_through_untouched():
    # arete does not parse tags; MindNode's importer does. The renderer's job
    # is only to deliver the text intact.
    raw = "earning enough #Important #Money"
    assert tree([Row(0, raw)]).find("node").find("node").get("TEXT") == raw


def test_a_long_line_is_not_truncated():
    raw = "word " * 2000
    assert tree([Row(0, raw)]).find("node").find("node").get("TEXT") == raw


def test_many_nodes_all_render():
    rows = [Row(0, f"item {n}") for n in range(2000)]
    assert len(tree(rows).find("node").findall("node")) == 2000


def test_deep_nesting_closes_every_node():
    rows = parse("".join("\t" * d + f"n{d}\n" for d in range(30)))
    assert shape(tree(rows).find("node")) == [(d, f"n{d}") for d in range(30)]


def test_no_rows_still_gives_a_root():
    root = tree([]).find("node")
    assert root.get("TEXT") == "Centre"
    assert root.findall("node") == []
