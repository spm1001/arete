"""The Shortcut bridge, with `shortcuts` itself stubbed out."""

import subprocess
from pathlib import Path

import pytest

from arete import shortcut
from arete.shortcut import ShortcutError


class FakeRun:
    """Stands in for subprocess.run, recording what it was asked to do."""

    def __init__(self, listing=("Arete Export", "Other"), returncode=0,
                 output="# Map\n\n- one\n", stderr="", raises=None,
                 list_returncode=0, list_raises=None):
        self.listing = listing
        self.list_raises = list_raises
        self.returncode = returncode
        self.output = output
        self.stderr = stderr
        self.raises = raises
        self.list_returncode = list_returncode
        self.calls = []
        self.payloads = []   # what each run actually received on its input

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[:2] == ["shortcuts", "list"]:
            if self.list_raises is not None:
                raise self.list_raises
            return subprocess.CompletedProcess(
                argv, self.list_returncode, "\n".join(self.listing) + "\n", ""
            )
        if "--input-path" in argv:
            self.payloads.append(
                Path(argv[argv.index("--input-path") + 1]).read_text(encoding="utf-8")
            )
        if self.raises is not None:
            raise self.raises
        if self.output is not None and "--output-path" in argv:
            index = argv.index("--output-path")
            Path(argv[index + 1]).write_text(self.output, encoding="utf-8")
        return subprocess.CompletedProcess(argv, self.returncode, "", self.stderr)


@pytest.fixture
def fake(monkeypatch):
    def install(**kwargs):
        runner = FakeRun(**kwargs)
        monkeypatch.setattr(subprocess, "run", runner)
        return runner
    return install


def test_available_lists_shortcut_names(fake):
    fake(listing=("A", "B"))
    assert shortcut.available() == ["A", "B"]


def test_available_is_none_when_the_command_is_missing(fake):
    fake(list_raises=FileNotFoundError("shortcuts"))
    assert shortcut.available() is None


def test_available_is_none_when_shortcuts_exits_non_zero(fake):
    fake(list_returncode=1)
    assert shortcut.available() is None


def test_installed_is_false_when_shortcuts_cannot_be_listed(fake):
    fake(list_raises=FileNotFoundError("shortcuts"))
    assert shortcut.installed() is False


def test_installed_checks_for_an_exact_name(fake):
    fake(listing=("Arete Export",))
    assert shortcut.installed("Arete Export") is True
    assert shortcut.installed("arete export") is False


def test_export_returns_the_shortcut_output(fake):
    fake(output="# Map\n\n- one\n- two\n")
    assert shortcut.export("Map") == "# Map\n\n- one\n- two\n"


def test_export_passes_the_document_name_as_its_payload(fake):
    runner = fake()
    shortcut.export("My Areas of Focus")
    assert [c for c in runner.calls if c[1] == "run"][0][:3] == [
        "shortcuts", "run", "Arete Export",
    ]
    assert runner.payloads == ["My Areas of Focus"]


def test_export_asks_for_output_but_append_does_not(fake):
    runner = fake(listing=("Arete Export", "Arete Append"))
    shortcut.export("Map")
    shortcut.append("Map", "Parent", "Leaf")
    runs = [c for c in runner.calls if c[1] == "run"]
    assert "--output-path" in runs[0]
    assert "--output-path" not in runs[1]


# --- append ----------------------------------------------------------------

def test_append_sends_three_lines_in_order(fake):
    runner = fake(listing=("Arete Append",))
    shortcut.append("In my work I am 2", "The long game", "a pension")
    assert runner.payloads == ["In my work I am 2\nThe long game\na pension\n"]


def test_append_uses_its_own_default_shortcut_name(fake):
    runner = fake(listing=(shortcut.APPEND_NAME,))
    shortcut.append("M", "P", "N")
    assert [c for c in runner.calls if c[1] == "run"][0][2] == shortcut.APPEND_NAME


def test_append_honours_a_custom_name(fake):
    runner = fake(listing=("Mine",))
    shortcut.append("M", "P", "N", name="Mine")
    assert [c for c in runner.calls if c[1] == "run"][0][2] == "Mine"


def test_append_reports_a_missing_shortcut_by_name(fake):
    fake(listing=("Arete Export",))
    with pytest.raises(ShortcutError, match="no Shortcut named 'Arete Append'"):
        shortcut.append("M", "P", "N")


@pytest.mark.parametrize("field", [0, 1, 2])
def test_a_newline_in_any_field_is_refused(fake, field):
    # The payload is positional, so a newline would shift the fields and attach
    # the node somewhere unintended — plausible-looking and wrong.
    fake(listing=("Arete Append",))
    args = ["Map", "Parent", "Leaf"]
    args[field] = "has\na newline"
    with pytest.raises(ShortcutError, match="contains a newline"):
        shortcut.append(*args)


def test_a_carriage_return_is_refused_too(fake):
    fake(listing=("Arete Append",))
    with pytest.raises(ShortcutError, match="contains a newline"):
        shortcut.append("Map", "Par\rent", "Leaf")


def test_append_surfaces_a_failing_shortcut(fake):
    fake(listing=("Arete Append",), returncode=1, stderr="Node not found", output=None)
    with pytest.raises(ShortcutError, match="Node not found"):
        shortcut.append("M", "P", "N")


def test_append_reports_a_timeout(fake):
    fake(listing=("Arete Append",),
         raises=subprocess.TimeoutExpired(cmd="shortcuts", timeout=60))
    with pytest.raises(ShortcutError, match="did not finish within 60s"):
        shortcut.append("M", "P", "N")


def test_export_honours_a_custom_shortcut_name(fake):
    runner = fake(listing=("Custom One",))
    shortcut.export("Map", name="Custom One")
    assert [c for c in runner.calls if c[1] == "run"][0][2] == "Custom One"


def test_missing_shortcut_is_reported_by_name(fake):
    fake(listing=("Something Else",))
    with pytest.raises(ShortcutError, match="no Shortcut named 'Arete Export'"):
        shortcut.export("Map")


def test_unlistable_shortcuts_is_reported(fake):
    fake(list_returncode=1)
    with pytest.raises(ShortcutError, match="could not list Shortcuts"):
        shortcut.export("Map")


def test_a_failing_shortcut_surfaces_its_error(fake):
    fake(returncode=1, stderr="Document not found", output=None)
    with pytest.raises(ShortcutError, match="Document not found"):
        shortcut.export("Map")


def test_a_shortcut_that_writes_nothing_is_an_error(fake):
    fake(output=None, returncode=0)
    with pytest.raises(ShortcutError, match="produced no output"):
        shortcut.export("Map")


def test_blank_output_is_an_error_not_an_empty_map(fake):
    fake(output="   \n\n")
    with pytest.raises(ShortcutError, match="returned nothing"):
        shortcut.export("Map")


def test_a_timeout_is_reported_with_the_limit(fake):
    fake(raises=subprocess.TimeoutExpired(cmd="shortcuts", timeout=120))
    with pytest.raises(ShortcutError, match="did not finish within 120s"):
        shortcut.export("Map")
