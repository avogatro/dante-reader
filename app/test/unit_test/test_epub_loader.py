import os
from app.epub_loader import EpubBook

def test_epub_book_loads_metadata(dummy_epub_path):
    """Test that EpubBook extracts basic metadata correctly from our dummy EPUB."""
    book = EpubBook(dummy_epub_path)
    
    assert book.title == "Pytest Dummy Book"
    assert book.author == "Test Author"
    assert book.language == "en"

def test_epub_book_loads_chapters(dummy_epub_path):
    """Test that EpubBook builds the chapter spine and extracts HTML correctly."""
    book = EpubBook(dummy_epub_path)
    
    # It should have our 2 chapters (ebooklib might also include the nav as a chapter)
    assert len(book.chapters) >= 2
    
    # Find the chapters by file_name to be safe from ebooklib's internal ordering
    chap1 = next(c for c in book.chapters if "chap_01" in c.file_name)
    assert "<h1>Chapter 1</h1>" in chap1.get_html()
    
    chap2 = next(c for c in book.chapters if "chap_02" in c.file_name)
    assert "This is the second chapter text" in chap2.get_html()
