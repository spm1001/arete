"""Reading lists of the shapes people actually paste."""

from arete.outline import Row, depth_counts, lift_single_root, parse


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


# --- Markdown headings as hierarchy ----------------------------------------
#
# MindNode's own Markdown export uses #/##/### for the upper levels and
# indented bullets below, so heading level has to count as depth. A parser
# that ignored it flattened a 93-node map to two levels.

def test_heading_level_sets_depth():
    assert depths(parse("# One\n## Two\n### Three\n")) == [0, 1, 2]


def test_bullets_hang_off_the_last_heading():
    rows = parse("# Root\n## Branch\n- leaf\n")
    assert depths(rows) == [0, 1, 2]
    assert texts(rows) == ["Root", "Branch", "leaf"]


def test_bullet_indentation_stacks_on_the_heading_depth():
    rows = parse("# Root\n## Branch\n- leaf\n\t- deeper\n")
    assert depths(rows) == [0, 1, 2, 3]


def test_a_later_heading_resets_the_bullet_depth():
    rows = parse("# Root\n## A\n- a1\n## B\n- b1\n")
    assert list(zip(depths(rows), texts(rows))) == [
        (0, "Root"), (1, "A"), (2, "a1"), (1, "B"), (2, "b1"),
    ]


def test_a_heading_jump_is_taken_at_face_value():
    # MindNode does not skip levels, but a hand-written document might.
    assert depths(parse("# One\n### Three\n- leaf\n")) == [0, 2, 3]


def test_an_untitled_heading_is_kept_so_children_stay_put():
    # Dropping it would make "child" a sibling of "Named" rather than its
    # niece — plausible-looking and wrong.
    rows = parse("# Root\n## Named\n## \n- child\n")
    assert list(zip(depths(rows), texts(rows))) == [
        (0, "Root"), (1, "Named"), (1, ""), (2, "child"),
    ]


def test_a_bare_hash_run_is_an_untitled_heading_not_text():
    rows = parse("# Root\n###\n")
    assert texts(rows) == ["Root", ""]


def test_more_than_six_hashes_is_not_a_heading():
    assert texts(parse("####### seven\n")) == ["####### seven"]


def test_a_list_with_no_headings_is_unaffected():
    assert depths(parse("a\n\tb\n\t\tc\n")) == [0, 1, 2]


def test_tab_indented_bullets_under_headings():
    # Exactly the shape MindNode exports.
    source = "# Root\n## Branch\n- one\n\t- two\n\t\t- three\n"
    assert depths(parse(source)) == [0, 1, 2, 3, 4]


# --- Making extract and import inverses -------------------------------------

def test_lift_single_root_drops_the_root_and_lifts_the_rest():
    rows = parse("# Root\n## Branch\n- leaf\n")
    assert [(r.depth, r.text) for r in lift_single_root(rows)] == [
        (0, "Branch"), (1, "leaf"),
    ]


def test_lift_single_root_leaves_a_flat_list_alone():
    # Several top-level rows is a list of branches, not a root plus children.
    rows = parse("a\nb\nc\n")
    assert lift_single_root(rows) == rows


def test_lift_single_root_leaves_rows_alone_when_the_first_is_indented():
    rows = parse("  a\nb\n")
    assert lift_single_root(rows) == rows


def test_lift_single_root_on_no_rows():
    assert lift_single_root([]) == []


def test_lift_single_root_on_a_root_with_nothing_under_it():
    assert lift_single_root(parse("# Only\n")) == []


def test_round_trip_shape_survives_lifting():
    # The invariant behind: arete --extract X --plain | arete --stdin --title X
    source = "# Root\n## A\n- a1\n\t- a2\n## B\n- b1\n"
    lifted = lift_single_root(parse(source))
    text = "\n".join(f"{'  ' * r.depth}- {r.text}" for r in lifted) + "\n"
    assert parse(text) == lifted
