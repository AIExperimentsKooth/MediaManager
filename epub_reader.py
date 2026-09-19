#!/usr/bin/env python3
"""
EPUB Reader - Reads and displays EPUB books in the GUI with progress tracking.
"""

import tkinter as tk
from tkinter import ttk
import os
import re
import html
import zipfile
import xml.etree.ElementTree as ET


class EpubReader:
    """EPUB reader widget that displays book content in a scrollable text area."""

    def __init__(self, parent, filepath, book_manager, status_callback):
        self.parent = parent
        self.filepath = filepath
        self.book_manager = book_manager
        self.status_callback = status_callback

        self.chapters = []  # list of (title, html_content)
        self.current_chapter = 0
        self.total_chapters = 0

        self._parse_epub()

    def _parse_epub(self):
        """Parse the EPUB file and extract chapters."""
        if not os.path.exists(self.filepath):
            raise FileNotFoundError("EPUB file not found: {}".format(self.filepath))

        with zipfile.ZipFile(self.filepath, "r") as zf:
            # Find the OPF file
            opf_path = None
            if "META-INF/container.xml" in zf.namelist():
                container_xml = zf.read("META-INF/container.xml")
                root = ET.fromstring(container_xml)
                ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
                rootfile = root.find(".//c:rootfile", ns)
                if rootfile is not None:
                    opf_path = rootfile.get("full-path")

            if not opf_path:
                # Fallback: search for .opf file
                for name in zf.namelist():
                    if name.endswith(".opf"):
                        opf_path = name
                        break

            if not opf_path:
                raise ValueError("Could not find OPF file in EPUB")

            # Parse the spine to get reading order
            opf_xml = zf.read(opf_path)
            opf_root = ET.fromstring(opf_xml)

            # Get the spine itemrefs
            spine_items = []
            for elem in opf_root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "itemref":
                    idref = elem.get("idref")
                    if idref:
                        spine_items.append(idref)

            # Build a map of id -> href
            id_map = {}
            for elem in opf_root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "item":
                    item_id = elem.get("id")
                    href = elem.get("href")
                    media_type = elem.get("media-type", "")
                    if item_id and href:
                        id_map[item_id] = (href, media_type)

            # Resolve paths relative to OPF directory
            opf_dir = os.path.dirname(opf_path)

            # Extract chapters in spine order
            for itemref in spine_items:
                if itemref in id_map:
                    href, media_type = id_map[itemref]
                    if "html" in media_type or "xml" in media_type:
                        # Resolve the path
                        if opf_dir:
                            full_path = os.path.normpath(os.path.join(opf_dir, href))
                        else:
                            full_path = href

                        if full_path in zf.namelist():
                            content = zf.read(full_path).decode("utf-8", errors="replace")
                            # Extract text content
                            text = self._html_to_text(content)
                            if text.strip():
                                # Try to get a title from the first heading
                                title = self._extract_title(content)
                                if not title:
                                    title = "Chapter {}".format(len(self.chapters) + 1)
                                self.chapters.append((title, text))

            if not self.chapters:
                raise ValueError("No readable content found in EPUB")

        self.total_chapters = len(self.chapters)

        # Restore saved position
        progress = self.book_manager.get_progress(self.filepath)
        if progress:
            self.current_chapter = min(progress["position"], self.total_chapters - 1)

    def _html_to_text(self, html_content):
        """Convert HTML content to plain text."""
        # Remove script and style tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Convert block elements to newlines
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</h[1-6]>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)

        # Remove all remaining tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        text = html.unescape(text)

        # Clean up whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = text.strip()

        return text

    def _extract_title(self, html_content):
        """Try to extract a chapter title from HTML."""
        # Look for h1, h2, or title tag
        for tag in ["h1", "h2", "title"]:
            match = re.search(r"<{}[^>]*>(.*?)</{}>".format(tag, tag), html_content, re.DOTALL | re.IGNORECASE)
            if match:
                title = re.sub(r"<[^>]+>", "", match.group(1))
                title = html.unescape(title).strip()
                if title:
                    return title[:80]  # Limit length
        return None

    def build(self):
        """Build the reader UI in the parent frame."""
        # Clear existing content
        for widget in self.parent.winfo_children():
            widget.destroy()

        # Header
        header = ttk.Frame(self.parent)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))

        book = self.book_manager.get_book(self.filepath)
        title_text = book["title"] if book else os.path.basename(self.filepath)
        author_text = book["author"] if book else ""

        ttk.Label(header, text=title_text, style="Header.TLabel").pack(side=tk.LEFT)
        if author_text:
            ttk.Label(header, text="by {}".format(author_text), style="Meta.TLabel").pack(side=tk.LEFT, padx=(10, 0))

        # Progress bar
        progress_frame = ttk.Frame(self.parent)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_bar = ttk.Progressbar(
            progress_frame, orient=tk.HORIZONTAL, mode="determinate",
            maximum=self.total_chapters, style="Progress.TProgressbar"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.progress_label = ttk.Label(progress_frame, text="", style="Meta.TLabel")
        self.progress_label.pack(side=tk.RIGHT)

        # Chapter navigation
        nav_frame = ttk.Frame(self.parent)
        nav_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(nav_frame, text="<< Prev", style="Nav.TButton", command=self._prev_chapter).pack(side=tk.LEFT, padx=2)
        self.chapter_label = ttk.Label(nav_frame, text="", style="Meta.TLabel")
        self.chapter_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text="Next >>", style="Nav.TButton", command=self._next_chapter).pack(side=tk.LEFT, padx=2)

        # Chapter dropdown
        self.chapter_var = tk.StringVar()
        self.chapter_combo = ttk.Combobox(
            nav_frame, textvariable=self.chapter_var, state="readonly", width=40
        )
        self.chapter_combo.pack(side=tk.LEFT, padx=10)
        self.chapter_combo.bind("<<ComboboxSelected>>", self._on_chapter_select)

        # Populate chapter list
        self.chapter_combo["values"] = ["{}/{}: {}".format(i + 1, self.total_chapters, t) for i, (t, _) in enumerate(self.chapters)]

        # Text display area
        text_frame = ttk.Frame(self.parent)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_area = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 12),
            padx=20,
            pady=20,
            bg="#fffff8",
            relief=tk.FLAT,
        )
        text_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=text_scroll.set)

        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind keyboard shortcuts
        self.text_area.bind("<Next>", lambda e: self._next_chapter())
        self.text_area.bind("<Prior>", lambda e: self._prev_chapter())
        self.text_area.bind("<Right>", lambda e: self._next_chapter())
        self.text_area.bind("<Left>", lambda e: self._prev_chapter())

        # Display current chapter
        self._display_chapter(self.current_chapter)

    def _display_chapter(self, index):
        """Display a specific chapter."""
        if index < 0 or index >= self.total_chapters:
            return

        self.current_chapter = index
        title, text = self.chapters[index]

        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, text)
        self.text_area.see("1.0")

        # Update UI
        self.chapter_label.config(text="Chapter {}/{}: {}".format(index + 1, self.total_chapters, title))
        self.chapter_var.set("{}/{}: {}".format(index + 1, self.total_chapters, title))
        self.progress_bar["value"] = index + 1

        pct = (index + 1) / self.total_chapters * 100
        self.progress_label.config(text="{:.0f}%".format(pct))

        # Save progress
        self.book_manager.update_progress(
            self.filepath,
            position=index,
            total=self.total_chapters,
            percent=pct,
        )

        self.status_callback("Chapter {}/{}: {}".format(index + 1, self.total_chapters, title))

    def _prev_chapter(self):
        if self.current_chapter > 0:
            self._display_chapter(self.current_chapter - 1)

    def _next_chapter(self):
        if self.current_chapter < self.total_chapters - 1:
            self._display_chapter(self.current_chapter + 1)

    def _on_chapter_select(self, event):
        """Handle chapter dropdown selection."""
        selection = self.chapter_var.get()
        # Parse the index from "X/Y: Title"
        match = re.match(r"(\d+)/", selection)
        if match:
            index = int(match.group(1)) - 1
            self._display_chapter(index)
