"""
Library Panel — Bookshelf grid displaying owned EPUB files.
Shows cover art thumbnails with titles in a scrollable grid layout.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QFont, QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from .epub_loader import EpubBook
from .pdf_book import PdfBook
from .dante_book import DanteBook
from .config import get_epubs_dir


def _generate_placeholder_cover(title: str, width: int = 140, height: int = 200) -> QPixmap:
    """Generate a simple placeholder cover with the book title."""
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#1c2333"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Border
    pen = QPen(QColor("#c9a96e"))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawRoundedRect(2, 2, width - 4, height - 4, 6, 6)

    # Inner decorative line
    pen.setWidth(1)
    pen.setColor(QColor("#30363d"))
    painter.setPen(pen)
    painter.drawRoundedRect(8, 8, width - 16, height - 16, 4, 4)

    # Title text
    painter.setPen(QColor("#e6e1d8"))
    font = QFont("Georgia", 9)
    font.setItalic(True)
    painter.setFont(font)

    # Word-wrap the title inside the cover
    text_rect = pixmap.rect().adjusted(14, 20, -14, -20)
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        title,
    )

    painter.end()
    return pixmap


class LibraryPanel(QWidget):
    """
    Sidebar panel showing the user's EPUB library as a visual bookshelf.
    Emits `book_selected(str)` with the full path when a book is chosen.
    """

    book_selected = pyqtSignal(str)  # Full path to the selected .epub
    close_requested = pyqtSignal()   # Emitted when the X button is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._books: list[dict] = []  # {"path": str, "title": str, "cover": QPixmap}
        self._setup_ui()
        self.scan_library()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Header ──
        header_layout = QHBoxLayout()
        header = QLabel("📚  Library")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #c9a96e; background: transparent; padding: 4px;")
        
        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.setStyleSheet("QPushButton { font-weight: bold; font-size: 18px; border: none; background: transparent; color: #e6e1d8; padding: 0px; margin: 0px; } QPushButton:hover { background: #30363d; border-radius: 4px; }")
        btn_refresh.setToolTip("Refresh Library")
        btn_refresh.clicked.connect(self.scan_library)

        btn_close = QPushButton("×")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("QPushButton { font-weight: bold; font-size: 18px; border: none; background: transparent; color: #e6e1d8; padding: 0px; margin: 0px; } QPushButton:hover { background: #30363d; border-radius: 4px; }")
        btn_close.setToolTip("Close Library")
        btn_close.clicked.connect(self.close_requested.emit)
        
        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(btn_refresh)
        header_layout.addWidget(btn_close)
        layout.addLayout(header_layout)

        # ── Search / Filter ──
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search books...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_books)
        layout.addWidget(self._search)

        # ── Book List ──
        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(140, 200))
        self._list.setGridSize(QSize(160, 260))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setWrapping(True)
        self._list.setSpacing(8)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setWordWrap(True)
        self._list.setStyleSheet("""
            QListWidget {
                background-color: #0d1117;
                border: none;
            }
            QListWidget::item {
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: rgba(201, 169, 110, 0.15);
                border: 1px solid #c9a96e;
            }
            QListWidget::item:hover {
                background-color: rgba(201, 169, 110, 0.08);
            }
        """)
        self._list.itemDoubleClicked.connect(self._on_book_clicked)
        layout.addWidget(self._list)

        # ── Book Count ──
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
        layout.addWidget(self._count_label)

    def scan_library(self) -> None:
        """Scan the e-pub directory and populate the book list."""
        self._books.clear()
        self._list.clear()

        epubs_dir = get_epubs_dir()

        if not os.path.isdir(epubs_dir):
            self._count_label.setText("No e-pub directory found")
            return

        book_files = []
        for root, _, files in os.walk(epubs_dir):
            for f in files:
                if f.lower().endswith((".epub", ".pdf", ".dante", ".zip")):
                    # Store path relative to epubs_dir so the UI doesn't get cluttered with full paths
                    rel_path = os.path.relpath(os.path.join(root, f), epubs_dir)
                    book_files.append(rel_path)
                    
        book_files.sort(key=str.lower)

        for filename in book_files:
            full_path = os.path.join(epubs_dir, filename)
            # Extract display title from the basename: strip extension and [ID]
            basename = os.path.basename(filename)
            title = os.path.splitext(basename)[0]
            import re
            title_clean = re.sub(r"\s*\[\d+\]\s*$", "", title)

            # Try to extract cover from EPUB/PDF/Dante (quick load)
            cover_pixmap = None
            try:
                if filename.lower().endswith(".pdf"):
                    book = PdfBook(full_path)
                elif filename.lower().endswith((".dante", ".zip")):
                    book = DanteBook(full_path)
                else:
                    book = EpubBook(full_path)
                    
                cover_data = book.get_cover_image()
                if cover_data:
                    pix = QPixmap()
                    pix.loadFromData(cover_data)
                    if not pix.isNull():
                        cover_pixmap = pix.scaled(
                            140, 200,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
            except Exception:
                pass

            if cover_pixmap is None:
                cover_pixmap = _generate_placeholder_cover(title_clean)

            self._books.append({
                "path": full_path,
                "title": title_clean,
                "cover": cover_pixmap,
            })

            item = QListWidgetItem()
            item.setText(title_clean)
            item.setIcon(QIcon(cover_pixmap))
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            item.setFont(QFont("Segoe UI", 10))
            item.setSizeHint(QSize(160, 260))
            self._list.addItem(item)

        self._count_label.setText(f"{len(self._books)} books")

    def _filter_books(self, text: str) -> None:
        """Filter visible books by search text."""
        text_lower = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            visible = text_lower in item.text().lower()
            item.setHidden(not visible)

    def _on_book_clicked(self, item: QListWidgetItem) -> None:
        """Handle book selection."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.book_selected.emit(path)
