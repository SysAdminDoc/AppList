#!/usr/bin/env python3
"""Run AppList as a module."""

import multiprocessing
multiprocessing.freeze_support()

import sys
from .cli import run_cli


def main():
    argv = sys.argv[1:]
    if argv:
        sys.exit(run_cli(argv))
    try:
        from .ui import AppListWindow
    except ImportError as exc:
        print(f"GUI dependencies missing: {exc}", file=sys.stderr)
        sys.exit(1)
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError, ValueError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError, ValueError):
            pass
    app = AppListWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
