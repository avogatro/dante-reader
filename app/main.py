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


import time
import cProfile
import pstats
import io

_START_TIME = time.time()
_DEBUG_PROFILE = "--debug-profile" in sys.argv

if _DEBUG_PROFILE:
    _PROFILER = cProfile.Profile()
    _PROFILER.enable()
else:
    _PROFILER = None

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

    # Schedule a callback on the first idle loop (when UI is done drawing)
    from PyQt6.QtCore import QTimer
    def print_startup_time():
        if _PROFILER:
            _PROFILER.disable()
            
        elapsed = time.time() - _START_TIME
        print(f"\n🚀 UI fully rendered in: {elapsed:.3f} seconds\n")
        
        if _PROFILER:
            # Print profiler stats
            s = io.StringIO()
            ps = pstats.Stats(_PROFILER, stream=s).sort_stats('cumulative')
            ps.print_stats(25)
            print("=== STARTUP PROFILE (TOP 25 CUMULATIVE TIME) ===")
            print(s.getvalue())
        
    QTimer.singleShot(0, print_startup_time)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
