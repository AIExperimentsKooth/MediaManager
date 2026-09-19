# Media Manager

A Python-based GUI application for reading EPUB and PDF books with progress tracking.

## Features

- Library Management: Add, remove, and search EPUB and PDF books
- EPUB Reader: Read EPUB books chapter by chapter with navigation
- PDF Reader: Read PDF books page by page with navigation
- Progress Tracking: Automatically saves your reading position
- Resume Reading: Pick up where you left off
- Font Controls: Adjust text size in the PDF reader
- Keyboard Navigation: Use arrow keys, Page Up/Down to navigate

## Requirements

- Python 3.7+
- PyPDF2 (for PDF text extraction)

## Installation

```
pip install -r requirements.txt
```

## Usage

```
python main.py
```

### Adding Books
1. Click "Add Book" in the Library tab
2. Select one or more EPUB or PDF files
3. Books appear in the library list with metadata

### Reading
1. Select a book in the library
2. Double-click or click "Open Book"
3. Navigate using Prev/Next buttons, keyboard arrows, or the chapter/page dropdown

### Progress Tracking
- Progress is saved automatically as you navigate
- Your position is restored when you reopen a book
- Progress data is stored in progress.json
- Library data is stored in library.json

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Left Arrow | Previous chapter/page |
| Right Arrow | Next chapter/page |
| Page Up | Previous chapter/page |
| Page Down | Next chapter/page |

## Project Structure

```
MediaManager/
  main.py           - Entry point
  app.py            - Main GUI application
  book_manager.py   - Library and progress management
  epub_reader.py    - EPUB reading engine
  pdf_reader.py     - PDF reading engine
  requirements.txt  - Python dependencies
  progress.json     - (generated) Reading progress data
  library.json      - (generated) Book library data
```

## Notes

- EPUB reading extracts text content (images are not displayed)
- PDF reading extracts text (scanned/image-only PDFs may not have extractable text)
- Removing a book from the library does NOT delete the file from disk
