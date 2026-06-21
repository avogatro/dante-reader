import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, QTabWidget, QToolButton, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QIcon, QPainter, QFontMetrics, QShortcut, QKeySequence

class WrappingListWidget(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_width = -1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.viewport().width()
        
        # Prevent infinite layout loops
        if width == self._last_width:
            return
        self._last_width = width
        
        # Defer the heavy calculation so the UI updates instantly
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self._recalc_heights(width))
        
    def _recalc_heights(self, width: int):
        # Double check width hasn't changed since the timer started
        if self.viewport().width() != width:
            return
            
        self._recalc_idx = 0
        self._recalc_width = width
        self._process_next_chunk()
        
    def _process_next_chunk(self):
        if self.viewport().width() != self._recalc_width:
            return
            
        chunk_size = 15
        end = min(self._recalc_idx + chunk_size, self.count())
        
        for i in range(self._recalc_idx, end):
            item = self.item(i)
            if not item:
                continue
                
            widget = self.itemWidget(item)
            if widget:
                new_height = widget.heightForWidth(self._recalc_width)
                if new_height > 0:
                    new_size = QSize(self._recalc_width, new_height)
                else:
                    new_size = QSize(self._recalc_width, widget.sizeHint().height())
                
                if item.sizeHint() != new_size:
                    item.setSizeHint(new_size)
                    
        self._recalc_idx = end
        if self._recalc_idx < self.count():
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1, self._process_next_chunk)

class UserDataPanel(QWidget):
    # Emit chapter index, scroll percent, selected_text (optional)
    navigate_requested = pyqtSignal(int, float, str)
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
            QTabBar::tab { background: transparent; color: #8b949e; padding: 8px 16px; border: 1px solid transparent; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #161b22; color: #c9a96e; border: 1px solid #30363d; border-bottom: 2px solid #c9a96e; font-weight: bold; }
            QTabBar::tab:hover:!selected { background: #161b22; border: 1px solid #30363d; border-bottom: none; }
        """)
        
        self._bookmarks_list = WrappingListWidget()
        self._bookmarks_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._bookmarks_list.setStyleSheet(self._list_style())
        self._bookmarks_list.itemClicked.connect(self._on_bookmark_clicked)
        self._bookmarks_list.itemSelectionChanged.connect(self._on_bookmarks_selection_changed)
        
        self._notes_list = WrappingListWidget()
        self._notes_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._notes_list.setStyleSheet(self._list_style())
        self._notes_list.itemClicked.connect(self._on_note_clicked)
        self._notes_list.itemSelectionChanged.connect(self._on_notes_selection_changed)

        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
        self._tabs.addTab(self._bookmarks_list, QIcon(os.path.join(icon_dir, "bookmark.svg")), self.tr("Bookmarks"))
        self._tabs.addTab(self._notes_list, QIcon(os.path.join(icon_dir, "note.svg")), self.tr("Notes"))
        
        layout.addWidget(self._tabs)

        del_shortcut = QShortcut(QKeySequence("Delete"), self)
        del_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        del_shortcut.activated.connect(self._on_delete_shortcut)

        edit_shortcut = QShortcut(QKeySequence("F2"), self)
        edit_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        edit_shortcut.activated.connect(self._on_edit_shortcut)

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
            
            btn_container = QWidget()
            btn_container.setObjectName("btn_container")
            btn_layout = QVBoxLayout(btn_container)
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
            
            btn_container.setVisible(False)
            
            w_layout.addLayout(content_layout, 1)
            w_layout.addWidget(btn_container)
            
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
            
            btn_container = QWidget()
            btn_container.setObjectName("btn_container")
            btn_layout = QVBoxLayout(btn_container)
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
            
            btn_container.setVisible(False)
            
            w_layout.addLayout(content_layout, 1)
            w_layout.addWidget(btn_container)
            
            policy = widget.sizePolicy()
            policy.setHeightForWidth(True)
            widget.setSizePolicy(policy)
            
            item.setSizeHint(widget.sizeHint())
            self._notes_list.addItem(item)
            self._notes_list.setItemWidget(item, widget)

    def _on_bookmark_clicked(self, item: QListWidgetItem):
        b = item.data(Qt.ItemDataRole.UserRole)
        if b:
            self.navigate_requested.emit(b.get("chapter", 0), b.get("scroll_percent", 0.0), "")

    def _on_note_clicked(self, item: QListWidgetItem):
        n = item.data(Qt.ItemDataRole.UserRole)
        if n:
            self.navigate_requested.emit(n.get("chapter", 0), n.get("scroll_percent", 0.0), n.get("selected_text", ""))

    def _on_bookmarks_selection_changed(self):
        self._update_button_visibility(self._bookmarks_list)

    def _on_notes_selection_changed(self):
        self._update_button_visibility(self._notes_list)

    def _update_button_visibility(self, lst: QListWidget):
        for i in range(lst.count()):
            item = lst.item(i)
            widget = lst.itemWidget(item)
            if widget:
                btn_container = widget.findChild(QWidget, "btn_container")
                if btn_container:
                    btn_container.setVisible(item.isSelected())

    def _get_active_list(self) -> QListWidget:
        return self._bookmarks_list if self._tabs.currentIndex() == 0 else self._notes_list

    def _on_delete_shortcut(self):
        lst = self._get_active_list()
        item = lst.currentItem()
        if item and item.isSelected():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                if self._tabs.currentIndex() == 0:
                    self.delete_bookmark_requested.emit(data["id"])
                else:
                    self.delete_note_requested.emit(data["id"])

    def _on_edit_shortcut(self):
        lst = self._get_active_list()
        item = lst.currentItem()
        if item and item.isSelected():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                if self._tabs.currentIndex() == 0:
                    label_text = data.get("label") or ""
                    self.edit_bookmark_requested.emit(data["id"], label_text)
                else:
                    self.edit_note_requested.emit(data["id"], data.get("note", ""))
