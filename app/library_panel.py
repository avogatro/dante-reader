"""
Library Panel — Bookshelf grid displaying owned EPUB files.
Shows cover art thumbnails with titles in a scrollable grid layout.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt6.QtGui import QPixmap, QImage, QIcon, QFont, QColor, QPainter, QPen
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


def _generate_placeholder_cover(title: str, width: int = 140, height: int = 200) -> QImage:
    """Generate a simple placeholder cover with the book title."""
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#1c2333"))

    painter = QPainter(image)
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
    text_rect = image.rect().adjusted(14, 20, -14, -20)
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        title,
    )

    painter.end()
    return image


class LibraryScannerWorker(QThread):
    books_discovered = pyqtSignal(list)
    book_found = pyqtSignal(str, str, object)
    finished_scan = pyqtSignal(int)

    def run(self):
        epubs_dir = get_epubs_dir()
        if not os.path.isdir(epubs_dir):
            self.finished_scan.emit(-1)
            return

        book_files = []
        for root, _, files in os.walk(epubs_dir):
            for f in files:
                if f.lower().endswith((".epub", ".pdf", ".dante", ".zip")):
                    rel_path = os.path.relpath(os.path.join(root, f), epubs_dir)
                    book_files.append(rel_path)
                    
        book_files.sort(key=str.lower)
        
        discovered = []
        for filename in book_files:
            full_path = os.path.join(epubs_dir, filename)
            basename = os.path.basename(filename)
            title = os.path.splitext(basename)[0]
            import re
            title_clean = re.sub(r"\s*\[\d+\]\s*$", "", title)
            discovered.append((title_clean, full_path))
            
        self.books_discovered.emit(discovered)

        import hashlib
        import time
        from .config import PROJECT_ROOT
        
        cache_dir = os.path.join(PROJECT_ROOT, "app", ".cover_cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)

        for filename in book_files:
            full_path = os.path.join(epubs_dir, filename)
            basename = os.path.basename(filename)
            title = os.path.splitext(basename)[0]
            import re
            title_clean = re.sub(r"\s*\[\d+\]\s*$", "", title)

            cover_image = None
            
            # ── Check Cache ──
            cache_path = ""
            try:
                mtime = os.path.getmtime(full_path)
                cache_key = hashlib.md5(f"{full_path}_{mtime}".encode("utf-8")).hexdigest()
                cache_path = os.path.join(cache_dir, f"{cache_key}.png")
                
                if os.path.exists(cache_path):
                    img = QImage(cache_path)
                    if not img.isNull():
                        cover_image = img
            except Exception:
                pass

            # ── Cache Miss: Parse Book ──
            if cover_image is None:
                try:
                    if filename.lower().endswith(".pdf"):
                        book = PdfBook(full_path)
                    elif filename.lower().endswith((".dante", ".zip")):
                        book = DanteBook(full_path)
                    else:
                        book = EpubBook(full_path)
                        
                    cover_data = book.get_cover_image()
                    if cover_data:
                        img = QImage()
                        img.loadFromData(cover_data)
                        if not img.isNull():
                            cover_image = img.scaled(
                                140, 200,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                            # Save to cache
                            if cache_path:
                                cover_image.save(cache_path, "PNG")
                except Exception:
                    pass

            if cover_image is None:
                cover_image = _generate_placeholder_cover(title_clean)

            self.book_found.emit(title_clean, full_path, cover_image)
            
            # CRITICAL: Force the thread to yield the Python GIL so the main UI thread 
            # can process events (like clicking tabs) without freezing.
            time.sleep(0.01)
            
        self.finished_scan.emit(len(book_files))


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
        self._scanner = None
        self._setup_ui()
        self.scan_library()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Header ──
        header_layout = QHBoxLayout()
        
        icon_lbl = QLabel()
        from app.ui_utils import get_icon
        icon_lbl.setPixmap(get_icon("library.svg").pixmap(24, 24))
        
        header = QLabel(self.tr(" Library"))
        f = header.font()
        f.setPointSize(14)
        f.setWeight(QFont.Weight.Bold)
        header.setFont(f)
        header.setObjectName("headerTitle")
        
        btn_refresh = QPushButton()
        btn_refresh.setIcon(get_icon("refresh.svg"))
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.setObjectName("iconButton")
        btn_refresh.clicked.connect(self.scan_library)
        
        btn_close = QPushButton()
        btn_close.setIcon(get_icon("close.svg"))
        btn_close.setFixedSize(28, 28)
        btn_close.setObjectName("iconButton")
        btn_close.clicked.connect(self.close_requested.emit)
        
        header_layout.addWidget(icon_lbl)
        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(btn_refresh)
        header_layout.addWidget(btn_close)
        layout.addLayout(header_layout)

        # ── Search / Filter ──
        self._search = QLineEdit()
        self._search.setPlaceholderText(self.tr("Search books..."))
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
        
        self._list.itemDoubleClicked.connect(self._on_book_clicked)
        layout.addWidget(self._list)

        # ── Book Count ──
        self._count_label = QLabel("")
        self._count_label.setObjectName("countLabel")
        layout.addWidget(self._count_label)

        from app.style_manager import load_qss
        self.setStyleSheet(load_qss("library_panel.qss"))

    def scan_library(self) -> None:
        """Scan the e-pub directory and populate the book list asynchronously."""
        if self._scanner and self._scanner.isRunning():
            return
            
        self._books.clear()
        self._list.clear()
        self._count_label.setText(self.tr("Scanning library..."))

        self._scanner = LibraryScannerWorker()
        self._scanner.books_discovered.connect(self._on_books_discovered)
        self._scanner.book_found.connect(self._on_book_found)
        self._scanner.finished_scan.connect(self._on_scan_finished)
        self._scanner.start()

    def _on_books_discovered(self, discovered: list[tuple[str, str]]) -> None:
        self._list.setUpdatesEnabled(False)
        
        # Create one shared placeholder for all items
        placeholder = _generate_placeholder_cover("Loading...")
        from PyQt6.QtGui import QPixmap
        placeholder_pixmap = QPixmap.fromImage(placeholder)
        
        for title_clean, full_path in discovered:
            item = QListWidgetItem()
            item.setText(title_clean)
            item.setIcon(QIcon(placeholder_pixmap))
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            f = self.font()
            f.setPointSize(10)
            item.setFont(f)
            item.setSizeHint(QSize(160, 260))
            self._list.addItem(item)
            
            self._books.append({
                "path": full_path,
                "title": title_clean,
                "cover": placeholder_pixmap,
            })
            
        self._list.setUpdatesEnabled(True)

    def _on_book_found(self, title_clean: str, full_path: str, cover_image: object) -> None:
        cover_pixmap = QPixmap.fromImage(cover_image)

        # Update the placeholder item with the real cover
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == full_path:
                item.setIcon(QIcon(cover_pixmap))
                self._books[i]["cover"] = cover_pixmap
                break
        
    def _on_scan_finished(self, count: int) -> None:
        if count == -1:
            self._count_label.setText(self.tr("No e-pub directory found"))
        else:
            self._count_label.setText(f"{count} " + self.tr("books"))

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
