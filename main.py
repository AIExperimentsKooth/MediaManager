#!/usr/bin/env python3
"""
Media Manager - A Python-based GUI application for reading EPUB and PDF books
with progress tracking.

Usage: python main.py
"""

import sys
import os

# Ensure the app directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import MediaManagerApp


def main():
    app = MediaManagerApp()
    app.run()


if __name__ == "__main__":
    main()
