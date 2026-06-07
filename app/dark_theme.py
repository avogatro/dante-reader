"""
Dark theme QSS stylesheet for the EPUB Reader.
Deep navy-dark palette with parchment-gold accents, inspired by classical Dante aesthetics.
"""

# ── Color Palette ──
BG_DARKEST = "#0d1117"       # Window background
BG_DARK = "#161b22"          # Panel backgrounds
BG_PANEL = "#1c2333"         # Card / sidebar backgrounds
BG_INPUT = "#22293a"         # Input fields, code areas
BORDER = "#30363d"           # Subtle borders
TEXT_PRIMARY = "#e6e1d8"     # Warm off-white reading text
TEXT_SECONDARY = "#8b949e"   # Muted labels
TEXT_DIM = "#6e7681"         # Placeholder, disabled text
ACCENT_GOLD = "#c9a96e"      # Parchment gold — primary accent
ACCENT_HOVER = "#dfc08a"     # Gold hover state
ACCENT_BLUE = "#58a6ff"      # Links, interactive highlights
SCROLLBAR_BG = "#1c2333"
SCROLLBAR_HANDLE = "#30363d"
SCROLLBAR_HOVER = "#484f58"

DARK_QSS = f"""
/* ═══════════════════════════════════════════
   Global Styles
   ═══════════════════════════════════════════ */

QMainWindow {{
    background-color: {BG_DARKEST};
    color: {TEXT_PRIMARY};
}}

QWidget {{
    background-color: {BG_DARKEST};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 15px;
}}

/* ═══════════════════════════════════════════
   Menu Bar
   ═══════════════════════════════════════════ */

QMenuBar {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px 0px;
    font-size: 15px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 6px 14px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {BG_PANEL};
    color: {ACCENT_GOLD};
}}

QMenu {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 7px 28px 7px 14px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {BG_PANEL};
    color: {ACCENT_GOLD};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

/* ═══════════════════════════════════════════
   Splitter
   ═══════════════════════════════════════════ */

QSplitter::handle {{
    background-color: {BORDER};
    width: 2px;
}}

QSplitter::handle:hover {{
    background-color: {ACCENT_GOLD};
}}

/* ═══════════════════════════════════════════
   Scroll Bars
   ═══════════════════════════════════════════ */

QScrollBar:vertical {{
    background: {SCROLLBAR_BG};
    width: 10px;
    margin: 0;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {SCROLLBAR_HANDLE};
    min-height: 30px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {SCROLLBAR_HOVER};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {SCROLLBAR_BG};
    height: 10px;
    margin: 0;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {SCROLLBAR_HANDLE};
    min-width: 30px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {SCROLLBAR_HOVER};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ═══════════════════════════════════════════
   Push Buttons
   ═══════════════════════════════════════════ */

QPushButton {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 15px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {BG_INPUT};
    border-color: {ACCENT_GOLD};
    color: {ACCENT_GOLD};
}}

QPushButton:pressed {{
    background-color: {BORDER};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BG_PANEL};
}}

/* ═══════════════════════════════════════════
   Labels
   ═══════════════════════════════════════════ */

QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}

/* ═══════════════════════════════════════════
   List / Tree Views
   ═══════════════════════════════════════════ */

QListWidget, QTreeWidget {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: none;
    padding: 4px;
}}

QListWidget::item, QTreeWidget::item {{
    padding: 6px 10px;
    border-radius: 4px;
}}

QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {BG_PANEL};
    color: {ACCENT_GOLD};
}}

QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {BG_INPUT};
}}

/* ═══════════════════════════════════════════
   Combo Box
   ═══════════════════════════════════════════ */

QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 100px;
}}



QComboBox QAbstractItemView {{
    background-color: {BG_DARK};
    selection-background-color: {BG_PANEL};
    selection-color: {ACCENT_GOLD};
    outline: none;
}}

/* ═══════════════════════════════════════════
   Text Edits
   ═══════════════════════════════════════════ */

QTextEdit, QPlainTextEdit, QTextBrowser {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {ACCENT_GOLD};
    selection-color: {BG_DARKEST};
}}

QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 12px;
    selection-background-color: {ACCENT_GOLD};
    selection-color: {BG_DARKEST};
}}

QLineEdit:focus {{
    border-color: {ACCENT_GOLD};
}}

/* ═══════════════════════════════════════════
   Tab Widget
   ═══════════════════════════════════════════ */

QTabWidget::pane {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-top: none;
    border-radius: 0 0 6px 6px;
}}

QTabBar::tab {{
    background-color: {BG_DARKEST};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    font-size: 13px;
}}

QTabBar::tab:selected {{
    background-color: {BG_DARK};
    color: {ACCENT_GOLD};
    border-bottom: 2px solid {ACCENT_GOLD};
}}

QTabBar::tab:hover:!selected {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
}}

/* ═══════════════════════════════════════════
   Status Bar
   ═══════════════════════════════════════════ */

QStatusBar {{
    background-color: {BG_DARK};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: 13px;
}}

/* ═══════════════════════════════════════════
   Tool Tips
   ═══════════════════════════════════════════ */

QToolTip {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 13px;
}}

/* ═══════════════════════════════════════════
   Slider
   ═══════════════════════════════════════════ */

QSlider::groove:horizontal {{
    background: {BORDER};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {ACCENT_GOLD};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background: {ACCENT_HOVER};
}}

/* ═══════════════════════════════════════════
   Group Box
   ═══════════════════════════════════════════ */

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    color: {ACCENT_GOLD};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
"""

# CSS injected into QWebEngineView for dark reading mode
READER_DARK_CSS = f"""
html, body {{
    background-color: {BG_DARKEST} !important;
    color: {TEXT_PRIMARY} !important;
    min-height: 100vh !important;
}}

a {{
    color: {ACCENT_BLUE} !important;
}}

a:hover {{
    color: {ACCENT_HOVER} !important;
}}



/* Fix for EPUB covers using SVG with height 100% but no parent height */
svg[height="100%"] {{
    height: 95vh !important;
    width: auto !important;
    object-fit: contain !important;
}}

/* Footnote anchor styling */
a.fnanchor, a.pginternal {{
    color: {ACCENT_GOLD} !important;
    text-decoration: none !important;
    font-weight: bold;
    cursor: pointer;
}}

a.fnanchor:hover, a.pginternal:hover {{
    color: {ACCENT_HOVER} !important;
    text-decoration: underline !important;
}}

/* TTS highlight for currently-spoken sentence */
.tts-active {{
    background-color: rgba(201, 169, 110, 0.2) !important;
    border-radius: 3px;
    outline: 1px solid rgba(201, 169, 110, 0.4);
}}

/* Selection styling */
::selection {{
    background-color: {ACCENT_GOLD} !important;
    color: {BG_DARKEST} !important;
}}

/* Custom Dark Scrollbars */
::-webkit-scrollbar {{
    width: 14px;
    height: 14px;
}}
::-webkit-scrollbar-track {{
    background: {BG_DARKEST}; 
}}
::-webkit-scrollbar-thumb {{
    background: {BG_DARK}; 
    border-radius: 7px;
    border: 3px solid {BG_DARKEST};
}}
::-webkit-scrollbar-thumb:hover {{
    background: {ACCENT_BLUE}; 
}}
"""
