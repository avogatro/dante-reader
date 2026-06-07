"""
Custom URL scheme handler for serving EPUB internal assets.
Registers an 'epub://' scheme so QWebEngineView can load CSS, images,
and fonts from the in-memory EPUB content without extracting to disk.
"""

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QUrl
from PyQt6.QtWebEngineCore import (
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
    QWebEngineUrlRequestJob,
)

# The scheme name MUST be registered before QApplication is created.
EPUB_SCHEME = b"epub"


def register_epub_scheme() -> None:
    """Register the 'epub' URL scheme with Qt. Call before QApplication()."""
    scheme = QWebEngineUrlScheme(EPUB_SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Path)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.CorsEnabled
    )
    QWebEngineUrlScheme.registerScheme(scheme)


class EpubSchemeHandler(QWebEngineUrlSchemeHandler):
    """
    Intercepts epub:// requests and serves content from the loaded EpubBook.

    URL format:
        epub://content/<internal_path>
        e.g. epub://content/OEBPS/Styles/style.css
             epub://content/OEBPS/Images/cover.jpg
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._book = None  # EpubBook instance
        self._html_processor = None  # Callable[[str, str], str]

    def set_book(self, book) -> None:
        """Set the active EpubBook whose assets we serve."""
        self._book = book

    def set_html_processor(self, processor) -> None:
        """Set a callback to process HTML before serving (e.g. for CSS injection)."""
        self._html_processor = processor

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:
        """Handle an incoming epub:// request."""
        url = job.requestUrl()
        host = url.host()
        path = url.path().lstrip("/")

        # Serve PDF.js viewer assets
        if host == "pdfjs":
            import os
            import mimetypes
            rel_path = path
            base_dir = os.path.join(os.path.dirname(__file__), "assets", "pdfjs")
            full_path = os.path.normpath(os.path.join(base_dir, rel_path))
            
            # Prevent directory traversal
            if not full_path.startswith(os.path.normpath(base_dir)) or not os.path.exists(full_path):
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
                
            with open(full_path, "rb") as f:
                data = f.read()
                
            if full_path.endswith(".mjs") or full_path.endswith(".js"):
                mime_type = "application/javascript"
            elif full_path.endswith(".wasm"):
                mime_type = "application/wasm"
            elif full_path.endswith(".css"):
                mime_type = "text/css"
            else:
                mime_type, _ = mimetypes.guess_type(full_path)
                if mime_type is None:
                    mime_type = "application/octet-stream"
                    
            buf = QBuffer(parent=self)
            buf.setData(QByteArray(data))
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            job.reply(mime_type.encode("utf-8"), buf)
            return

        # Serve user's PDF files
        if host == "pdf":
            import os
            import urllib.parse
            pdf_path = urllib.parse.unquote(path) # Decode in case of %20 spaces
            
            if not os.path.exists(pdf_path):
                print(f"[scheme] PDF not found: {pdf_path}")
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
                
            with open(pdf_path, "rb") as f:
                data = f.read()
                
            buf = QBuffer(parent=self)
            buf.setData(QByteArray(data))
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            job.reply(b"application/pdf", buf)
            return

        # EPUB Content
        if self._book is None or getattr(self._book, 'is_pdf', False):
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        # Look up the asset in the EPUB
        data = self._book.get_asset(path)
        if data is None:
            # Try without leading directory components (some EPUBs have varying paths)
            # e.g., "OEBPS/images/cover.jpg" vs "images/cover.jpg"
            for asset_name in self._book._assets:
                if asset_name.endswith(path) or path.endswith(asset_name):
                    data = self._book._assets[asset_name]
                    path = asset_name
                    break

        if data is None:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        mime_type = self._book.get_asset_type(path)

        # If it's an HTML file and we have a processor, inject our styles!
        if mime_type in ("text/html", "application/xhtml+xml") and self._html_processor:
            try:
                html_str = data.decode("utf-8")
                # Processor takes (html_string, file_path)
                html_str = self._html_processor(html_str, path)
                data = html_str.encode("utf-8")
            except Exception as e:
                print(f"[scheme] Error processing HTML for {path}: {e}")

        buf = QBuffer(parent=self)
        buf.setData(QByteArray(data))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(mime_type.encode("utf-8"), buf)
