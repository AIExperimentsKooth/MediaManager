#!/usr/bin/env python3
"""
PDF Reader - Reads and displays PDF books in the GUI with progress tracking.
Uses PyPDF2/pypdf for text extraction.
"""

import tkinter as tk
from tkinter import ttk
import os
import re


class PdfReader:
    """PDF reader widget that displays book content in a scrollable text area."""

    def __init__(self, parent, filepath, book_manager, status_callback):
        self.parent = parent
        self.filepath = filepath
        self.book_manager = book_manager
        self.status_callback = status_callback

        self.pages = []  # list of page text strings
        self.current_page = 0
        self.total_pages = 0

        self._parse_pdf()

    def _parse_pdf(self):
        """Parse the PDF file and extract text from all pages."""
        if not os.path.exists(self.filepath):
            raise FileNotFoundError("PDF file not found: {}".format(self.filepath))

        reader = None
        try:
            from PyPDF2 import PdfReader as PyPdfReader
            reader = PyPdfReader(self.filepath)
        except ImportError:
            try:
                from pypdf import PdfReader as NewPdfReader
                reader = NewPdfReader(self.filepath)
            except ImportError:
                raise ImportError(
                    "No PDF library found. Please install one:\n"
                    "  pip install PyPDF2\n"
                    "  or\n"
                    "  pip install pypdf"
                )

        self.total_pages = len(reader.pages)

        if self.total_pages == 0:
            raise ValueError("PDF has no pages")

        # Extract text from each page
        for i in range(self.total_pages):
            try:
                text = reader.pages[i].extract_text()
                if text is None:
                    text = ""
            except Exception:
                text = "[Could not extract text from page {}]".format(i + 1)
            self.pages.append(text)

        # Restore saved position
        progress = self.book_manager.get_progress(self.filepath)
        if progress:
            self.current_page = min(progress["position"], self.total_pages - 1)

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
            maximum=self.total_pages, style="Progress.TProgressbar"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.progress_label = ttk.Label(progress_frame, text="", style="Meta.TLabel")
        self.progress_label.pack(side=tk.RIGHT)

        # Page navigation
        nav_frame = ttk.Frame(self.parent)
        nav_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(nav_frame, text="<< Prev", style="Nav.TButton", command=self._prev_page).pack(side=tk.LEFT, padx=2)
        self.page_label = ttk.Label(nav_frame, text="", style="Meta.TLabel")
        self.page_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text="Next >>", style="Nav.TButton", command=self._next_page).pack(side=tk.LEFT, padx=2)

        # Page jump
        jump_frame = ttk.Frame(nav_frame)
        jump_frame.pack(side=tk.RIGHT)
        self.page_var = tk.StringVar()
        page_entry = ttk.Entry(jump_frame, textvariable=self.page_var, width=6)
        page_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(jump_frame, text="Go", command=self._jump_to_page).pack(side=tk.LEFT, padx=2)

        # Font size controls
        font_frame = ttk.Frame(nav_frame)
        font_frame.pack(side=tk.RIGHT, padx=10)
        self.font_size = tk.IntVar(value=12)
        ttk.Button(font_frame, text="A-", width=3, command=self._decrease_font).pack(side=tk.LEFT, padx=1)
        ttk.Button(font_frame, text="A+", width=3, command=self._increase_font).pack(side=tk.LEFT, padx=1)

        # Text display area
        text_frame = ttk.Frame(self.parent)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_area = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", self.font_size.get()),
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
        self.text_area.bind("<Next>", lambda e: self._next_page())
        self.text_area.bind("<Prior>", lambda e: self._prev_page())
        self.text_area.bind("<Right>", lambda e: self._next_page())
        self.text_area.bind("<Left>", lambda e: self._prev_page())

        # Display current page
        self._display_page(self.current_page)

    def _display_page(self, index):
        """Display a specific page."""
        if index < 0 or index >= self.total_pages:
            return

        self.current_page = index
        text = self.pages[index]

        self.text_area.delete("1.0", tk.END)
        if text.strip():
            self.text_area.insert(tk.END, text)
        else:
            self.text_area.insert(tk.END, "[No extractable text on page {}]".format(index + 1))
        self.text_area.see("1.0")

        # Update UI
        self.page_label.config(text="Page {}/{}".format(index + 1, self.total_pages))
        self.progress_bar["value"] = index + 1

        pct = (index + 1) / self.total_pages * 100
        self.progress_label.config(text="{:.0f}%".format(pct))

        # Save progress
        self.book_manager.update_progress(
            self.filepath,
            position=index,
            total=self.total_pages,
            percent=pct,
        )

        self.status_callback("Page {}/{}".format(index + 1, self.total_pages))

    def _prev_page(self):
        if self.current_page > 0:
            self._display_page(self.current_page - 1)

    def _next_page(self):
        if self.current_page < self.total_pages - 1:
            self._display_page(self.current_page + 1)

    def _jump_to_page(self):
        """Jump to a specific page number."""
        try:
            page_num = int(self.page_var.get())
            if 1 <= page_num <= self.total_pages:
                self._display_page(page_num - 1)
            else:
                self.status_callback("Page number must be between 1 and {}".format(self.total_pages))
        except ValueError:
            self.status_callback("Invalid page number")

    def _increase_font(self):
        """Increase font size."""
        if self.font_size.get() < 24:
            self.font_size.set(self.font_size.get() + 1)
            self.text_area.config(font=("Segoe UI", self.font_size.get()))

    def _decrease_font(self):
        """Decrease font size."""
        if self.font_size.get() > 8:
            self.font_size.set(self.font_size.get() - 1)
            self.text_area.config(font=("Segoe UI", self.font_size.get()))
