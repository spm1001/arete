"""Arete — Turn a flat list into a MindNode mind map, via OPML import."""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("arete")
except PackageNotFoundError:  # running from source (PYTHONPATH), not installed
    __version__ = "0.0.0+dev"

from arete.opml import render
from arete.outline import Row, parse

__all__ = ["Row", "parse", "render", "__version__"]
