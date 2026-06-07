"""
Footnote Panel — Side panel that displays intercepted footnote content.
Opens when the user clicks a footnote anchor [N] in the reader.
Supports TTS read-aloud of footnote text.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QSizePolicy,
)


class FootnotePanel(QWidget):
    """
    Collapsible side panel for displaying footnote content.

    Signals:
        read_footnote_requested(str): Emitted with plain-text footnote for TTS
        close_requested(): Emitted when user closes the panel
    """

    read_footnote_requested = pyqtSignal(str)
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_text = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Header ──
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        header_icon = QLabel("📝")
        header_icon.setFont(QFont("Segoe UI", 14))
        header_icon.setStyleSheet("background: transparent;")
        header_layout.addWidget(header_icon)

        header_label = QLabel("Footnote")
        header_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header_label.setStyleSheet("color: #c9a96e; background: transparent;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        self._btn_read = QPushButton("🔊 Read")
        self._btn_read.setToolTip("Read this footnote aloud")
        self._btn_read.setFixedHeight(28)
        self._btn_read.clicked.connect(self._on_read_clicked)
        header_layout.addWidget(self._btn_read)

        self._btn_close = QPushButton("✕")
        self._btn_close.setFixedSize(28, 28)
        self._btn_close.setStyleSheet("""
            QPushButton {
                border: none;
                color: #8b949e;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #e6e1d8;
            }
        """)
        self._btn_close.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self._btn_close)

        layout.addLayout(header_layout)

        # ── Footnote ID Label ──
        self._id_label = QLabel("")
        self._id_label.setStyleSheet(
            "color: #8b949e; font-size: 11px; background: transparent; padding: 2px 0;"
        )
        layout.addWidget(self._id_label)

        # ── Content Browser ──
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setStyleSheet("""
            QTextBrowser {
                background-color: #161b22;
                color: #e6e1d8;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 12px;
                font-family: Georgia, "Times New Roman", serif;
                font-size: 15px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self._browser, 1)

        # ── Placeholder state ──
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        """Show placeholder message when no footnote is loaded."""
        self._browser.setHtml(
            '<div style="text-align: center; padding: 40px; color: #6e7681;">'
            '<p style="font-size: 28px;">📝</p>'
            '<p style="font-style: italic;">Click a footnote link [N] in the text<br>'
            "to view its content here.</p></div>"
        )
        self._id_label.setText("")
        self._btn_read.setEnabled(False)
        self._current_text = ""

    def show_footnote(self, anchor_id: str, html_content: str) -> None:
        """Display a footnote's HTML content in the panel."""
        from bs4 import BeautifulSoup

        # Clean the HTML: remove return links, style appropriately
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove "back" links (common in Gutenberg footnotes)
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "fnanchor" in href.lower() or "noteref" in href.lower():
                a.decompose()

        clean_html = str(soup)

        # Extract plain text for TTS
        self._current_text = soup.get_text(separator=" ", strip=True)

        # Wrap in styled container
        styled_html = f"""
        <div style="
            font-family: Georgia, 'Times New Roman', serif;
            font-size: 15px;
            line-height: 1.7;
            color: #e6e1d8;
        ">
            {clean_html}
        </div>
        """

        self._browser.setHtml(styled_html)
        self._id_label.setText(f"Anchor: #{anchor_id}")
        self._btn_read.setEnabled(bool(self._current_text))

    def _on_read_clicked(self) -> None:
        """Request TTS to read the current footnote text."""
        if self._current_text:
            self.read_footnote_requested.emit(self._current_text)

    def clear(self) -> None:
        """Reset to placeholder state."""
        self._show_placeholder()
