"""Pytest configuration – makes the .pyw module importable."""

import importlib.util
import importlib.machinery
import sys
from pathlib import Path

# Register .pyw as a valid Python source extension
importlib.machinery.SOURCE_SUFFIXES.append(".pyw")

# Load youtube_mp3_downloader.pyw as a regular module
_SRC = Path(__file__).resolve().parent.parent / "youtube_mp3_downloader.pyw"
_spec = importlib.util.spec_from_file_location(
    "youtube_mp3_downloader",
    str(_SRC),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["youtube_mp3_downloader"] = _mod
_spec.loader.exec_module(_mod)
