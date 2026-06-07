"""
Dante EPUB Reader — Entry Point
A premium dark-mode EPUB reader with TTS narration and Gemini AI integration.
"""

import sys
import os
import io

# ── Fix Windows console encoding (MUST be first) ──
# Without this, any print() containing Unicode (Japanese, arrows, etc.)
# crashes the Qt app because the Windows console uses 'charmap' codec.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

# Register custom URL scheme BEFORE QApplication is created
from app.url_scheme_handler import register_epub_scheme
register_epub_scheme()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app.dark_theme import DARK_QSS
from app.reader_window import ReaderWindow


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("DanteReader")
    app.setApplicationName("DanteEpubReader")

    # Apply global dark theme
    app.setStyleSheet(DARK_QSS)

    # Set default application font
    font = QFont("Segoe UI", 13)
    app.setFont(font)

    # Launch main window
    window = ReaderWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
