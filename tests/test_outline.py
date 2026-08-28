"""Reading lists of the shapes people actually paste."""

from arete.outline import Row, depth_counts, parse


def texts(rows):
    return [row.text for row in rows]


def depths(rows):
    return [row.depth for row in rows]


def test_flat_list_is_all_depth_zero():
    assert depths(parse("one\ntwo\nthree\n")) == [0, 0, 0]


def test_blank_lines_are_dropped():
    assert texts(parse("one\n\n\ntwo\n")) == ["one", "two"]


def test_empty_input_gives_no_rows():
    assert parse("") == []
    assert parse("\n  \n\t\n") == []


def test_tab_indentation():
    assert depths(parse("a\n\tb\n\t\tc\n")) == [0, 1, 2]


def test_two_space_indentation():
    assert depths(parse("a\n  b\n    c\n")) == [0, 1, 2]


def test_four_space_indentation():
    assert depths(parse("a\n    b\n        c\n")) == [0, 1, 2]


def test_indent_unit_is_inferred_not_assumed():
    # Three-space indentation is unusual but unambiguous, and must not be
    # rounded down to zero levels by a hardcoded unit.
    assert depths(parse("a\n   b\n      c\n")) == [0, 1, 2]


def test_mixed_tabs_and_spaces_in_one_list():
    # What a paste assembled from two sources looks like.
    rows = parse("a\n\tb\nc\n    d\n")
    assert depths(rows) == [0, 1, 0, 1]


def test_markdown_bullets_are_stripped():
    assert texts(parse("- one\n* two\n+ three\n• four\n")) == [
        "one", "two", "three", "four",
    ]


def test_numbering_is_stripped():
    assert texts(parse("1. one\n2) two\na. three\n")) == ["one", "two", "three"]


def test_only_the_outermost_marker_is_stripped():
    # "- 1. dedupe" is a bulleted item whose text is numbered by its author.
    # Eating both markers would quietly rewrite what they typed.
    assert texts(parse("- 1. dedupe\n")) == ["1. dedupe"]


def test_headings_lose_their_hashes():
    assert texts(parse("# Title\n## Sub\n")) == ["Title", "Sub"]


def test_a_lone_marker_is_not_an_item():
    assert parse("-\n*\n") == []


def test_text_is_stripped_of_surrounding_space():
    assert texts(parse("  padded  \n")) == ["padded"]


def test_tab_stop_is_configurable():
    # With a tab worth 2 columns, a tab and two spaces are the same depth.
    rows = parse("a\n\tb\n  c\n", tab_stop=2)
    assert depths(rows) == [0, 1, 1]


def test_depth_counts_summarises_the_shape():
    rows = [Row(0, "a"), Row(1, "b"), Row(1, "c")]
    assert depth_counts(rows) == {0: 1, 1: 2}


def test_deep_nesting_is_preserved():
    source = "".join("\t" * depth + f"level {depth}\n" for depth in range(25))
    assert depths(parse(source)) == list(range(25))


def test_horizontal_rules_are_not_items():
    assert parse("a\n---\nb\n***\nc\n___\n") == [
        Row(0, "a"), Row(0, "b"), Row(0, "c"),
    ]


def test_a_symbol_only_item_is_still_an_item():
    # A rule is punctuation used as a separator; an emoji is a node someone meant.
    assert [row.text for row in parse("🎯\n")] == ["🎯"]
