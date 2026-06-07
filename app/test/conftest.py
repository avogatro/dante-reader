import os
import pytest
from ebooklib import epub

@pytest.fixture
def dummy_epub_path(tmp_path):
    """
    Creates a tiny, valid EPUB file in a temporary directory using ebooklib
    and returns its file path. This ensures tests run fast and don't require
    committing bulky .epub binaries to the repository.
    """
    book = epub.EpubBook()

    # Metadata
    book.set_identifier("id123456")
    book.set_title("Pytest Dummy Book")
    book.set_language("en")
    book.add_author("Test Author")

    # Chapters
    c1 = epub.EpubHtml(title="Chapter 1", file_name="chap_01.xhtml", lang="en")
    c1.content = "<h1>Chapter 1</h1><p>This is the first chapter text.</p>"
    
    c2 = epub.EpubHtml(title="Chapter 2", file_name="chap_02.xhtml", lang="en")
    c2.content = "<h1>Chapter 2</h1><p>This is the second chapter text.</p>"

    book.add_item(c1)
    book.add_item(c2)

    # Define TOC
    book.toc = (c1, c2)

    # Add default NCX and Nav
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define spine
    book.spine = ["nav", c1, c2]

    # Write to temp path
    epub_file = tmp_path / "dummy_book.epub"
    epub.write_epub(str(epub_file), book, {})

    return str(epub_file)
