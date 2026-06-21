import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QTabWidget)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QShortcut, QKeySequence
from app.ui_utils import get_icon

class WrappingListWidget(QListWidget):
    item_needs_widget = pyqtSignal(QListWidgetItem)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _on_scroll(self, *args):
        viewport_rect = self.viewport().rect()
        # Add margin to load slightly ahead of scrolling
        viewport_rect.adjust(0, -300, 0, 300)
        
        for i in range(self.count()):
            item = self.item(i)
            rect = self.visualItemRect(item)
            
            if rect.bottom() < viewport_rect.top():
                continue
            if rect.top() > viewport_rect.bottom():
                break
                
            if not self.itemWidget(item):
                self.item_needs_widget.emit(item)



class UserDataPanel(QWidget):
    # Emit chapter index, scroll percent, selected_text (optional)
    navigate_requested = pyqtSignal(int, float, str)
    delete_bookmark_requested = pyqtSignal(str)
    delete_note_requested = pyqtSignal(str)
    edit_note_requested = pyqtSignal(str, str)
    edit_bookmark_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from app.style_manager import load_qss
        self.setStyleSheet(load_qss("userdata_panel.qss"))
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(get_icon("bookmark.svg").pixmap(20, 20))

        title = QLabel(self.tr(" Bookmarks & Notes"))
        title.setObjectName("headerTitle")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Tabs
        self._tabs = QTabWidget()

        
        self._bookmarks_list = WrappingListWidget()
        self._bookmarks_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._bookmarks_list.itemClicked.connect(self._on_bookmark_clicked)
        self._bookmarks_list.item_needs_widget.connect(self._on_bookmark_needs_widget)
        self._bookmarks_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._bookmarks_list.customContextMenuRequested.connect(self._on_bookmark_context_menu)
        
        self._notes_list = WrappingListWidget()
        self._notes_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._notes_list.itemClicked.connect(self._on_note_clicked)
        self._notes_list.item_needs_widget.connect(self._on_note_needs_widget)
        self._notes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._notes_list.customContextMenuRequested.connect(self._on_note_context_menu)
        
        self._tabs.addTab(self._bookmarks_list, get_icon("bookmark.svg"), self.tr("Bookmarks"))
        self._tabs.addTab(self._notes_list, get_icon("note.svg"), self.tr("Notes"))
        
        layout.addWidget(self._tabs)

        del_shortcut = QShortcut(QKeySequence("Delete"), self)
        del_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        del_shortcut.activated.connect(self._on_delete_shortcut)

        edit_shortcut = QShortcut(QKeySequence("F2"), self)
        edit_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        edit_shortcut.activated.connect(self._on_edit_shortcut)



    def populate_data(self, bookmarks: list, notes: list):
        self._bookmarks_list.clear()
        self._notes_list.clear()
        
        # Populate bookmarks
        for b in bookmarks:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, b)
            item.setSizeHint(QSize(0, 48))
            self._bookmarks_list.addItem(item)
            
        # Populate notes
        for n in notes:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, n)
            item.setSizeHint(QSize(0, 145))
            self._notes_list.addItem(item)
            
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._bookmarks_list._on_scroll)
        QTimer.singleShot(0, self._notes_list._on_scroll)

    def _on_bookmark_needs_widget(self, item: QListWidgetItem):
        b = item.data(Qt.ItemDataRole.UserRole)
        if b:
            self._create_bookmark_widget(item, b)

    def _on_note_needs_widget(self, item: QListWidgetItem):
        n = item.data(Qt.ItemDataRole.UserRole)
        if n:
            self._create_note_widget(item, n)

    def _create_bookmark_widget(self, item: QListWidgetItem, b: dict):
        widget = QWidget()
        w_layout = QHBoxLayout(widget)
        w_layout.setContentsMargins(5, 5, 5, 5)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        pct = int(b.get("scroll_percent", 0.0) * 100)
        ch_label = QLabel(self.tr("Chapter {index}").format(index=b.get("chapter", 0) + 1) + f" ({pct}%)")
        ch_label.setObjectName("chapterLabel")
        header_layout.addWidget(ch_label)
        header_layout.addStretch()
        content_layout.addLayout(header_layout)
        
        label_text = b.get("label")
        if label_text:
            text_label = QLabel(label_text)
            text_label.setWordWrap(False)
            text_label.setMinimumWidth(1)
            text_label.setObjectName("bookmarkLabel")
        else:
            text_label = QLabel(self.tr("Bookmark"))
            text_label.setObjectName("bookmarkLabelEmpty")
        content_layout.addWidget(text_label)
        content_layout.addStretch()
        
        w_layout.addLayout(content_layout, 1)
        
        self._bookmarks_list.setItemWidget(item, widget)
        item.setSizeHint(QSize(0, 48))

    def _create_note_widget(self, item: QListWidgetItem, n: dict):
        widget = QWidget()
        w_layout = QHBoxLayout(widget)
        w_layout.setContentsMargins(5, 5, 5, 5)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        pct = int(n.get("scroll_percent", 0.0) * 100)
        ch_label = QLabel(self.tr("Chapter {index}").format(index=n.get("chapter", 0) + 1) + f" ({pct}%)")
        ch_label.setObjectName("chapterLabel")
        header_layout.addWidget(ch_label)
        header_layout.addStretch()
        content_layout.addLayout(header_layout)
        
        q_text = n.get("selected_text", "")
        if len(q_text) > 600:
            q_text = q_text[:600] + "..."
            
        if q_text:
            quote_label = QLabel(f'"{q_text}"')
            quote_label.setWordWrap(True)
            quote_label.setMinimumWidth(1)
        else:
            quote_label = QLabel()
        quote_label.setObjectName("quoteLabel")
        
        n_text = n.get("note", "")
        if len(n_text) > 600:
            n_text = n_text[:600] + "..."
        note_label = QLabel(n_text)
        note_label.setWordWrap(True)
        note_label.setMinimumWidth(1)
        note_label.setObjectName("noteLabel")
        
        if n.get("selected_text"):
            content_layout.addWidget(quote_label)
        content_layout.addWidget(note_label)
        content_layout.addStretch()
        
        w_layout.addLayout(content_layout, 1)
        
        self._notes_list.setItemWidget(item, widget)
        item.setSizeHint(QSize(0, 145))

    def _on_bookmark_clicked(self, item: QListWidgetItem):
        b = item.data(Qt.ItemDataRole.UserRole)
        if b:
            self.navigate_requested.emit(b.get("chapter", 0), b.get("scroll_percent", 0.0), "")

    def _on_note_clicked(self, item: QListWidgetItem):
        n = item.data(Qt.ItemDataRole.UserRole)
        if n:
            self.navigate_requested.emit(n.get("chapter", 0), n.get("scroll_percent", 0.0), n.get("selected_text", ""))

    def _on_bookmark_context_menu(self, pos):
        item = self._bookmarks_list.itemAt(pos)
        if not item: return
        b = item.data(Qt.ItemDataRole.UserRole)
        if not b: return
        
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        edit_action = menu.addAction(get_icon("pencil.svg"), self.tr("Edit"))
        del_action = menu.addAction(get_icon("delete.svg"), self.tr("Delete"))
        
        action = menu.exec(self._bookmarks_list.viewport().mapToGlobal(pos))
        if action == edit_action:
            self.edit_bookmark_requested.emit(b["id"], b.get("label", ""))
        elif action == del_action:
            self.delete_bookmark_requested.emit(b["id"])

    def _on_note_context_menu(self, pos):
        item = self._notes_list.itemAt(pos)
        if not item: return
        n = item.data(Qt.ItemDataRole.UserRole)
        if not n: return
        
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        edit_action = menu.addAction(get_icon("pencil.svg"), self.tr("Edit"))
        del_action = menu.addAction(get_icon("delete.svg"), self.tr("Delete"))
        
        action = menu.exec(self._notes_list.viewport().mapToGlobal(pos))
        if action == edit_action:
            self.edit_note_requested.emit(n["id"], n.get("note", ""))
        elif action == del_action:
            self.delete_note_requested.emit(n["id"])

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
