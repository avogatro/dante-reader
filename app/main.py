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
from app.style_manager import load_qss
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
    app.setStyleSheet(load_qss("base.qss"))

    # Set app icon
    from app.ui_utils import get_icon
    app.setWindowIcon(get_icon("logo_mountain"))

    # Set default application font
    ui_font_family = "Segoe UI"
    if app_lang == "zh_CN":
        ui_font_family = "Microsoft YaHei"
    elif app_lang == "ja":
        ui_font_family = "Meiryo"
        
    font = QFont(ui_font_family, 13)
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
        print(f"\n[STARTUP] UI fully rendered in: {elapsed:.3f} seconds\n")
        
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
