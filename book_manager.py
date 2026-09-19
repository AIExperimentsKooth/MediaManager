#!/usr/bin/env python3
"""
Book Manager - Handles the book library and reading progress tracking.
"""

import os
import json
import re
from datetime import datetime


class BookManager:
    """Manages the book library and reading progress."""

    def __init__(self, progress_file):
        self.progress_file = progress_file
        self.library = []  # list of book dicts
        self.progress = {}  # dict keyed by book path
        self._load()

    def _load(self):
        """Load library and progress from disk."""
        # Load library
        library_file = self.progress_file.replace("progress.json", "library.json")
        if os.path.exists(library_file):
            try:
                with open(library_file, "r", encoding="utf-8") as f:
                    self.library = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.library = []
        else:
            self.library = []

        # Load progress
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    self.progress = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.progress = {}
        else:
            self.progress = {}

    def _save_library(self):
        """Save library to disk."""
        library_file = self.progress_file.replace("progress.json", "library.json")
        with open(library_file, "w", encoding="utf-8") as f:
            json.dump(self.library, f, indent=2, ensure_ascii=False)

    def _save_progress(self):
        """Save progress to disk."""
        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)

    def add_book(self, filepath):
        """Add a book to the library."""
        filepath = os.path.abspath(filepath)
        # Check if already in library
        for book in self.library:
            if book["path"] == filepath:
                return

        ext = os.path.splitext(filepath)[1].lower()
        book_type = "epub" if ext == ".epub" else "pdf"

        # Extract metadata
        title = os.path.splitext(os.path.basename(filepath))[0]
        author = "Unknown"

        if book_type == "epub":
            title, author = self._extract_epub_metadata(filepath)
        elif book_type == "pdf":
            title, author = self._extract_pdf_metadata(filepath)

        book = {
            "path": filepath,
            "title": title,
            "author": author,
            "type": book_type,
            "added": datetime.now().isoformat(),
        }
        self.library.append(book)
        self._save_library()

    def remove_book(self, filepath):
        """Remove a book from the library (does not delete the file)."""
        filepath = os.path.abspath(filepath)
        self.library = [b for b in self.library if b["path"] != filepath]
        # Also remove progress
        if filepath in self.progress:
            del self.progress[filepath]
        self._save_library()
        self._save_progress()

    def get_book(self, filepath):
        """Get a book by path."""
        filepath = os.path.abspath(filepath)
        for book in self.library:
            if book["path"] == filepath:
                return book
        return None

    def get_all_books(self):
        """Get all books in the library."""
        return sorted(self.library, key=lambda b: b["title"].lower())

    def get_progress(self, filepath):
        """Get reading progress for a book."""
        filepath = os.path.abspath(filepath)
        return self.progress.get(filepath)

    def update_progress(self, filepath, position, total, percent=None):
        """Update reading progress for a book.

        Args:
            filepath: Path to the book file
            position: Current position (page number or chapter index)
            total: Total pages or chapters
            percent: Optional explicit percentage (0-100)
        """
        filepath = os.path.abspath(filepath)
        if percent is None:
            percent = (position / total * 100) if total > 0 else 0

        self.progress[filepath] = {
            "position": position,
            "total": total,
            "percent": round(percent, 1),
            "last_read": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self._save_progress()

    def _extract_epub_metadata(self, filepath):
        """Extract title and author from an EPUB file."""
        title = os.path.splitext(os.path.basename(filepath))[0]
        author = "Unknown"
        try:
            import zipfile
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(filepath, "r") as zf:
                # Try container.xml to find OPF file
                opf_path = None
                if "META-INF/container.xml" in zf.namelist():
                    container_xml = zf.read("META-INF/container.xml")
                    root = ET.fromstring(container_xml)
                    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
                    rootfile = root.find(".//c:rootfile", ns)
                    if rootfile is not None:
                        opf_path = rootfile.get("full-path")

                if opf_path and opf_path in zf.namelist():
                    opf_xml = zf.read(opf_path)
                    opf_root = ET.fromstring(opf_xml)

                    # Search for dc:title and dc:creator
                    for elem in opf_root.iter():
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag == "title" and elem.text:
                            title = elem.text.strip()
                            break

                    for elem in opf_root.iter():
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag == "creator" and elem.text:
                            author = elem.text.strip()
                            break
        except Exception:
            pass
        return title, author

    def _extract_pdf_metadata(self, filepath):
        """Extract title and author from a PDF file."""
        title = os.path.splitext(os.path.basename(filepath))[0]
        author = "Unknown"
        try:
            # Try PyPDF2 first
            from PyPDF2 import PdfReader as PyPdfReader
            reader = PyPdfReader(filepath)
            meta = reader.metadata
            if meta:
                if meta.title:
                    title = meta.title.strip()
                if meta.author:
                    author = meta.author.strip()
        except ImportError:
            try:
                # Try pypdf
                from pypdf import PdfReader as NewPdfReader
                reader = NewPdfReader(filepath)
                meta = reader.metadata
                if meta:
                    if meta.title:
                        title = meta.title.strip()
                    if meta.author:
                        author = meta.author.strip()
            except ImportError:
                pass
        except Exception:
            pass
        return title, author
