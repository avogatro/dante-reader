import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.ui_utils import get_icon
from app.style_manager import load_qss

class SearchPanel(QWidget):
    result_selected = pyqtSignal(int, str)  # chapter_idx, query
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setStyleSheet(load_qss("search_panel.qss"))
        self._setup_ui()
        self._current_query = ""

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        # Header
        header_layout = QHBoxLayout()
        
        header_icon = QLabel()
      
        header_icon.setPixmap(get_icon("search.svg").pixmap(24, 24))
        header_layout.addWidget(header_icon)
        
        self._title_label = QLabel(self.tr(" Search Results"))
        self._title_label.setObjectName("headerTitle")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        self._clear_btn = QPushButton(self.tr("Clear"))
        self._clear_btn.setObjectName("clearButton")
        self._clear_btn.clicked.connect(self.clear_results)
        self._clear_btn.hide()
        header_layout.addWidget(self._clear_btn)

        layout.addLayout(header_layout)

        self._status_label = QLabel(self.tr("Type a query in the top bar to search."))
        self._status_label.setObjectName("statusLabel")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._list_widget = QListWidget()
        
        self._list_widget.setWordWrap(True)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list_widget)

    def show_loading(self, query: str):
        self._current_query = query
        self._status_label.setText(self.tr("Searching for '{query}'...").format(query=query))
        self._status_label.show()
        self._list_widget.clear()
        self._clear_btn.hide()

    def show_error(self, error: str):
        self._status_label.setText(self.tr("Error: {error}").format(error=error))
        self._status_label.show()

    def load_results(self, results: list, query: str):
        self._current_query = query
        self._list_widget.clear()
        
        if not results:
            self._status_label.setText(self.tr("No results found for '{query}'.").format(query=query))
            self._status_label.show()
            self._clear_btn.hide()
            return
            
        self._status_label.hide()
        self._clear_btn.show()
        
        for res in results:
            item = QListWidgetItem()
            # We use setToolTip to store the plain text data, but we can also store custom data
            item.setData(Qt.ItemDataRole.UserRole, res["chapter_idx"])
            
            # Format the item
            title = res.get("title", "Unknown Chapter")
            snippet = res.get("snippet", "")
            
            # Basic HTML formatting is tricky in QListWidgetItem directly, 
            # so we'll just set text and rely on rich text if possible.
            # QListWidget items don't support HTML naturally, but we can use a custom widget 
            # if we want. For simplicity, let's strip HTML from snippet for the list item text

            plain_snippet = re.sub(r'<[^>]+>', '', snippet)
            item.setText(f"{title}\n{plain_snippet}")
            
            self._list_widget.addItem(item)

    def clear_results(self):
        self._list_widget.clear()
        self._current_query = ""
        self._status_label.setText(self.tr("Type a query in the top bar to search."))
        self._status_label.show()
        self._clear_btn.hide()
        self.clear_requested.emit()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        chapter_idx = item.data(Qt.ItemDataRole.UserRole)
        if chapter_idx is not None and self._current_query:
            self.result_selected.emit(chapter_idx, self._current_query)
