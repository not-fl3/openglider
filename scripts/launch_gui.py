#!/usr/bin/env python3
"""Dedicated GUI launcher used for frozen app builds."""

import multiprocessing

from openglider.gui import start_main_window


def main() -> None:
    # Prevent spawned helper processes in frozen builds from re-running the GUI startup.
    multiprocessing.freeze_support()
    start_main_window()


if __name__ == "__main__":
    main()
