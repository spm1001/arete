"""The parts of the MindNode integration that can be tested without the app."""

from arete.mindnode import safe_filename


def test_plain_titles_are_left_alone():
    assert safe_filename("In my work I am") == "In my work I am"


def test_brackets_and_punctuation_are_kept():
    assert safe_filename("Q3 themes (2026), draft-2 & co's") == (
        "Q3 themes (2026), draft-2 & co's"
    )


def test_path_separators_cannot_escape_the_filename():
    assert "/" not in safe_filename("a/b")
    assert safe_filename("../../etc/passwd").count("_") >= 1


def test_empty_or_punctuation_only_titles_get_a_fallback():
    assert safe_filename("   ") == "Imported list"
    assert safe_filename("...") == "Imported list"
    assert safe_filename("") == "Imported list"


def test_unicode_titles_are_preserved():
    # \w is unicode-aware, so accented titles should not be mangled.
    assert safe_filename("Café thèmes") == "Café thèmes"
