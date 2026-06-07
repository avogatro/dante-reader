import os
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from app.library_panel import LibraryPanel
from app.epub_loader import EpubBook

def test_library_panel_add_and_select_book(qtbot, dummy_epub_path):
    """
    Test that the LibraryPanel can have a book added to it,
    and clicking that book emits the book_selected signal.
    """
    panel = LibraryPanel()
    qtbot.addWidget(panel)

    # Mock the directory scanning to look at our temporary directory
    import app.library_panel
    import os
    original_get_epubs_dir = app.library_panel.get_epubs_dir
    app.library_panel.get_epubs_dir = lambda: os.path.dirname(dummy_epub_path)
    
    panel.scan_library()
    
    # Restore the original
    app.library_panel.get_epubs_dir = original_get_epubs_dir
    
    # Verify it was added to the list widget
    assert panel._list.count() == 1
    item = panel._list.item(0)
    
    # We expect the text to include the title
    assert "dummy_book" in item.text() or "Pytest" in item.text()
    
    # Test the signal emission
    with qtbot.waitSignal(panel.book_selected, timeout=1000) as blocker:
        # Instead of simulating a double click which can fail in headless environments,
        # directly invoke the slot that handles the click.
        panel._on_book_clicked(item)
        
    # The emitted signal should contain the file path
    assert blocker.args[0] == dummy_epub_path
