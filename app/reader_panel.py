"""
Reader Panel — Central reading area using QWebEngineView.
Renders EPUB chapter XHTML with dark mode CSS injection, text selection,
footnote link interception, and dynamic font/spacing controls.

Link interception uses QWebEnginePage.acceptNavigationRequest() at the
C++ level — far more reliable than injected JS which can fail due to
qwebchannel.js loading issues with custom URL schemes.
"""

import os
import re
import json
import traceback
import urllib.parse
import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QUrlQuery
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QCheckBox,
)
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineNavigationRequest,
    QWebEngineProfile,
    QWebEnginePage,
)

from .epub_loader import EpubBook
from .pdf_book import PdfBook
from app.ui_utils import get_icon_path
from app.config import get_max_width_px
from app.services.html_processor import EpubHtmlProcessor
from app.translation_parser import inject_translation_ids, inject_translated_text
from app.reader_context_menu import ReaderContextMenu
from app.source_viewer import SourceViewerWindow
from .table_layout_manager import TableLayoutManager
from .translation_helper import TranslationHelper


class ReaderPanel(QWidget):
    """
    Central EPUB reader panel with chapter navigation and reading controls.

    Signals:
        text_selected(str): text selected by user
        chapter_changed(int): Emitted when a new chapter loads
    """

    chapter_changed = pyqtSignal(int)
    text_selected = pyqtSignal(str)
    read_selection_requested = pyqtSignal(str)
    translation_requested = pyqtSignal(list)
    library_toggle_requested = pyqtSignal()
    ai_toggle_requested = pyqtSignal()
    focus_toggle_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    
    bookmark_requested = pyqtSignal(int, float)
    note_requested = pyqtSignal(int, float, str)
    
    # Text selection signals
    ai_explain_requested = pyqtSignal()
    ai_translate_requested = pyqtSignal()
    
    # Context menu TTS signals
    play_chapter_requested = pyqtSignal()
    stop_tts_requested = pyqtSignal()
    prev_chapter_requested = pyqtSignal()
    next_chapter_requested = pyqtSignal()
    
    # Media & Context signals
    audio_play_requested = pyqtSignal(str)
    footnote_requested = pyqtSignal(str)
    dictionary_lookup_requested = pyqtSignal(str)

    def __init__(self, scheme_handler, parent=None):
        super().__init__(parent)
        self._scheme_handler = scheme_handler
        self._book: EpubBook | PdfBook | None = None
        self._current_chapter = 0
        self._dark_mode = True
        self._first_load = False
        self._font_family = "Georgia"
        self._font_size = 18
        self._line_height = 1.8
        self._page_width = 750
        self._pdf_reading_mode = False
        self._last_rendered_html = ""   # Store for "View Source"
        self._last_original_html = ""   # Pre-injection EPUB HTML
        self._source_windows = []       # Keep references so they don't get GC'd
        self._table_layout_manager = TableLayoutManager(self)
        self._translation_helper = TranslationHelper(self)
        self._scheme_handler.set_html_processor(self._process_html)
        self._setup_ui()
        
        # Register global shortcuts for actions not in the main window menu
        shortcuts = [
            ("Ctrl+U", self._open_source_viewer),
            ("F5", self.play_chapter_requested.emit),
            ("F7", self.stop_tts_requested.emit),
            ("Ctrl+E", self.ai_explain_requested.emit),
            ("Ctrl+T", self.ai_translate_requested.emit),
            ("Ctrl+Shift+S", self._trigger_read_selection_from_shortcut),
            ("Ctrl+B", self._trigger_add_bookmark),
            ("Ctrl+N", self._trigger_add_note_from_shortcut),
        ]
        
        for key, slot in shortcuts:
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(slot)
            self.addAction(action)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Table Translation / Dante Controls ──
        self._table_nav_bar = QHBoxLayout()
        self._table_nav_bar.setContentsMargins(12, 6, 12, 6)
        self._table_nav_bar.setSpacing(15)
        
        self._track_toggles_layout = QHBoxLayout()
        self._track_toggles_layout.setSpacing(10)
        self._track_toggles_layout.setContentsMargins(0, 0, 0, 0)
        self._table_nav_bar.addLayout(self._track_toggles_layout)
        
        self._dynamic_checkboxes = {}
        
        self._btn_translate_page = QPushButton(self.tr("AI: Translate Page"))
  
        self._btn_translate_page.clicked.connect(self._translation_helper.translate_visible_page)
        self._table_nav_bar.addWidget(self._btn_translate_page)
        
        self._table_nav_bar.addStretch()
        
        self._label_tts= QLabel(self.tr("TTS:"))
        self._table_nav_bar.addWidget(self._label_tts)
        self._table_tts_combo = QComboBox()
        self._table_tts_combo.addItems([self.tr("Original"), self.tr("AI Translation")])
        self._table_nav_bar.addWidget(self._table_tts_combo)
        
        self._table_controls_widget = QWidget()
        self._table_controls_widget.setObjectName("tableControls")
        self._table_controls_widget.setLayout(self._table_nav_bar)
        self._table_controls_widget.setObjectName("tableControls")
        self._table_controls_widget.hide()
        layout.addWidget(self._table_controls_widget)

        # ── Web View ──
        self._profile = QWebEngineProfile("ReaderProfile", self)
        self._profile.installUrlSchemeHandler(b"epub", self._scheme_handler)

        self._web = QWebEngineView(self)
        self._page = QWebEnginePage(self._profile, self._web)
        self._web.setPage(self._page)
        self._web.setObjectName("webEngine")
        self._web.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._web.customContextMenuRequested.connect(self._show_context_menu)
        self._page.navigationRequested.connect(self._on_navigation_requested)
        self._page.selectionChanged.connect(self._on_selection_changed)
        self._page.loadFinished.connect(self._on_page_load_finished)

        layout.addWidget(self._web, 1)

        self._translation_manager = None
        self.show_placeholder()

    def show_placeholder(self) -> None:
        """Display the app logo and name when no book is loaded."""
        icon_path = get_icon_path("logo_mountain.svg")
        template_path = os.path.join(os.path.dirname(__file__), "assets", "html", "placeholder.html")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                html = f.read().replace("{icon_path}", icon_path)
        except Exception:
            html = "<html><body><h1>Dante Reader</h1></body></html>"
        
        self._web.setHtml(html, QUrl(f"file:///{os.path.dirname(__file__).replace(chr(92), '/')}"))

    def set_tts_target(self, target: str):
        self._tts_target = target

    def _on_chapter_translated(self, index: int):
        self._translation_helper.on_chapter_translated(index)

    def _on_translation_error(self, index: int, error_msg: str):
        self._translation_helper.on_translation_error(index, error_msg)

    def _on_page_load_finished(self, ok: bool) -> None:
        # If it's a PDF, apply the dark mode preference instantly upon load
        if self._book and getattr(self._book, 'is_pdf', False):
            self.set_dark_mode(getattr(self, '_dark_mode', True))
            
        if self._book and not getattr(self._book, 'is_pdf', False):
            self._table_layout_manager.update_table_layout()

        if ok and getattr(self, '_first_load', False):
            # Only force this aggressive repaint once when the book is initially loaded (cover page)
            self._first_load = False
            
            QTimer.singleShot(50, self._web.update)
            self._page.runJavaScript("if (typeof window.readerBridge !== 'undefined') window.readerBridge.forceRepaint();")

    # ── Book Loading ──

    def load_book(self, book, target_page: int = 1) -> None:
        """Load a new book and display the first chapter or the PDF."""
        self._book = book
        self._first_load = True
        self._translation_manager = None
        
        is_pdf = getattr(book, 'is_pdf', False)
        
        # If it's a PDF AND we are NOT in reading mode, hide nav and route to PDF.js
        if is_pdf and not self._pdf_reading_mode:
            # URL encode the local absolute path so it survives the ?file= query parameter
            encoded_path = urllib.parse.quote(book.path)
            
            # Since we manage dark mode via a CSS class on the body, we can just load the viewer 
            # and inject the class via javascript, but to avoid flashing we can pass it as a param too.
            viewer_url = f"epub://pdfjs/web/viewer.html?file=epub://pdf/{encoded_path}#page={target_page}"
            
            self._web.load(QUrl(viewer_url))
            self.chapter_changed.emit(0)
            return

        # EPUB (or PDF in Reading Mode) or Dante: setup chapter navigation
        if is_pdf:
            self._book.set_reading_mode(True)
            
        # Clear existing track toggles
        for i in reversed(range(self._track_toggles_layout.count())): 
            widget = self._track_toggles_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self._dynamic_checkboxes.clear()
        
        if getattr(book, 'is_dante', False):
            self._page_width = get_max_width_px()
            
            tracks = getattr(book, 'metadata', {}).get('tracks', {})
            
            # Ensure AI Translation track is always available as an option
            if "translation" not in tracks:
                tracks["translation"] = {"label": "AI Translation", "type": "translation"}
            
            for key, val in tracks.items():
                chk = QCheckBox(val.get("label", key))
                chk.setObjectName("tableCheck")
                # Initially uncheck pronunciation tracks and the AI translation track
                chk.setChecked(val.get("type") != "pronunciation" and key not in ("ai_translation", "translation"))
                chk.stateChanged.connect(self._table_layout_manager.update_table_layout)
                self._track_toggles_layout.addWidget(chk)
                self._dynamic_checkboxes[key] = chk
            
            self._table_tts_combo.blockSignals(True)
            self._table_tts_combo.clear()
            for key, val in tracks.items():
                self._table_tts_combo.addItem(val.get("label", ""), key)
            if self._table_tts_combo.count() > 0:
                self._table_tts_combo.setCurrentIndex(0)
            self._table_tts_combo.blockSignals(False)
        else:
            self._chk_col_original = QCheckBox(self.tr("Original"))
            self._chk_col_original.setObjectName("tableCheck")
            self._chk_col_original.setChecked(True)
            self._chk_col_original.stateChanged.connect(self._table_layout_manager.update_table_layout)
            self._track_toggles_layout.addWidget(self._chk_col_original)
            
            self._chk_col_translation = QCheckBox(self.tr("AI Translation"))
            self._chk_col_translation.setObjectName("tableCheck")
            self._chk_col_translation.setChecked(False)
            self._chk_col_translation.stateChanged.connect(self._table_layout_manager.update_table_layout)
            self._track_toggles_layout.addWidget(self._chk_col_translation)
            
            self._dynamic_checkboxes["original"] = self._chk_col_original
            self._dynamic_checkboxes["translation"] = self._chk_col_translation
            
            self._table_tts_combo.blockSignals(True)
            self._table_tts_combo.clear()
            self._table_tts_combo.addItems([self.tr("Original"), self.tr("AI Translation")])
            self._table_tts_combo.setCurrentText(self.tr("Original"))
            self._table_tts_combo.blockSignals(False)
                
        self._table_controls_widget.show()
        self._table_layout_manager.update_table_layout()

        self._scheme_handler.set_book(book)

        # Build file_name → chapter index map for cross-file link resolution
        self._fname_to_chapter: dict[str, int] = {}
        if hasattr(book, 'chapters'):
            for ch in book.chapters:
                self._fname_to_chapter[ch.file_name] = ch.index
                # Also map just the basename for loose matching
                basename = ch.file_name.rsplit("/", 1)[-1]
                self._fname_to_chapter[basename] = ch.index


        if is_pdf and self._pdf_reading_mode:
            self._load_chapter(target_page - 1)
        else:
            self._load_chapter(0)

    def _load_chapter(self, index: int, scroll_to_anchor: str = "") -> None:
        """Load and render a specific chapter, optionally scrolling to an anchor."""
        if not self._book:
            return

        chapter = self._book.get_chapter(index)
        if not chapter:
            return

        self._current_chapter = index

        if getattr(self._book, 'is_pdf', False):
            # For PDF Reading Mode, get_chapter returns a raw HTML string.
            # We process it to inject CSS, then render it directly via setHtml.
            html = chapter
            html = self._process_html(html, f"page_{index}.html")
            self._web.setHtml(html, QUrl("epub://content/"))
        elif getattr(self._book, 'is_dante', False):
            # For Dante Mode, generate the grid table HTML
            html = chapter.get_html()
            html = self._process_html(html, f"canto_{index}.html")
            self._web.setHtml(html, QUrl("epub://content/"))
            
            # Apply initial column visibility
            QTimer.singleShot(100, self._table_layout_manager.update_table_layout)
        else:
            # For EPUBs, get_chapter returns a Chapter object with a file_name.
            # We navigate to it via the scheme handler so relative assets load.
            url = QUrl(f"epub://content/{chapter.file_name}")
            if self._web.url() == url:
                self._web.reload()
            else:
                self._web.setUrl(url)

        # If we need to scroll to a specific anchor after load
        if scroll_to_anchor:
            QTimer.singleShot(300, lambda: self._scroll_to_anchor(scroll_to_anchor))

        # Update nav controls
        self.chapter_changed.emit(index)

    def _scroll_to_anchor(self, anchor_id: str) -> None:
        """Scroll the web view to a specific anchor element."""
        self._page.runJavaScript(f"if (typeof window.readerBridge !== 'undefined') window.readerBridge.scrollToAnchor('{anchor_id}');")

    def _process_html(self, html: str, file_path: str) -> str:
        """Callback from EpubSchemeHandler: injects CSS dynamically into HTML."""
        self._last_original_html = html
        
        # Strip XML declaration from the top to prevent injections/parsers from messing with it
        xml_decl = ""
        match = re.match(r'^(\s*<\?xml[^>]*\?>)', html, re.IGNORECASE)
        if match:
            xml_decl = match.group(1).strip() + "\n"
            html = html[match.end():]

        try:
            settings = {
                "page_width": self._page_width,
                "font_family": self._font_family,
                "font_size": self._font_size,
                "line_height": self._line_height,
                "dark_mode": self._dark_mode
            }
            html = EpubHtmlProcessor.process(html, file_path, settings)
            
            # Inject the active table layout directly into the HTML so it takes effect instantly
            layout_css = f"<style id='table-column-toggles'>{self._table_layout_manager.get_table_layout_css()}</style>"
            html = EpubHtmlProcessor._inject_head_content(html, layout_css)
        except Exception as e:
            traceback.print_exc()
            print("CRASH IN HTML PROCESSOR:", e)
        
        self._last_rendered_html = xml_decl + html
        
        # Inject translation IDs for EPUBs
        if not getattr(self._book, 'is_dante', False):
            html = inject_translation_ids(html)
            
        # If we already have translations for this chapter, inject them right away (for both EPUB and Dante)
        if self._translation_manager and self._translation_manager.has_chapter(self._current_chapter):
            trans_dict = self._translation_manager.get_chapter(self._current_chapter)
            html = inject_translated_text(html, trans_dict)
                
        # Fix SVG attribute casing AFTER all BeautifulSoup manipulations have finished!
        html = re.sub(r'\bviewbox\s*=', 'viewBox=', html, flags=re.IGNORECASE)
        html = re.sub(r'\bpreserveaspectratio\s*=', 'preserveAspectRatio=', html, flags=re.IGNORECASE)
        
        self._last_rendered_html = xml_decl + html
        return self._last_rendered_html

    # ══════════════════════════════════════
    # Navigation Request Handler (signal-based)
    # ══════════════════════════════════════

    def _on_navigation_requested(self, request: QWebEngineNavigationRequest) -> None:
        """Handle link clicks natively via Qt WebEngine."""
        url = request.url()
        scheme = url.scheme()
        path = url.path().lstrip("/")
        
        # Intercept our custom actions
        if scheme == "epub" and url.host() == "action":
            self._handle_action_url(request, path, url)
            return

        try:
            nav_type = request.navigationType()

            # Only intercept user-clicked links — let everything else pass through
            if nav_type != QWebEngineNavigationRequest.NavigationType.LinkClickedNavigation:
                return  # Qt auto-accepts when no reject() is called

            url = request.url()
            scheme = url.scheme()
            fragment = url.fragment()
            path = url.path().lstrip("/")

            print(f"[reader] Link clicked: scheme={scheme} path={path!r} fragment={fragment!r}", flush=True)

            # ── Case 1: External HTTP(S) links ──
            if scheme in ("http", "https"):
                request.reject()
                url_str = url.toString()
                QTimer.singleShot(0, lambda: webbrowser.open(url_str))
                return

            # ── Case 2: Pure anchor link (#footnote123, no file path) ──
            if fragment and (not path or path == "/"):
                # DO NOT REJECT. Let Chromium handle it natively.
                # This adds a history state, so mouse-back works!
                return

            # ── Case 3: epub:// link ──
            if scheme == "epub":
                self._handle_epub_link(request, path, fragment)
                return

        except Exception as e:
            print(f"[reader] Error in navigation handler: {e!r}", flush=True)

    def _handle_action_url(self, request: QWebEngineNavigationRequest, path: str, url: QUrl) -> None:
        request.reject()
        if path == "next-chapter":
            QTimer.singleShot(0, self._next_chapter)
        elif path == "media":
            query = QUrlQuery(url.query())
            media_type = query.queryItemValue("type")
            media_id = query.queryItemValue("id")
            
            if media_type == "audio":
                QTimer.singleShot(0, lambda: self._handle_audio_click(media_id))
            elif media_type == "video":
                QTimer.singleShot(0, lambda: self._handle_video_click(media_id))
            elif media_type == "foot":
                QTimer.singleShot(0, lambda: self._handle_footnote_click(media_id))
        elif path == "dict":
            query = QUrlQuery(url.query())
            word = query.queryItemValue("word")
            if word:
                # QUrlQuery returns URL-encoded string. We decode it.
                word = urllib.parse.unquote(word)
                QTimer.singleShot(0, lambda: self.dictionary_lookup_requested.emit(word))

    def _handle_epub_link(self, request: QWebEngineNavigationRequest, path: str, fragment: str) -> None:
        # Check if this link points to the CURRENT chapter file
        is_same_page = False
        if self._book and fragment:
            current_ch = self._book.get_chapter(self._current_chapter)
            if current_ch:
                current_fname = current_ch.file_name
                current_basename = current_fname.rsplit("/", 1)[-1]
                link_basename = path.rsplit("/", 1)[-1]
                if link_basename == current_basename or path == current_fname:
                    is_same_page = True

        if is_same_page:
            print(f"[reader]   -> Same-page anchor: #{fragment}", flush=True)
            # DO NOT REJECT. Let Chromium handle natively to track history.
            return
        else:
            # REJECT cross-file navigation so we can inject styles
            request.reject()
            p, f = path, fragment or ""
            print(f"[reader]   -> Cross-file nav: {p!r} #{f!r}", flush=True)
            QTimer.singleShot(0, lambda: self._on_chapter_link_clicked(p, f))

    def _handle_audio_click(self, media_id: str) -> None:
        self.audio_play_requested.emit(media_id)

    def _handle_video_click(self, media_id: str) -> None:
        if not self._book or not hasattr(self._book, 'videos'):
            return
        video_data = self._book.videos.get(media_id)
        if not video_data:
            return
        url = video_data.get("url", "")
        start_time = video_data.get("start_timestamp", 0)
        if url:
            if "youtube.com" in url or "youtu.be" in url:
                if "?" in url:
                    url += f"&t={start_time}s"
                else:
                    url += f"?t={start_time}s"
            webbrowser.open(url)

    def _handle_footnote_click(self, media_id: str) -> None:
        if not self._book or not hasattr(self._book, 'footnotes'):
            return
        if media_id not in self._book.footnotes:
            return
        self.footnote_requested.emit(media_id)



    def _on_chapter_link_clicked(self, file_path: str, fragment: str) -> None:
        """
        Handle a cross-file EPUB link (e.g. clicking a canto link).
        Find the target chapter and load it through our styled pipeline.
        """
        try:
            if not self._book:
                return

            # Try to find the chapter by file path
            chapter_idx = self._fname_to_chapter.get(file_path)

            # Try basename if full path didn't match
            if chapter_idx is None:
                basename = file_path.rsplit("/", 1)[-1]
                chapter_idx = self._fname_to_chapter.get(basename)

            # Try stripping common prefixes
            if chapter_idx is None:
                for fname, idx in self._fname_to_chapter.items():
                    if file_path.endswith(fname) or fname.endswith(file_path):
                        chapter_idx = idx
                        break

            if chapter_idx is not None:
                self._load_chapter(chapter_idx, scroll_to_anchor=fragment)
            else:
                print(f"[reader] Warning: could not find chapter for link: {file_path!r}", flush=True)
        except Exception as e:
            print(f"[reader] Error handling chapter link: {e!r}", flush=True)

    # ── Text Selection (native, no JS bridge needed) ──

    def _on_selection_changed(self) -> None:
        """Handle text selection via the built-in QWebEnginePage signal."""
        
        def _emit_cleaned(result_str: str):
            if not result_str:
                return
            
            try:
                data = json.loads(result_str)
                text = data.get("text", "")
                track = data.get("track", "")
            except Exception:
                text = result_str
                track = ""
                
            if not text:
                return
                
            # If we identified the track column of the selection, sync the TTS combobox
            if track:
                index = self._table_tts_combo.findData(track)
                if index >= 0:
                    self._table_tts_combo.setCurrentIndex(index)
                else:
                    # Fallback for normal EPUB mode without data keys
                    if track == "original":
                        idx = self._table_tts_combo.findText("Original")
                        if idx >= 0:
                            self._table_tts_combo.setCurrentIndex(idx)
                    elif track == "translation" or track == "ai_translation":
                        idx = self._table_tts_combo.findText("AI Translation")
                        if idx >= 0:
                            self._table_tts_combo.setCurrentIndex(idx)
                            
            # Remove multiple empty lines caused by table DOM gaps
            cleaned = "\n".join([line for line in text.splitlines() if line.strip()])
            if cleaned:
                self.text_selected.emit(cleaned)
                
        # Constrain selection to a single column in table/grid mode, and identify track
        js = "if (typeof window.getConstrainedSelection === 'function') { window.getConstrainedSelection(); } else { JSON.stringify({text:'', track:''}); }"
        self._page.runJavaScript(js, _emit_cleaned)

    # ── Navigation ──

    def _prev_chapter(self) -> None:
        if self._current_chapter > 0:
            self._load_chapter(self._current_chapter - 1)

    def _next_chapter(self) -> None:
        if self._book and self._current_chapter < self._book.get_chapter_count() - 1:
            self._load_chapter(self._current_chapter + 1)
    def go_to_chapter(self, index: int) -> None:
        """Public method to navigate to a specific chapter."""
        self._load_chapter(index)

    # ── Reading Preferences ──

    def set_pdf_reading_mode(self, enabled: bool) -> None:
        if self._pdf_reading_mode == enabled:
            return
            
        if not self._book or not getattr(self._book, 'is_pdf', False):
            self._pdf_reading_mode = enabled
            return

        def _execute_switch(target_page: int = 1):
            self._pdf_reading_mode = enabled
            self._book.set_reading_mode(enabled)
            self.load_book(self._book, target_page=target_page)

        if enabled:
            # Switching TO reading mode from PDF.js
            # Ask PDF.js for current page, then switch.
            self._page.runJavaScript(
                "typeof PDFViewerApplication !== 'undefined' ? PDFViewerApplication.page : 1", 
                lambda p: _execute_switch(int(p) if p else 1)
            )
        else:
            # Switching TO PDF.js from reading mode
            # We already know the current chapter index (page - 1).
            target_page = self._current_chapter + 1
            _execute_switch(target_page)

    def set_dark_mode(self, enabled: bool) -> None:
        self._dark_mode = enabled
        if self._book and getattr(self._book, 'is_pdf', False):
            # Tell PDF.js viewer to toggle the dark-mode class on the body
            js = f"if (typeof window.readerBridge !== 'undefined' && window.readerBridge.setPdfDarkMode) window.readerBridge.setPdfDarkMode({'true' if enabled else 'false'});"
            self._page.runJavaScript(js)
        else:
            self._reload_current()

    def reset_pdf_settings(self) -> None:
        if self._book and getattr(self._book, 'is_pdf', False):
            self._page.runJavaScript("if (typeof window.readerBridge !== 'undefined') window.readerBridge.resetPdfSettings();")

    def set_font_family(self, family: str) -> None:
        self._font_family = family
        self._reload_current()

    def set_font_size(self, size: int) -> None:
        self._font_size = size
        self._reload_current()

    def set_line_height(self, height: float) -> None:
        self._line_height = height
        self._reload_current()

    def set_page_width(self, width: int) -> None:
        self._page_width = width
        self._reload_current()

    def _get_active_page(self):
        return self._page

    def _reload_current(self) -> None:
        """Reload current chapter with updated styles."""
        if self._book:
            self._load_chapter(self._current_chapter)

    # ── Text Extraction for TTS ──

    def get_current_chapter_text(self, callback) -> None:
        """Extract plain text from the current chapter HTML for TTS asynchronously."""
        if not self._book:
            callback("")
            return
            
        target_key = self._table_tts_combo.currentData()
        if target_key:
            target_selector = f".track-{target_key}"
        else:
            # Standard EPUB mode
            target = self._table_tts_combo.currentText()
            if target == "Original":
                target_selector = ".track-original"
            else:
                target_selector = ".track-translation"
        safe_target = json.dumps(target_selector) if target_selector else "''"
        js = f"if (typeof window.extractChapterText === 'function') {{ window.extractChapterText({safe_target}); }} else {{ ''; }}"
        self._get_active_page().runJavaScript(js, callback)
    def get_current_chapter_index(self) -> int:
        return self._current_chapter

    def highlight_sentence(self, text: str) -> None:
        """Find and highlight the given sentence in the DOM while clearing previous highlights."""
        safe_text = json.dumps(text) if text else "''"
        
        target_key = self._table_tts_combo.currentData()
        target_class = ""
        if target_key:
            target_class = f".track-{target_key}"
        else:
            # Standard EPUB mode
            target = self._table_tts_combo.currentText()
            if target == "Original":
                target_class = ".track-original"
            elif target == "AI Translation":
                target_class = ".track-translation"
                
        safe_target = json.dumps(target_class) if target_class else "''"
       
        js = f"if (typeof window.highlightTTS === 'function') {{ window.highlightTTS({safe_text}, {safe_target}); }}"
        self._get_active_page().runJavaScript(js)

    # ── Context Menu ──

    def _show_context_menu(self, pos) -> None:
        """Show custom right-click context menu with View Source option."""
        ReaderContextMenu.show_menu(self, pos)

    def _open_source_viewer(self) -> None:
        """Open a new window showing the current chapter's source and CSS."""
        if not self._book:
            return

        def on_html(rend_html: str):
            chapter = self._book.get_chapter(self._current_chapter)
            chapter_title = self.tr("Chapter {index}").format(index=self._current_chapter)
            orig_html = self._last_original_html
            css_sheets = []

            if getattr(self._book, 'is_pdf', False):
                chapter_title = self.tr("Page {index}").format(index=self._current_chapter + 1)
                if getattr(self._book, '_reading_mode', False):
                    if isinstance(chapter, str):
                        orig_html = chapter
                else:
                    orig_html = self.tr("<!-- PDF.js Native Viewer -->")
            else:
                if chapter and hasattr(chapter, 'title'):
                    chapter_title = chapter.title
                if hasattr(self._book, '_book') and self._book._book:
                    from ebooklib import ITEM_STYLE
                    for item in self._book._book.get_items_of_type(ITEM_STYLE):
                        name = item.get_name()
                        try:
                            content = item.get_content().decode("utf-8", errors="replace")
                        except Exception:
                            content = "/* Could not decode CSS */"
                        css_sheets.append((name, content))

            win = SourceViewerWindow(
                rendered_html=rend_html,
                original_html=orig_html,
                css_sheets=css_sheets,
                chapter_title=chapter_title,
                parent=None,
            )
            win.show()
            self._source_windows.append(win)
        self._get_active_page().toHtml(on_html)

    def _trigger_add_note(self, selected_text: str):
        self._get_active_page().runJavaScript("if (typeof window.readerBridge !== 'undefined') { window.readerBridge.getScrollPercent(); } else { 0.0; }", lambda pct: self.note_requested.emit(self.get_current_chapter_index(), float(pct or 0.0), selected_text))

    def _trigger_add_note_from_shortcut(self):
        # First get selected text, then trigger add note
        self._get_active_page().runJavaScript("window.getSelection().toString();", self._trigger_add_note)

    def _trigger_read_selection_from_shortcut(self):
        self._get_active_page().runJavaScript("window.getSelection().toString();", self.read_selection_requested.emit)

    def _trigger_add_bookmark(self):
        self._get_active_page().runJavaScript("if (typeof window.readerBridge !== 'undefined') { window.readerBridge.getScrollPercent(); } else { 0.0; }", lambda pct: self.bookmark_requested.emit(self.get_current_chapter_index(), float(pct or 0.0)))

    def navigate_to_percent(self, chapter_idx: int, pct: float, text_to_highlight: str = "") -> None:
        def _do_scroll():
            self._get_active_page().runJavaScript(f"if (typeof window.readerBridge !== 'undefined') window.readerBridge.scrollToPercent({pct});")
            if text_to_highlight:
                self.highlight_sentence(text_to_highlight)

        if chapter_idx != self._current_chapter:
            try:
                self._page.loadFinished.disconnect(self._pending_scroll)
            except Exception:
                pass
            self._pending_scroll = lambda ok: _do_scroll() if ok else None
            self._page.loadFinished.connect(self._pending_scroll)
            self.go_to_chapter(chapter_idx)
        else:
            _do_scroll()
