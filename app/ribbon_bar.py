import os
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QIcon, QAction, QPainter, QColor, QMouseEvent
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QTabWidget, QComboBox, QLineEdit, QSizePolicy, QToolButton, QFrame, QMenu
)

def get_icon(name: str) -> QIcon:
    path = os.path.join(os.path.dirname(__file__), "assets", "icons", f"{name}.svg")
    return QIcon(path)

class RibbonButton(QToolButton):
    def __init__(self, text, icon_name, tooltip=None, parent=None):
        super().__init__(parent)
        self.setText(text)
        if tooltip:
            self.setToolTip(tooltip)
        else:
            self.setToolTip(text)
        if icon_name:
            self.setIcon(get_icon(icon_name))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(28, 28))
        self.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                background: transparent;
                color: #e6e1d8;
                padding: 4px;
                font-size: 11px;
                min-width: 65px;
                min-height: 55px;
            }
            QToolButton:hover {
                background: #30363d;
                border: 1px solid #c9a96e;
            }
            QToolButton:pressed, QToolButton:checked {
                background: #40464d;
                border: 1px solid #c9a96e;
            }
            QToolButton::menu-indicator { image: none; }
        """)

# Custom Title Bar implementation with aero snap/dragging handled in reader_window via nativeEvent
class CustomTitleBar(QWidget):
    close_requested = pyqtSignal()
    maximize_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    
    open_requested = pyqtSignal()
    prev_chapter_requested = pyqtSignal()
    next_chapter_requested = pyqtSignal()
    chapter_selected = pyqtSignal(int)
    search_requested = pyqtSignal(str)
    
    toggle_library = pyqtSignal()
    toggle_sidebar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet("background: #0d1117;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(4)
        
        # Left Side (Open, Prev, Next, Combo, Search)
        self.btn_open = self._make_btn("open_file", "Open Book")
        self.btn_open.clicked.connect(self.open_requested.emit)
        
        self.btn_prev = self._make_btn("prev", "Previous Chapter")
        self.btn_prev.clicked.connect(self.prev_chapter_requested.emit)
        
        self.btn_next = self._make_btn("next", "Next Chapter")
        self.btn_next.clicked.connect(self.next_chapter_requested.emit)
        
        self.chapter_combo = QComboBox()
        self.chapter_combo.setMinimumWidth(450)
        self.chapter_combo.setMaximumWidth(450)
        self.chapter_combo.setStyleSheet("""
            QComboBox { background: #161b22; color: #e6e1d8; border: 1px solid #30363d; border-radius: 4px; padding: 4px 8px; font-size: 13px;}
            QComboBox::drop-down { border: none; }
        """)
        self.chapter_combo.currentIndexChanged.connect(self.chapter_selected.emit)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search book...")
        self.search_input.setMinimumWidth(450)
        self.search_input.setMaximumWidth(600)
        self.search_input.setStyleSheet("""
            QLineEdit { background: #161b22; color: #e6e1d8; border: 1px solid #30363d; border-radius: 12px; padding: 4px 12px; font-size: 13px;}
        """)
        self.search_input.returnPressed.connect(lambda: self.search_requested.emit(self.search_input.text()))
        
        self.chapter_info = QLabel("")
        self.chapter_info.setStyleSheet("color: #8b949e; font-size: 13px; padding: 0px 6px;")
        
        layout.addWidget(self.btn_open)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.chapter_combo)
        layout.addWidget(self.chapter_info)
        layout.addWidget(self.btn_next)
        layout.addSpacing(10)
        layout.addWidget(self.search_input)
        
        # Middle spacer (draggable area)
        self.drag_area = QLabel("")
        self.drag_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drag_area.setStyleSheet("color: #8b949e; font-weight: bold; font-size: 14px;")
        self.drag_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.drag_area)
        
        # Right Side (Toggles)
        self.btn_lib = self._make_btn("library", "Toggle Library")
        self.btn_lib.clicked.connect(self.toggle_library.emit)
        
        self.btn_side = self._make_btn("sidebar", "Toggle Sidebar")
        self.btn_side.clicked.connect(self.toggle_sidebar.emit)
        
        layout.addWidget(self.btn_lib)
        layout.addWidget(self.btn_side)
        layout.addSpacing(10)
        
        # Window Controls
        self.btn_min = self._make_btn("minimize", "Minimize")
        self.btn_min.clicked.connect(self.minimize_requested.emit)
        
        self.btn_max = self._make_btn("maximize", "Maximize")
        self.btn_max.clicked.connect(self.maximize_requested.emit)
        
        self.btn_close = self._make_btn("close", "Close")
        self.btn_close.clicked.connect(self.close_requested.emit)
        
        # Apply hover effect to close button
        self.btn_close.setStyleSheet("""
            QPushButton { border: none; border-radius: 0; background: transparent; }
            QPushButton:hover { background: #e81123; border-radius: 0;}
        """)
        
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(event)



    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()

    def _make_btn(self, icon_name, tooltip):
        b = QPushButton()
        b.setIcon(get_icon(icon_name))
        b.setToolTip(tooltip)
        b.setFixedSize(36, 36)
        b.setStyleSheet("""
            QPushButton { border: none; border-radius: 4px; background: transparent; }
            QPushButton:hover { background: #30363d; }
        """)
        return b

    def set_maximized_icon(self, is_max: bool):
        if is_max:
            self.btn_max.setIcon(get_icon("restore"))
        else:
            self.btn_max.setIcon(get_icon("maximize"))

class RibbonBar(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(130)
        self.setStyleSheet("""
            QTabWidget::pane { border: none; border-top: 1px solid #30363d; background: #0d1117; }
            QTabBar::tab { background: transparent; color: #8b949e; padding: 6px 16px; font-size: 13px; margin-top: 2px; border-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { color: #c9a96e; background: #161b22; font-weight: bold; }
            QTabBar::tab:hover:!selected { background: #161b22; }
            QWidget { background: #0d1117; }
        """)
        
        self.view_tab = QWidget()
        self.read_tab = QWidget()
        self.ai_tab = QWidget()
        
        self.addTab(self.view_tab, "View")
        self.addTab(self.read_tab, "Reading")
        self.addTab(self.ai_tab, "AI / Research")
        
        self._setup_view_tab()
        self._setup_read_tab()
        self._setup_ai_tab()
        
    def _create_group(self, title: str) -> QWidget:
        g = QFrame()
        l = QVBoxLayout(g)
        l.setContentsMargins(6, 4, 6, 0)
        
        content = QHBoxLayout()
        content.setSpacing(4)
        g.content_layout = content
        
        l.addLayout(content)
        l.addStretch()
        
        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #e6e1d8; font-size: 11px; margin-top: 2px;")
        l.addWidget(lbl)
        
        # Add a subtle right border to the group
        g.setStyleSheet("QFrame { border-right: 1px solid #30363d; border-radius: 0px; }")
        return g

    def _setup_view_tab(self):
        layout = QHBoxLayout(self.view_tab)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        
        # Font Group
        font_g = self._create_group("Typography")
        self.font_btn = RibbonButton("Font Family", "font", "Change Font Family")
        self.font_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.size_btn = RibbonButton("Font Size", "size", "Change Font Size")
        self.size_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        font_g.content_layout.addWidget(self.font_btn)
        font_g.content_layout.addWidget(self.size_btn)
        layout.addWidget(font_g)
        
        # Layout Group
        layout_g = self._create_group("Layout")
        self.spacing_btn = RibbonButton("Line Spacing", "spacing", "Change Line Spacing")
        self.spacing_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.width_btn = RibbonButton("Content Width", "width", "Change Content Width")
        self.width_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        layout_g.content_layout.addWidget(self.spacing_btn)
        layout_g.content_layout.addWidget(self.width_btn)
        layout.addWidget(layout_g)
        
        # Mode Group
        mode_g = self._create_group("Modes")
        self.theme_btn = RibbonButton("Dark Mode", "dark_mode", "Toggle Dark/Light Theme")
        self.theme_btn.setCheckable(True)
        self.pdf_mode_btn = RibbonButton("PDF Extract", "pdf_mode", "Toggle PDF Text Extraction Mode")
        self.pdf_mode_btn.setCheckable(True)
        self.epub_md_btn = RibbonButton("ePub Extract", "epub_mode", "Toggle EPUB Markdown Mode")
        self.epub_md_btn.setCheckable(True)
        
        mode_g.content_layout.addWidget(self.theme_btn)
        mode_g.content_layout.addWidget(self.pdf_mode_btn)
        mode_g.content_layout.addWidget(self.epub_md_btn)
        layout.addWidget(mode_g)
        
        layout.addStretch()

    def _setup_read_tab(self):
        layout = QHBoxLayout(self.read_tab)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        
        play_g = self._create_group("Narration")
        self.play_btn = RibbonButton("Play Audio", "play", "Start Narration (F5)")
        self.stop_btn = RibbonButton("Stop Audio", "stop", "Stop Narration (F7)")
        
        play_g.content_layout.addWidget(self.play_btn)
        play_g.content_layout.addWidget(self.stop_btn)
        layout.addWidget(play_g)
        
        settings_g = self._create_group("Settings")
        self.voice_btn = RibbonButton("Select Voice", "voice", "Select AI Voice")
        self.voice_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.skip_fn_btn = RibbonButton("Skip Footnotes", "skip_footnotes", "Toggle Reading Footnotes Aloud")
        self.skip_fn_btn.setCheckable(True)
        
        settings_g.content_layout.addWidget(self.voice_btn)
        settings_g.content_layout.addWidget(self.skip_fn_btn)
        layout.addWidget(settings_g)
        
        layout.addStretch()

    def _setup_ai_tab(self):
        layout = QHBoxLayout(self.ai_tab)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        
        ai_g = self._create_group("AI / Translate")
        self.translate_btn = RibbonButton("Target Language", "translate", "Select Target Translation Language")
        self.translate_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.ai_model_btn = RibbonButton("AI Settings", "ai_model", "Open AI Settings Panel")
        
        ai_g.content_layout.addWidget(self.translate_btn)
        ai_g.content_layout.addWidget(self.ai_model_btn)
        layout.addWidget(ai_g)
        
        layout.addStretch()
