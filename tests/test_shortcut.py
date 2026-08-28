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

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[:2] == ["shortcuts", "list"]:
            if self.list_raises is not None:
                raise self.list_raises
            return subprocess.CompletedProcess(
                argv, self.list_returncode, "\n".join(self.listing) + "\n", ""
            )
        if self.raises is not None:
            raise self.raises
        if self.output is not None:
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


def test_export_passes_the_document_name_as_input(fake):
    runner = fake()
    shortcut.export("My Areas of Focus")
    run_call = [c for c in runner.calls if c[1] == "run"][0]
    input_path = Path(run_call[run_call.index("--input-path") + 1])
    # The temp dir is gone by now, so assert on the argv shape instead.
    assert run_call[:3] == ["shortcuts", "run", "Arete Export"]
    assert input_path.name == "name.txt"


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
