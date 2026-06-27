#!/usr/bin/env python3
"""AppList entrypoint."""

import multiprocessing

multiprocessing.freeze_support()

import ctypes
import sys
from typing import List, Optional

from applist.cli import run_cli


def _set_dpi_awareness() -> None:
    """Enable high-DPI rendering on Windows when available."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError, ValueError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError, ValueError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    """Run CLI mode when arguments are present, otherwise open the GUI."""
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        return run_cli(argv)

    try:
        from applist.ui import AppListWindow
    except ImportError as exc:
        print(
            "AppList GUI dependencies are missing. Run: py -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        print(f"Import error: {exc}", file=sys.stderr)
        return 1

    _set_dpi_awareness()
    app = AppListWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
