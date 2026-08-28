"""Rendering OPML that MindNode will actually accept."""

import xml.etree.ElementTree as ElementTree

import pytest

from arete.opml import render
from arete.outline import Row, parse


def tree(rows, title="Map"):
    return ElementTree.fromstring(render(rows, title))


def shape(element, depth=0):
    """Flatten the parsed XML back into (depth, text) pairs."""
    out = []
    for child in element.findall("outline"):
        out.append((depth, child.get("text")))
        out.extend(shape(child, depth + 1))
    return out


def test_output_is_well_formed_xml():
    assert tree(parse("a\n\tb\n")) is not None


def test_no_wrapper_root_is_added():
    # MindNode makes the centre node from the document name. A wrapper here
    # produces a second centre node nested inside the first.
    body = tree(parse("a\nb\n"), "Centre").find("body")
    assert [o.get("text") for o in body.findall("outline")] == ["a", "b"]


def test_title_goes_in_the_head():
    assert tree(parse("a\n"), "My map").find("head/title").text == "My map"


def test_nesting_survives_the_round_trip():
    rows = parse("a\n\tb\n\t\tc\n\td\ne\n")
    assert shape(tree(rows).find("body")) == [
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
    # saxutils.escape leaves quotes alone, which yields output that looks
    # right and will not parse. Attributes need the stricter escaping.
    body = tree([Row(0, raw)]).find("body")
    assert body.find("outline").get("text") == raw


def test_unicode_survives_verbatim():
    raw = "Emoji 🎯, accents — Café, naïve, Ångström"
    assert tree([Row(0, raw)]).find("body").find("outline").get("text") == raw


def test_title_is_escaped_too():
    assert tree([Row(0, "x")], 'A & B "C"').find("head/title").text == 'A & B "C"'


def test_a_long_line_is_not_truncated():
    # The claim is about a limit, so test the limit rather than today's input.
    raw = "word " * 2000
    assert tree([Row(0, raw)]).find("body").find("outline").get("text") == raw


def test_many_nodes_all_render():
    rows = [Row(0, f"item {n}") for n in range(2000)]
    assert len(tree(rows).find("body").findall("outline")) == 2000


def test_every_open_tag_is_closed_at_depth():
    rows = parse("".join("\t" * d + f"n{d}\n" for d in range(30)))
    assert shape(tree(rows).find("body")) == [(d, f"n{d}") for d in range(30)]


def test_empty_rows_render_an_empty_body():
    assert tree([]).find("body").findall("outline") == []
