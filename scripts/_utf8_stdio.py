"""Utilities for forcing UTF-8 stdio in Windows-hosted scripts."""

from __future__ import annotations

import io
import sys


def configure_utf8_stdio() -> None:
    """Wrap Windows stdio streams in UTF-8 text wrappers when possible."""
    if sys.platform != "win32":
        return

    if hasattr(sys.stdin, "buffer"):
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
