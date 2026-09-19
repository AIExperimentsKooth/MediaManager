#!/usr/bin/env python3
"""
Media Manager Application - Main GUI and orchestration.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import re

from book_manager import BookManager
from epub_reader import EpubReader
from pdf_reader import PdfReader


APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROGRESS_FILE = os.path.join(APP_DIR, "progress.json")


class MediaManagerApp:
    """Main Media Manager application."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Media Manager")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        # Set up a nice style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._configure_styles()

        # Book manager handles library + progress
        self.book_manager = BookManager(PROGRESS_FILE)

        # Current reader (None when in library view)
        self.current_reader = None

        # Build the UI
        self._build_ui()

        # Load library
        self._refresh_library()

    def _configure_styles(self):
        self.style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        self.style.configure("Subtitle.TLabel", font=("Segoe UI", 11))
        self.style.configure("BookCard.TFrame", padding=10)
        # Progressbar style must inherit layout from base Horizontal.TProgressbar
        self.style.layout("Progress.TProgressbar", self.style.layout("Horizontal.TProgressbar"))
        self.style.configure("Progress.TProgressbar", thickness=14)
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        self.style.configure("Meta.TLabel", font=("Segoe UI", 10))
        self.style.configure("Reader.TText", font=("Segoe UI", 12), padding=20)
        self.style.configure("Nav.TButton", font=("Segoe UI", 11), padding=8)
        self.style.configure("Toolbar.TButton", font=("Segoe UI", 10), padding=6)
        self.style.configure("Status.TLabel", font=("Segoe UI", 9), foreground="#666")

    def _build_ui(self):
        """Build the main application UI with a notebook (tabs)."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Library tab
        self.library_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.library_frame, text="  Library  ")
        self._build_library_tab()

        # Reader tab (hidden until a book is opened)
        self.reader_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.reader_frame, text="  Reader  ")
        self._build_reader_tab()

        # Status bar
        self.status_bar = ttk.Label(
            self.root, text="Ready", style="Status.TLabel", anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # --- Library Tab ---

    def _build_library_tab(self):
        frame = self.library_frame

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Button(
            toolbar, text="Add Book", command=self._add_book
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            toolbar, text="Remove Book", command=self._remove_book
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            toolbar, text="Refresh", command=self._refresh_library
        ).pack(side=tk.LEFT, padx=5)

        # Search
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_library())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))

        # Book list (Treeview)
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("title", "author", "type", "progress", "last_read")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("title", text="Title")
        self.tree.heading("author", text="Author")
        self.tree.heading("type", text="Type")
        self.tree.heading("progress", text="Progress")
        self.tree.heading("last_read", text="Last Read")

        self.tree.column("title", width=300, anchor=tk.W)
        self.tree.column("author", width=180, anchor=tk.W)
        self.tree.column("type", width=60, anchor=tk.CENTER)
        self.tree.column("progress", width=100, anchor=tk.CENTER)
        self.tree.column("last_read", width=150, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to open
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Detail panel at bottom
        detail_frame = ttk.Frame(frame)
        detail_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.detail_label = ttk.Label(detail_frame, text="Select a book to see details", style="Meta.TLabel")
        self.detail_label.pack(side=tk.LEFT)

        ttk.Button(
            detail_frame, text="Open Book", style="Nav.TButton", command=self._open_selected_book
        ).pack(side=tk.RIGHT, padx=5)

    def _refresh_library(self):
        """Reload the book list from disk."""
        self.tree.delete(*self.tree.get_children())
        books = self.book_manager.get_all_books()
        for book in books:
            progress = self.book_manager.get_progress(book["path"])
            pct = "{:.0f}%".format(progress["percent"]) if progress else "0%"
            last_read = progress.get("last_read", "-") if progress else "-"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    book["title"],
                    book["author"],
                    book["type"].upper(),
                    pct,
                    last_read,
                ),
                iid=book["path"],
            )
        self._set_status("{} book(s) in library".format(len(books)))

    def _filter_library(self):
        """Filter the tree by search text."""
        query = self.search_var.get().lower()
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            title = str(values[0]).lower()
            author = str(values[1]).lower()
            if query in title or query in author:
                self.tree.item(item, hidden=False)
            else:
                self.tree.item(item, hidden=True)

    def _on_tree_double_click(self, event):
        self._open_selected_book()

    def _add_book(self):
        """Open file dialog to add EPUB or PDF books."""
        files = filedialog.askopenfilenames(
            title="Select Books",
            filetypes=[
                ("EPUB files", "*.epub"),
                ("PDF files", "*.pdf"),
                ("All supported", "*.epub *.pdf"),
                ("All files", "*.*"),
            ],
        )
        if not files:
            return

        added = 0
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in (".epub", ".pdf"):
                self.book_manager.add_book(f)
                added += 1
            else:
                messagebox.showwarning("Unsupported", "{} is not an EPUB or PDF file.".format(os.path.basename(f)))

        if added:
            self._refresh_library()
            self._set_status("Added {} book(s)".format(added))

    def _remove_book(self):
        """Remove the selected book from the library."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a book to remove first.")
            return
        path = sel[0]
        title = self.tree.item(path, "values")[0]
        if messagebox.askyesno("Remove Book", "Remove '{}' from your library?\n(The file on disk will NOT be deleted.)".format(title)):
            self.book_manager.remove_book(path)
            self._refresh_library()
            self._set_status("Removed '{}'".format(title))

    def _open_selected_book(self):
        """Open the selected book in the reader tab."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a book to open.")
            return
        path = sel[0]
        book = self.book_manager.get_book(path)
        if not book:
            messagebox.showerror("Error", "Book not found.")
            return

        try:
            if book["type"] == "epub":
                self.current_reader = EpubReader(self.reader_frame, path, self.book_manager, self._set_status)
            else:
                self.current_reader = PdfReader(self.reader_frame, path, self.book_manager, self._set_status)
            self.current_reader.build()
            self.notebook.select(self.reader_frame)
            self._set_status("Opened: {}".format(book["title"]))
        except Exception as e:
            messagebox.showerror("Error", "Could not open book:\n{}".format(e))

    # --- Reader Tab ---

    def _build_reader_tab(self):
        """Placeholder for the reader tab (actual content built by reader classes)."""
        placeholder = ttk.Label(
            self.reader_frame,
            text="Open a book from the Library to start reading.",
            style="Subtitle.TLabel",
        )
        placeholder.pack(expand=True)

    # --- Helpers ---

    def _set_status(self, text):
        self.status_bar.config(text=text)

    def run(self):
        self.root.mainloop()
