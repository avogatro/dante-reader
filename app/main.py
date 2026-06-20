"""
Dante EPUB Reader — Entry Point
A premium dark-mode EPUB reader with TTS narration and Gemini AI integration.
"""

import sys
import os
import io

# No IO wrappers

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
    from app.config import load_prefs
    prefs = load_prefs()
    ui_scale = prefs.get("ui_scale", 1.0)
    if ui_scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = str(ui_scale)

    app = QApplication(sys.argv)
    app.setOrganizationName("DanteReader")
    app.setApplicationName("DanteEpubReader")

    # Load application language translations
    from PyQt6.QtCore import QTranslator
    app_lang = prefs.get("app_lang", "en")
    app._translator = QTranslator() # Keep reference
    translations_path = os.path.join(os.path.dirname(__file__), "..", "translations", f"{app_lang}.qm")
    if os.path.exists(translations_path):
        if app._translator.load(translations_path):
            app.installTranslator(app._translator)

    # Apply global dark theme
    app.setStyleSheet(DARK_QSS)

    # Set app icon
    from PyQt6.QtGui import QIcon
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "logo_mountain.svg")
    app.setWindowIcon(QIcon(icon_path))

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
