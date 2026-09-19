#!/usr/bin/env python3
"""
EPUB Reader - Reads and displays EPUB books in the GUI with progress tracking.
Supports text and inline images.
"""

import tkinter as tk
from tkinter import ttk
import os
import re
import html
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

try:
    from PIL import Image, ImageTk
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


class EpubReader:
    """EPUB reader widget that displays book content (text + images) in a scrollable area."""

    def __init__(self, parent, filepath, book_manager, status_callback):
        self.parent = parent
        self.filepath = filepath
        self.book_manager = book_manager
        self.status_callback = status_callback

        self.chapters = []  # list of (title, content_blocks)
        # content_blocks is a list of tuples: ("text", str) or ("image", bytes, media_type)
        self.current_chapter = 0
        self.total_chapters = 0

        self._image_cache = {}  # path -> PhotoImage

        self._parse_epub()

    def _parse_epub(self):
        """Parse the EPUB file and extract chapters with text and images."""
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
                        if opf_dir:
                            full_path = os.path.normpath(os.path.join(opf_dir, href))
                        else:
                            full_path = href

                        if full_path in zf.namelist():
                            content = zf.read(full_path).decode("utf-8", errors="replace")
                            # Extract content blocks (text + images in order)
                            blocks = self._html_to_blocks(content, zf, full_path)
                            if blocks:
                                title = self._extract_title(content)
                                if not title:
                                    title = "Chapter {}".format(len(self.chapters) + 1)
                                self.chapters.append((title, blocks))

            if not self.chapters:
                raise ValueError("No readable content found in EPUB")

        self.total_chapters = len(self.chapters)

        # Restore saved position
        progress = self.book_manager.get_progress(self.filepath)
        if progress:
            self.current_chapter = min(progress["position"], self.total_chapters - 1)

    def _html_to_blocks(self, html_content, zf, html_path):
        """Convert HTML content to ordered blocks of text and images."""
        # Remove script and style tags
        content = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE)

        # Determine the directory of the HTML file for resolving relative image paths
        html_dir = os.path.dirname(html_path)

        blocks = []
        # We'll parse the HTML sequentially, finding images and text in order
        # Use a regex-based approach to split content at image tags

        # Find all image tags with their positions
        img_pattern = re.compile(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*/?>', re.IGNORECASE)

        last_end = 0
        for match in img_pattern.finditer(content):
            # Text before this image
            text_segment = content[last_end:match.start()]
            text = self._strip_tags(text_segment)
            if text.strip():
                blocks.append(("text", text.strip()))

            # Image
            src = match.group(1)
            img_data = self._resolve_image(src, html_dir, zf)
            if img_data:
                blocks.append(("image", img_data))

            last_end = match.end()

        # Remaining text after last image
        if last_end < len(content):
            text_segment = content[last_end:]
            text = self._strip_tags(text_segment)
            if text.strip():
                blocks.append(("text", text.strip()))

        # If no images found, just return the full text as one block
        if not blocks:
            text = self._strip_tags(content)
            if text.strip():
                blocks.append(("text", text.strip()))

        return blocks

    def _strip_tags(self, html_segment):
        """Strip HTML tags from a segment and return clean text."""
        text = re.sub(r"<br\s*/?>", "\n", html_segment, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</h[1-6]>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text

    def _resolve_image(self, src, html_dir, zf):
        """Resolve an image src to actual image bytes from the EPUB zip."""
        # Remove any URL fragment or query
        src = src.split("#")[0].split("?")[0]

        # Handle data URIs
        if src.startswith("data:"):
            try:
                # data:image/png;base64,XXXX
                header, data = src.split(",", 1)
                import base64
                return base64.b64decode(data)
            except Exception:
                return None

        # Resolve relative path
        if html_dir:
            full_path = os.path.normpath(os.path.join(html_dir, src))
        else:
            full_path = os.path.normpath(src)

        # Try to find in zip
        if full_path in zf.namelist():
            return zf.read(full_path)

        # Try without leading slash
        alt_path = full_path.lstrip("/")
        if alt_path in zf.namelist():
            return zf.read(alt_path)

        # Try case-insensitive search
        for name in zf.namelist():
            if name.lower() == full_path.lower():
                return zf.read(name)

        return None

    def _extract_title(self, html_content):
        """Try to extract a chapter title from HTML."""
        for tag in ["h1", "h2", "title"]:
            match = re.search(r"<{}[^>]*>(.*?)</{}>".format(tag, tag), html_content, re.DOTALL | re.IGNORECASE)
            if match:
                title = re.sub(r"<[^>]+>", "", match.group(1))
                title = html.unescape(title).strip()
                if title:
                    return title[:80]
        return None

    def _load_image(self, img_bytes):
        """Load image bytes into a PhotoImage, with caching."""
        if not HAS_PILLOW:
            return None

        # Use a hash of the bytes as cache key
        import hashlib
        key = hashlib.md5(img_bytes).hexdigest()
        if key in self._image_cache:
            return self._image_cache[key]

        try:
            img = Image.open(BytesIO(img_bytes))
            # Limit image width to 600px for display
            max_width = 600
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self._image_cache[key] = photo
            return photo
        except Exception:
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

        # Scrollable content area using Canvas
        content_frame = ttk.Frame(self.parent)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(content_frame, bg="#fffff8", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Inner frame for content
        self.content_inner = tk.Frame(self.canvas, bg="#fffff8")
        self._canvas_window = self.canvas.create_window((0, 0), window=self.content_inner, anchor="nw")

        # Update canvas scroll region when inner frame changes
        self.content_inner.bind("<Configure>", self._on_content_configure)

        # Bind mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        # Bind keyboard shortcuts
        self.parent.bind("<Next>", lambda e: self._next_chapter())
        self.parent.bind("<Prior>", lambda e: self._prev_chapter())
        self.parent.bind("<Right>", lambda e: self._next_chapter())
        self.parent.bind("<Left>", lambda e: self._prev_chapter())

        # Display current chapter
        self._display_chapter(self.current_chapter)

    def _on_content_configure(self, event):
        """Update the canvas scroll region."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling (Windows/macOS)."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        """Handle mouse wheel scrolling (Linux)."""
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _display_chapter(self, index):
        """Display a specific chapter with text and images."""
        if index < 0 or index >= self.total_chapters:
            return

        self.current_chapter = index
        title, blocks = self.chapters[index]

        # Clear existing content
        for widget in self.content_inner.winfo_children():
            widget.destroy()

        # Render blocks in order
        for block in blocks:
            if block[0] == "text":
                text = block[1]
                # Use a Label with wraplength for text
                text_label = tk.Label(
                    self.content_inner,
                    text=text,
                    justify=tk.LEFT,
                    wraplength=700,
                    font=("Segoe UI", 11),
                    bg="#fffff8",
                    fg="#222222",
                    padx=20,
                    pady=5,
                )
                text_label.pack(fill=tk.X, padx=10, pady=3)

            elif block[0] == "image":
                img_bytes = block[1]
                photo = self._load_image(img_bytes)
                if photo:
                    img_label = tk.Label(self.content_inner, image=photo, bg="#fffff8")
                    # Keep a reference to prevent GC
                    img_label._image_ref = photo
                    img_label.pack(pady=10)
                else:
                    # Show a placeholder if image can't be loaded
                    placeholder = tk.Label(
                        self.content_inner,
                        text="[Image]",
                        font=("Segoe UI", 10, "italic"),
                        bg="#fffff8",
                        fg="#888888",
                    )
                    placeholder.pack(pady=5)

        # Update UI
        self.chapter_label.config(text="Chapter {}/{}: {}".format(index + 1, self.total_chapters, title))
        self.chapter_var.set("{}/{}: {}".format(index + 1, self.total_chapters, title))
        self.progress_bar["value"] = index + 1

        pct = (index + 1) / self.total_chapters * 100
        self.progress_label.config(text="{:.0f}%".format(pct))

        # Reset scroll to top
        self.canvas.yview_moveto(0)

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
        match = re.match(r"(\d+)/", selection)
        if match:
            index = int(match.group(1)) - 1
            self._display_chapter(index)
