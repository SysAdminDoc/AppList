"""PyInstaller runtime hook for frozen multiprocessing safety."""

import multiprocessing

multiprocessing.freeze_support()
