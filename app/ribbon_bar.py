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
    bookmark_requested = pyqtSignal()
    
    scale_requested = pyqtSignal(float)
    lang_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(45)
        self.setStyleSheet("background: #0d1117;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(4)
        
        # App Logo / System Menu
        self.app_logo = QToolButton()
        from PyQt6.QtGui import QPixmap, QIcon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "logo_mountain.svg")
        self.app_logo.setIcon(QIcon(icon_path))
        self.app_logo.setIconSize(QSize(24, 24))
        self.app_logo.setStyleSheet("QToolButton { border: none; background: transparent; padding: 0px 6px; } QToolButton::menu-indicator { image: none; }")
        self.app_logo.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.app_menu = QMenu(self)
        self.scale_menu = self.app_menu.addMenu(self.tr("UI Scale (Requires Restart)"))
        
        for scale in [1.0, 1.25, 1.5, 1.75, 2.0]:
            action = self.scale_menu.addAction(f"{int(scale*100)}%")
            action.setData(scale)
            
        self.scale_menu.triggered.connect(lambda action: self.scale_requested.emit(float(action.data())))
            
        self.lang_menu = self.app_menu.addMenu(self.tr("App Language (Requires Restart)"))
        
        lang_names = {
            "en": (self.tr("English"), "English"),
            "zh_CN": (self.tr("Chinese"), "中文"),
            "es": (self.tr("Spanish"), "Español"),
            "fr": (self.tr("French"), "Français"),
            "de": (self.tr("German"), "Deutsch"),
            "ja": (self.tr("Japanese"), "日本語")
        }
        for code, (translated, native) in lang_names.items():
            action = self.lang_menu.addAction(f"{translated} | {native}")
            action.setData(code)
        self.lang_menu.triggered.connect(lambda action: self.lang_requested.emit(str(action.data())))

        self.app_logo.setMenu(self.app_menu)
        layout.addWidget(self.app_logo)
        
        # Left Side (Open, Prev, Next, Combo, Search)
        self.btn_open = self._make_btn("open_file", self.tr("Open Book"))
        self.btn_open.clicked.connect(self.open_requested.emit)
        
        self.btn_prev = self._make_btn("prev", self.tr("Previous Chapter"))
        self.btn_prev.clicked.connect(self.prev_chapter_requested.emit)
        
        self.btn_next = self._make_btn("next", self.tr("Next Chapter"))
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
        self.search_input.setPlaceholderText(self.tr("Search book..."))
        self.search_input.setMinimumWidth(450)
        self.search_input.setMaximumWidth(600)
        self.search_input.setStyleSheet("""
            QLineEdit { background: #161b22; color: #e6e1d8; border: 1px solid #30363d; border-radius: 12px; padding: 4px 12px; font-size: 13px;}
        """)
        self.search_input.returnPressed.connect(lambda: self.search_requested.emit(self.search_input.text()))
        self.search_input.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.search_input.customContextMenuRequested.connect(lambda pos: self._show_search_context_menu(pos))
        
        self.chapter_info = QLabel("")
        self.chapter_info.setStyleSheet("color: #8b949e; font-size: 13px; padding: 0px 6px; background: transparent;")
        
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
        self.drag_area.setStyleSheet("color: #8b949e; font-weight: bold; font-size: 13px; padding: 0px; background: transparent;")
        self.drag_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.drag_area)
        
        # Right Side (Toggles)
        self.btn_lib = self._make_btn("library", self.tr("Toggle Library"))
        self.btn_lib.clicked.connect(self.toggle_library.emit)
        
        self.btn_side = self._make_btn("sidebar", self.tr("Toggle Sidebar"))
        self.btn_side.clicked.connect(self.toggle_sidebar.emit)
        
        self.btn_bookmark = self._make_btn("bookmark", self.tr("Bookmark Page"))
        self.btn_bookmark.clicked.connect(self.bookmark_requested.emit)
        
        layout.addWidget(self.btn_bookmark)
        layout.addWidget(self.btn_lib)
        layout.addWidget(self.btn_side)
        layout.addSpacing(10)
        
        # Window Controls
        self.btn_min = self._make_btn("minimize", self.tr("Minimize"))
        self.btn_min.clicked.connect(self.minimize_requested.emit)
        
        self.btn_max = self._make_btn("maximize", self.tr("Maximize"))
        self.btn_max.clicked.connect(self.maximize_requested.emit)
        
        self.btn_close = self._make_btn("close", self.tr("Close"))
        self.btn_close.clicked.connect(self.close_requested.emit)
        
        # Apply hover effect to close button
        self.btn_close.setStyleSheet("""
            QPushButton { border: none; border-radius: 0; background: transparent; }
            QPushButton:hover { background: #e81123; border-radius: 0;}
        """)
        
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)
        
    def _show_search_context_menu(self, pos) -> None:
        menu = self.search_input.createStandardContextMenu()
        
        import os
        from PyQt6.QtGui import QIcon
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
        
        for action in menu.actions():
            raw_text = action.text().replace("&", "")
            text = raw_text.split('\t')[0]
            
            if text == "Copy" or text == self.tr("Copy"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Copy") + shortcut)
                action.setIcon(QIcon(os.path.join(icon_dir, "copy.svg")))
            elif text == "Select All" or text == self.tr("Select All"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Select All") + shortcut)
                action.setIcon(QIcon(os.path.join(icon_dir, "select_all.svg")))
            elif text == "Paste" or text == self.tr("Paste"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Paste") + shortcut)
                action.setIcon(QIcon(os.path.join(icon_dir, "copy.svg")))
            elif text == "Undo" or text == self.tr("Undo"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Undo") + shortcut)
            elif text == "Redo" or text == self.tr("Redo"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Redo") + shortcut)
            elif text == "Cut" or text == self.tr("Cut"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Cut") + shortcut)
            elif text == "Delete" or text == self.tr("Delete"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Delete") + shortcut)
                
        menu.exec(self.search_input.mapToGlobal(pos))
        del menu

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
            QPushButton { padding: 1px; border: none; border-radius: 4px; background: transparent; }
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
            QTabWidget::pane { border: none; border-top: 1px solid #30363d; border-bottom: 1px solid #30363d; background: #0d1117; }
            QTabBar::tab { background: transparent; color: #8b949e; padding: 6px 16px; font-size: 13px; margin-top: 2px; border-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { color: #c9a96e; background: #161b22; font-weight: bold; }
            QTabBar::tab:hover:!selected { background: #161b22; }
            QWidget { background: #0d1117; }
        """)
        
        self.view_tab = QWidget()
        self.read_tab = QWidget()
        self.ai_tab = QWidget()
        
        self.addTab(self.view_tab, self.tr("View"))
        self.addTab(self.read_tab, self.tr("Reading"))
        self.addTab(self.ai_tab, self.tr("AI / Research"))
        
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
        g.setStyleSheet("QFrame { border-right: 1px solid #30363d; border-radius: 0px; }")
        l.addLayout(content)
        l.addStretch()
        
        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #e6e1d8; font-size: 11px; margin-top: 2px; background: transparent;")
        l.addWidget(lbl)
        
        # Add a subtle right border to the group
        
        return g

    def _setup_view_tab(self):
        layout = QHBoxLayout(self.view_tab)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        
        # Font Group
        font_g = self._create_group(self.tr("Typography"))
        self.font_btn = RibbonButton(self.tr("Font Family"), "font", self.tr("Change Font Family"))
        self.font_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.size_btn = RibbonButton(self.tr("Font Size"), "size", self.tr("Change Font Size"))
        self.size_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        font_g.content_layout.addWidget(self.font_btn)
        font_g.content_layout.addWidget(self.size_btn)
        layout.addWidget(font_g)
        
        # Layout Group
        layout_g = self._create_group(self.tr("Layout"))
        self.spacing_btn = RibbonButton(self.tr("Line Spacing"), "spacing", self.tr("Change Line Spacing"))
        self.spacing_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.width_btn = RibbonButton(self.tr("Content Width"), "width", self.tr("Change Content Width"))
        self.width_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        layout_g.content_layout.addWidget(self.spacing_btn)
        layout_g.content_layout.addWidget(self.width_btn)
        layout.addWidget(layout_g)
        
        # Mode Group
        mode_g = self._create_group(self.tr("Modes"))
        self.theme_btn = RibbonButton(self.tr("Dark Mode"), "dark_mode", self.tr("Toggle Dark/Light Theme"))
        self.theme_btn.setCheckable(True)
        self.pdf_mode_btn = RibbonButton(self.tr("PDF Extract"), "pdf_mode", self.tr("Toggle PDF Text Extraction Mode"))
        self.pdf_mode_btn.setCheckable(True)
        self.epub_md_btn = RibbonButton(self.tr("ePub Extract"), "epub_mode", self.tr("Toggle EPUB Markdown Mode"))
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
        
        play_g = self._create_group(self.tr("Narration"))
        self.play_btn = RibbonButton(self.tr("Play Audio"), "play", self.tr("Start Narration (F5)"))
        self.stop_btn = RibbonButton(self.tr("Stop Audio"), "stop", self.tr("Stop Narration (F7)"))
        
        play_g.content_layout.addWidget(self.play_btn)
        play_g.content_layout.addWidget(self.stop_btn)
        layout.addWidget(play_g)
        
        settings_g = self._create_group(self.tr("Settings"))
        self.voice_btn = RibbonButton(self.tr("Select Voice"), "voice", self.tr("Select AI Voice"))
        self.voice_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.skip_fn_btn = RibbonButton(self.tr("Skip Footnotes"), "skip_footnotes", self.tr("Toggle Reading Footnotes Aloud"))
        self.skip_fn_btn.setCheckable(True)
        
        settings_g.content_layout.addWidget(self.voice_btn)
        settings_g.content_layout.addWidget(self.skip_fn_btn)
        layout.addWidget(settings_g)
        
        layout.addStretch()

    def _setup_ai_tab(self):
        layout = QHBoxLayout(self.ai_tab)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        
        ai_g = self._create_group(self.tr("AI / Translate"))
        self.translate_btn = RibbonButton(self.tr("Target Language"), "translate", self.tr("Select Target Translation Language"))
        self.translate_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.ai_model_btn = RibbonButton(self.tr("AI Settings"), "ai_model", self.tr("Open AI Settings Panel"))
        
        ai_g.content_layout.addWidget(self.translate_btn)
        ai_g.content_layout.addWidget(self.ai_model_btn)
        layout.addWidget(ai_g)
        
        layout.addStretch()
