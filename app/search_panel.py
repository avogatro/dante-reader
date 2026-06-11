from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal, Qt

class SearchPanel(QWidget):
    result_selected = pyqtSignal(int, str)  # chapter_idx, query

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0d1117; color: #c9d1d9;")
        self._setup_ui()
        self._current_query = ""

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        self._title_label = QLabel("🔍 Search Results")
        self._title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e6e1d8;")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #58a6ff;
                border: none;
            }
            QPushButton:hover { text-decoration: underline; }
        """)
        self._clear_btn.clicked.connect(self.clear_results)
        self._clear_btn.hide()
        header_layout.addWidget(self._clear_btn)

        layout.addLayout(header_layout)

        self._status_label = QLabel("Type a query in the top bar to search.")
        self._status_label.setStyleSheet("color: #8b949e; font-style: italic;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet("""
            QListWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                border-bottom: 1px solid #30363d;
                padding: 10px;
            }
            QListWidget::item:hover {
                background-color: #21262d;
            }
            QListWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        self._list_widget.setWordWrap(True)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list_widget)

    def show_loading(self, query: str):
        self._current_query = query
        self._status_label.setText(f"Searching for '{query}'...")
        self._status_label.show()
        self._list_widget.clear()
        self._clear_btn.hide()

    def show_error(self, error: str):
        self._status_label.setText(f"Error: {error}")
        self._status_label.show()

    def load_results(self, results: list, query: str):
        self._current_query = query
        self._list_widget.clear()
        
        if not results:
            self._status_label.setText(f"No results found for '{query}'.")
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
            import re
            plain_snippet = re.sub(r'<[^>]+>', '', snippet)
            item.setText(f"{title}\n{plain_snippet}")
            
            self._list_widget.addItem(item)

    def clear_results(self):
        self._list_widget.clear()
        self._current_query = ""
        self._status_label.setText("Type a query in the top bar to search.")
        self._status_label.show()
        self._clear_btn.hide()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        chapter_idx = item.data(Qt.ItemDataRole.UserRole)
        if chapter_idx is not None and self._current_query:
            self.result_selected.emit(chapter_idx, self._current_query)
