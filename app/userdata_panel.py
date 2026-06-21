import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, QTabWidget, QToolButton, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QIcon, QPainter, QFontMetrics

class WrappingListWidget(QListWidget):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.viewport().width()
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if widget:
                new_height = widget.heightForWidth(width)
                if new_height > 0:
                    item.setSizeHint(QSize(width, new_height))
                else:
                    item.setSizeHint(QSize(width, widget.sizeHint().height()))

class UserDataPanel(QWidget):
    # Emit chapter index, scroll percent
    navigate_requested = pyqtSignal(int, float)
    delete_bookmark_requested = pyqtSignal(str)
    delete_note_requested = pyqtSignal(str)
    edit_note_requested = pyqtSignal(str, str)
    edit_bookmark_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget { background-color: #0d1117; color: #c9d1d9; }
        """)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "bookmark.svg")
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(icon_path).pixmap(20, 20))

        title = QLabel(self.tr(" Bookmarks & Notes"))
        title.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #30363d; border-radius: 4px; background: #0d1117; }
            QTabBar::tab { background: #161b22; color: #8b949e; padding: 8px 16px; border: 1px solid #30363d; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #0d1117; color: #e6e1d8; border-bottom: 1px solid #0d1117; font-weight: bold; }
        """)
        
        self._bookmarks_list = WrappingListWidget()
        self._bookmarks_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._bookmarks_list.setStyleSheet(self._list_style())
        self._bookmarks_list.itemDoubleClicked.connect(self._on_bookmark_double_clicked)
        
        self._notes_list = WrappingListWidget()
        self._notes_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._notes_list.setStyleSheet(self._list_style())
        self._notes_list.itemDoubleClicked.connect(self._on_note_double_clicked)

        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
        self._tabs.addTab(self._bookmarks_list, QIcon(os.path.join(icon_dir, "bookmark.svg")), self.tr("Bookmarks"))
        self._tabs.addTab(self._notes_list, QIcon(os.path.join(icon_dir, "note.svg")), self.tr("Notes"))
        
        layout.addWidget(self._tabs)

    def _list_style(self) -> str:
        return """
            QListWidget {
                background-color: transparent;
                
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #30363d;
                padding: 2px;
                min-height: 40px;
            }
            QListWidget::item:hover {
                background-color: #21262d;
            }
            QListWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """

    def populate_data(self, bookmarks: list, notes: list):
        self._bookmarks_list.clear()
        self._notes_list.clear()
        
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")

        # Populate bookmarks
        for b in bookmarks:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, b)
            
            # Custom widget for the item
            widget = QWidget()
            w_layout = QHBoxLayout(widget)
            w_layout.setContentsMargins(5, 5, 5, 5)
            
            content_layout = QVBoxLayout()
            content_layout.setSpacing(4)
            
            pct = int(b.get("scroll_percent", 0.0) * 100)
            ch_label = QLabel(self.tr("Chapter {index}").format(index=b.get("chapter", 0) + 1) + f" ({pct}%)")
            ch_label.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
            content_layout.addWidget(ch_label)
            
            label_text = b.get("label")
            if label_text:
                text_label = QLabel(label_text)
                text_label.setWordWrap(True)
                text_label.setStyleSheet("font-weight: bold; background: transparent;")
            else:
                text_label = QLabel(self.tr("Bookmark"))
                text_label.setStyleSheet("font-style: italic; color: #8b949e; background: transparent;")
            content_layout.addWidget(text_label)
            
            btn_layout = QVBoxLayout()
            btn_layout.setSpacing(12)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QToolButton()
            edit_btn.setIcon(QIcon(os.path.join(icon_dir, "pencil.svg")))
            edit_btn.setIconSize(QSize(20, 20))
            edit_btn.setStyleSheet("background: transparent; border: none;")
            edit_btn.clicked.connect(lambda checked, bid=b["id"], blabel=label_text or "": self.edit_bookmark_requested.emit(bid, blabel))
            
            del_btn = QToolButton()
            del_btn.setIcon(QIcon(os.path.join(icon_dir, "delete.svg")))
            del_btn.setIconSize(QSize(20, 20))
            del_btn.setStyleSheet("background: transparent; border: none;")
            del_btn.clicked.connect(lambda checked, bid=b["id"]: self.delete_bookmark_requested.emit(bid))
            
            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(del_btn)
            btn_layout.addStretch()
            
            w_layout.addLayout(content_layout, 1)
            w_layout.addLayout(btn_layout)
            
            policy = widget.sizePolicy()
            policy.setHeightForWidth(True)
            widget.setSizePolicy(policy)
            
            item.setSizeHint(widget.sizeHint())
            self._bookmarks_list.addItem(item)
            self._bookmarks_list.setItemWidget(item, widget)

        # Populate notes
        for n in notes:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, n)
            
            widget = QWidget()
            w_layout = QHBoxLayout(widget)
            w_layout.setContentsMargins(5, 5, 5, 5)
            
            content_layout = QVBoxLayout()
            content_layout.setSpacing(4)
            
            pct = int(n.get("scroll_percent", 0.0) * 100)
            ch_label = QLabel(self.tr("Chapter {index}").format(index=n.get("chapter", 0) + 1) + f" ({pct}%)")
            ch_label.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
            
            q_text = n.get("selected_text", "")
            if q_text:
                quote_label = QLabel(f'"{q_text}"')
                quote_label.setWordWrap(True)
            else:
                quote_label = QLabel()
            quote_label.setStyleSheet("color: #c9a96e; font-style: italic; background: transparent;")
            
            n_text = n.get("note", "")
            note_label = QLabel(n_text)
            note_label.setWordWrap(True)
            note_label.setStyleSheet("font-weight: bold; background: transparent;")
            
            content_layout.addWidget(ch_label)
            if n.get("selected_text"):
                content_layout.addWidget(quote_label)
            content_layout.addWidget(note_label)
            
            btn_layout = QVBoxLayout()
            btn_layout.setSpacing(12)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QToolButton()
            edit_btn.setIcon(QIcon(os.path.join(icon_dir, "pencil.svg")))
            edit_btn.setIconSize(QSize(20, 20))
            edit_btn.setStyleSheet("background: transparent; border: none;")
            edit_btn.clicked.connect(lambda checked, nid=n["id"], ntext=n.get("note", ""): self.edit_note_requested.emit(nid, ntext))
            
            del_btn = QToolButton()
            del_btn.setIcon(QIcon(os.path.join(icon_dir, "delete.svg")))
            del_btn.setIconSize(QSize(20, 20))
            del_btn.setStyleSheet("background: transparent; border: none;")
            del_btn.clicked.connect(lambda checked, nid=n["id"]: self.delete_note_requested.emit(nid))
            
            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(del_btn)
            btn_layout.addStretch()
            
            w_layout.addLayout(content_layout, 1)
            w_layout.addLayout(btn_layout)
            
            policy = widget.sizePolicy()
            policy.setHeightForWidth(True)
            widget.setSizePolicy(policy)
            
            item.setSizeHint(widget.sizeHint())
            self._notes_list.addItem(item)
            self._notes_list.setItemWidget(item, widget)

    def _on_bookmark_double_clicked(self, item: QListWidgetItem):
        b = item.data(Qt.ItemDataRole.UserRole)
        if b:
            self.navigate_requested.emit(b.get("chapter", 0), b.get("scroll_percent", 0.0))

    def _on_note_double_clicked(self, item: QListWidgetItem):
        n = item.data(Qt.ItemDataRole.UserRole)
        if n:
            self.navigate_requested.emit(n.get("chapter", 0), n.get("scroll_percent", 0.0))
