"""
Reader Panel — Central reading area using QWebEngineView.
Renders EPUB chapter XHTML with dark mode CSS injection, text selection,
footnote link interception, and dynamic font/spacing controls.

Link interception uses QWebEnginePage.acceptNavigationRequest() at the
C++ level — far more reliable than injected JS which can fail due to
qwebchannel.js loading issues with custom URL schemes.
"""

import re
import posixpath
from bs4 import BeautifulSoup
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QMenu,
    QMainWindow,
    QTabWidget,
    QPlainTextEdit,
    QMessageBox,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineNavigationRequest,
)

from .dark_theme import READER_DARK_CSS
from .epub_loader import EpubBook
from .pdf_book import PdfBook



class SourceViewerWindow(QMainWindow):
    """
    Window that displays the page source (rendered HTML, original EPUB HTML,
    and CSS stylesheets) in separate tabs.
    """

    def __init__(self, rendered_html: str, original_html: str,
                 css_sheets: list[tuple[str, str]], chapter_title: str,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Source — {chapter_title}")
        self.resize(900, 700)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        # Tab 1: Rendered HTML (with injected styles and bridge)
        rendered_edit = self._make_editor(rendered_html, "html")
        tabs.addTab(rendered_edit, "Rendered HTML")

        # Tab 2: Original EPUB HTML (before our injections)
        original_edit = self._make_editor(original_html, "html")
        tabs.addTab(original_edit, "Original EPUB HTML")

        # Tab 3+: CSS stylesheets from the EPUB
        if css_sheets:
            for name, css_content in css_sheets:
                css_edit = self._make_editor(css_content, "css")
                short_name = name.rsplit("/", 1)[-1] if "/" in name else name
                tabs.addTab(css_edit, f"CSS: {short_name}")
        else:
            no_css = self._make_editor("/* No CSS stylesheets found in this EPUB */", "css")
            tabs.addTab(no_css, "CSS")

    def _make_editor(self, content: str, lang: str) -> QPlainTextEdit:
        """Create a read-only code editor widget."""
        editor = QPlainTextEdit()
        editor.setPlainText(content)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0d1117;
                color: #e6e1d8;
                font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
                font-size: 13px;
                border: none;
                padding: 12px;
                selection-background-color: #c9a96e;
                selection-color: #0d1117;
            }
        """)
        return editor


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
    
    # AI Signals
    ai_explain_requested = pyqtSignal()
    ai_translate_requested = pyqtSignal()
    
    # Context menu TTS signals
    play_chapter_requested = pyqtSignal()
    stop_tts_requested = pyqtSignal()
    prev_chapter_requested = pyqtSignal()
    next_chapter_requested = pyqtSignal()
    
    # Media signals
    audio_play_requested = pyqtSignal(str)

    def __init__(self, scheme_handler, parent=None):
        super().__init__(parent)
        self._scheme_handler = scheme_handler
        self._book: EpubBook | PdfBook | None = None
        self._current_chapter = 0
        self._pdf_dark_mode = False
        self._first_load = False
        self._font_family = "Georgia"
        self._font_size = 18
        self._line_height = 1.8
        self._page_width = 750
        self._pdf_reading_mode = False
        self._last_rendered_html = ""   # Store for "View Source"
        self._last_original_html = ""   # Pre-injection EPUB HTML
        self._source_windows = []       # Keep references so they don't get GC'd
        self._scheme_handler.set_html_processor(self._process_html)
        self._setup_ui()
        
        # Register global shortcuts for actions not in the main window menu
        from PyQt6.QtGui import QAction
        from PyQt6.QtCore import Qt
        self._source_shortcut = QAction(self)
        self._source_shortcut.setShortcut("Ctrl+U")
        self._source_shortcut.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self._source_shortcut.triggered.connect(self._open_source_viewer)
        self.addAction(self._source_shortcut)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Navigation Bar ──
        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(12, 6, 12, 6)
        nav_bar.setSpacing(8)

        self._btn_toggle_lib = QPushButton("📚 Library")
        self._btn_toggle_lib.clicked.connect(self.library_toggle_requested.emit)
        nav_bar.addWidget(self._btn_toggle_lib)

        nav_bar.addSpacing(10)

        self._chapter_combo = QComboBox()
        self._chapter_combo.setMinimumWidth(250)
        self._chapter_combo.currentIndexChanged.connect(self._on_chapter_selected)
        nav_bar.addWidget(self._chapter_combo, 1)

        self._btn_prev = QPushButton("◀ Prev")
        self._btn_prev.setFixedWidth(80)
        self._btn_prev.clicked.connect(self._prev_chapter)
        nav_bar.addWidget(self._btn_prev)

        self._btn_next = QPushButton("Next ▶")
        self._btn_next.setFixedWidth(80)
        self._btn_next.clicked.connect(self._next_chapter)
        nav_bar.addWidget(self._btn_next)

        self._chapter_label = QLabel("")
        self._chapter_label.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
        nav_bar.addWidget(self._chapter_label)

        nav_bar.addStretch()

        self._btn_toggle_ai = QPushButton("✨ AI")
        self._btn_toggle_ai.clicked.connect(self.ai_toggle_requested.emit)
        nav_bar.addWidget(self._btn_toggle_ai)
        
        self._btn_focus = QPushButton("📖 Focus")
        self._btn_focus.setToolTip("Toggle both sidebars for distraction-free reading")
        self._btn_focus.clicked.connect(self.focus_toggle_requested.emit)
        nav_bar.addWidget(self._btn_focus)

        nav_widget = QWidget()
        nav_widget.setLayout(nav_bar)
        nav_widget.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        layout.addWidget(nav_widget)

        # ── Table Translation / Dante Controls ──
        self._table_nav_bar = QHBoxLayout()
        self._table_nav_bar.setContentsMargins(12, 6, 12, 6)
        self._table_nav_bar.setSpacing(15)
        
        self._track_toggles_layout = QHBoxLayout()
        self._track_toggles_layout.setSpacing(10)
        self._track_toggles_layout.setContentsMargins(0, 0, 0, 0)
        self._table_nav_bar.addLayout(self._track_toggles_layout)
        
        self._dynamic_checkboxes = {}
        
        self._btn_translate_page = QPushButton("Translate Page")
        self._btn_translate_page.clicked.connect(self._translate_visible_page)
        self._table_nav_bar.addWidget(self._btn_translate_page)
        
        self._table_nav_bar.addStretch()
        
        self._table_nav_bar.addWidget(QLabel("TTS:"))
        self._table_tts_combo = QComboBox()
        self._table_tts_combo.addItems(["Original", "Translation"])
        self._table_nav_bar.addWidget(self._table_tts_combo)
        
        self._table_controls_widget = QWidget()
        self._table_controls_widget.setLayout(self._table_nav_bar)
        self._table_controls_widget.setStyleSheet("background-color: #1c2128; border-bottom: 1px solid #30363d;")
        self._table_controls_widget.hide()
        layout.addWidget(self._table_controls_widget)

        # ── Web View ──
        from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

        self._profile = QWebEngineProfile("ReaderProfile", self)
        self._profile.installUrlSchemeHandler(b"epub", self._scheme_handler)

        self._web = QWebEngineView(self)
        self._page = QWebEnginePage(self._profile, self._web)
        self._web.setPage(self._page)
        self._web.setStyleSheet("background-color: #0d1117;")
        self._web.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._web.customContextMenuRequested.connect(self._show_context_menu)
        self._page.navigationRequested.connect(self._on_navigation_requested)
        self._page.selectionChanged.connect(self._on_selection_changed)
        self._page.loadFinished.connect(self._on_page_load_finished)

        layout.addWidget(self._web, 1)

        self._translation_manager = None

    def set_tts_target(self, target: str):
        self._tts_target = target

    def _get_table_layout_css(self) -> str:
        css_lines = []
        
        if getattr(self._book, 'is_dante', False):
            active_count = sum(1 for chk in self._dynamic_checkboxes.values() if chk.isChecked())
            width_pct = (100.0 / active_count) if active_count > 0 else 100.0
            
            for key, chk in self._dynamic_checkboxes.items():
                is_checked = chk.isChecked()
                css_lines.append(f".track-{key} {{ display: {'table-cell' if is_checked else 'none'} !important; width: {width_pct if is_checked else 0}% !important; padding: {'0 15px' if is_checked else '0'} !important; }}")
                
                # Backwards compatibility for V1 fallback classes
                if key == "text": css_lines.append(f".track-it {{ display: {'table-cell' if is_checked else 'none'} !important; width: {width_pct if is_checked else 0}% !important; padding: {'0 15px' if is_checked else '0'} !important; }}")
                if key == "ipa": css_lines.append(f".track-ipa {{ display: {'table-cell' if is_checked else 'none'} !important; width: {width_pct if is_checked else 0}% !important; padding: {'0 15px' if is_checked else '0'} !important; }}")
                if key == "longfellow": css_lines.append(f".track-en {{ display: {'table-cell' if is_checked else 'none'} !important; width: {width_pct if is_checked else 0}% !important; padding: {'0 15px' if is_checked else '0'} !important; }}")
        else:
            show_orig = self._dynamic_checkboxes.get("original", type('obj', (object,), {'isChecked': lambda: True})).isChecked()
            show_trans = self._dynamic_checkboxes.get("translation", type('obj', (object,), {'isChecked': lambda: False})).isChecked()
            css_lines.append(f".track-original {{ display: {'block' if show_orig else 'none'} !important; flex: 1; padding: {'0 15px' if show_orig else '0'} !important; }}")
            css_lines.append(f".track-translation {{ display: {'block' if show_trans else 'none'} !important; flex: 1; padding: {'0 15px' if show_trans else '0'} !important; }}")
        
        return " ".join(css_lines)

    def _update_table_layout(self):
        css_str = self._get_table_layout_css()
        js = f"""
        (function() {{
            var styleId = 'table-column-toggles';
            var styleEl = document.getElementById(styleId);
            if (!styleEl) {{
                styleEl = document.createElement('style');
                styleEl.id = styleId;
                document.head.appendChild(styleEl);
            }}
            styleEl.textContent = '{css_str}';
        }})();
        """
        self._page.runJavaScript(js)

    def _translate_visible_page(self):
        trans_chk = self._dynamic_checkboxes.get("translation")
        if trans_chk and not trans_chk.isChecked():
            trans_chk.setChecked(True)
            
        js = """
        (function() {
            var rows = document.querySelectorAll('.translation-row');
            var visibleIds = [];
            
            // Get viewport height with a 50% buffer above and below
            var buffer = window.innerHeight * 0.5;
            var topBound = -buffer;
            var bottomBound = window.innerHeight + buffer;
            
            for (var i = 0; i < rows.length; i++) {
                var rect = rows[i].getBoundingClientRect();
                // Check if row is within our buffered viewport
                if (rect.bottom > topBound && rect.top < bottomBound) {
                    var id = rows[i].getAttribute('data-trans-id');
                    if (id) {
                        visibleIds.push(id);
                    }
                }
            }
            return visibleIds;
        })();
        """
        self._page.runJavaScript(js, self._on_visible_ids_received)

    def _on_visible_ids_received(self, visible_ids):
        if not visible_ids:
            return
            
        from app.translation_parser import extract_translation_blocks
        all_blocks = extract_translation_blocks(self._last_rendered_html)
        needed_blocks = [b for b in all_blocks if b["id"] in visible_ids]
        
        if needed_blocks:
            if hasattr(self, "_btn_translate_page"):
                self._btn_translate_page.setText("⏳ Translating...")
                self._btn_translate_page.setEnabled(False)
            self.translation_requested.emit(needed_blocks)

    def _on_chapter_translated(self, index: int):
        if hasattr(self, "_btn_translate_page"):
            self._btn_translate_page.setText("🌍 Translate Page")
            self._btn_translate_page.setEnabled(True)
        if index == self._current_chapter and self._translation_manager:
            translations = self._translation_manager.get_chapter(index)
            import json
            js = f"""
            (function() {{
                var trans = {json.dumps(translations)};
                var parser = new DOMParser();
                for (var id in trans) {{
                    var el = document.querySelector('[data-trans-id="' + id + '"] .track-translation');
                    if (el) {{
                        try {{
                            el.innerHTML = trans[id];
                        }} catch (e) {{
                            var doc = parser.parseFromString(trans[id], 'text/html');
                            el.innerHTML = '';
                            Array.from(doc.body.childNodes).forEach(node => {{
                                el.appendChild(document.importNode(node, true));
                            }});
                        }}
                    }}
                }}
            }})();
            """
            self._page.runJavaScript(js)

    def _on_translation_error(self, index: int, error_msg: str):
        if hasattr(self, "_btn_translate_page"):
            self._btn_translate_page.setText("🌍 Translate Page")
            self._btn_translate_page.setEnabled(True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Translation Error", f"Failed to translate chapter {index}:\n\n{error_msg}")

    def _on_page_load_finished(self, ok: bool) -> None:
        # If it's a PDF, apply the dark mode preference instantly upon load
        if self._book and getattr(self._book, 'is_pdf', False):
            self.set_pdf_dark_mode(self._pdf_dark_mode)
            
        if self._book and not getattr(self._book, 'is_pdf', False):
            self._update_table_layout()

        if ok and getattr(self, '_first_load', False):
            # Only force this aggressive repaint once when the book is initially loaded (cover page)
            self._first_load = False
            
            QTimer.singleShot(50, self._web.update)
            js = """
            setTimeout(() => {
                window.scrollTo(0, 1); 
                window.scrollTo(0, 0);
                // Force a hardware compositor layer refresh
                if (document.body) {
                    document.body.style.transform = 'translateZ(0)';
                    setTimeout(() => document.body.style.transform = 'none', 50);
                }
            }, 50);
            """
            self._page.runJavaScript(js)

    # ── Book Loading ──

    def load_book(self, book, target_page: int = 1) -> None:
        """Load a new book and display the first chapter or the PDF."""
        self._book = book
        self._first_load = True
        self._translation_manager = None
        
        is_pdf = getattr(book, 'is_pdf', False)
        
        # If it's a PDF AND we are NOT in reading mode, hide nav and route to PDF.js
        if is_pdf and not self._pdf_reading_mode:
            self._btn_prev.hide()
            self._btn_next.hide()
            self._chapter_combo.hide()
            self._chapter_label.hide()
            
            import urllib.parse
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
            
        self._btn_prev.show()
        self._btn_next.show()
        self._chapter_combo.show()
        self._chapter_label.show()
        
        # Clear existing track toggles
        for i in reversed(range(self._track_toggles_layout.count())): 
            widget = self._track_toggles_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self._dynamic_checkboxes.clear()
        
        from PyQt6.QtWidgets import QCheckBox
        
        if getattr(book, 'is_dante', False):
            from app.config import get_max_width_px
            self._page_width = get_max_width_px()
            
            tracks = getattr(book, 'metadata', {}).get('tracks', {
                "text": {"label": "Original"},
                "ipa": {"label": "IPA Pronunciation"},
                "longfellow": {"label": "Translation"}
            })
            
            for key, val in tracks.items():
                chk = QCheckBox(val.get("label", key))
                chk.setChecked(key != "ipa")
                chk.stateChanged.connect(self._update_table_layout)
                self._track_toggles_layout.addWidget(chk)
                self._dynamic_checkboxes[key] = chk
            
            self._table_tts_combo.blockSignals(True)
            self._table_tts_combo.clear()
            for val in tracks.values():
                self._table_tts_combo.addItem(val.get("label", ""))
            if self._table_tts_combo.count() > 0:
                self._table_tts_combo.setCurrentIndex(0)
            self._table_tts_combo.blockSignals(False)
        else:
            self._chk_col_original = QCheckBox("Original")
            self._chk_col_original.setChecked(True)
            self._chk_col_original.stateChanged.connect(self._update_table_layout)
            self._track_toggles_layout.addWidget(self._chk_col_original)
            
            self._chk_col_translation = QCheckBox("Translation")
            self._chk_col_translation.setChecked(False)
            self._chk_col_translation.stateChanged.connect(self._update_table_layout)
            self._track_toggles_layout.addWidget(self._chk_col_translation)
            
            self._dynamic_checkboxes["original"] = self._chk_col_original
            self._dynamic_checkboxes["translation"] = self._chk_col_translation
            
            self._table_tts_combo.blockSignals(True)
            self._table_tts_combo.clear()
            self._table_tts_combo.addItems(["Original", "Translation"])
            self._table_tts_combo.setCurrentText("Original")
            self._table_tts_combo.blockSignals(False)
                
        self._table_controls_widget.show()
        self._update_table_layout()

        self._scheme_handler.set_book(book)

        # Build file_name → chapter index map for cross-file link resolution
        self._fname_to_chapter: dict[str, int] = {}
        if hasattr(book, 'chapters'):
            for ch in book.chapters:
                self._fname_to_chapter[ch.file_name] = ch.index
                # Also map just the basename for loose matching
                basename = ch.file_name.rsplit("/", 1)[-1]
                self._fname_to_chapter[basename] = ch.index

        # Populate chapter combo
        self._chapter_combo.blockSignals(True)
        self._chapter_combo.clear()
        toc = book.get_toc_entries()
        if toc:
            for title, idx in toc:
                self._chapter_combo.addItem(title, idx)
        else:
            if hasattr(book, 'chapters'):
                for ch in book.chapters:
                    self._chapter_combo.addItem(ch.title, ch.index)
        self._chapter_combo.blockSignals(False)

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
            QTimer.singleShot(100, self._update_table_layout)
        else:
            # For EPUBs, get_chapter returns a Chapter object with a file_name.
            # We navigate to it via the scheme handler so relative assets load.
            url = QUrl(f"epub://content/{chapter.file_name}")
            self._web.setUrl(url)

        # If we need to scroll to a specific anchor after load
        if scroll_to_anchor:
            QTimer.singleShot(300, lambda: self._scroll_to_anchor(scroll_to_anchor))

        # Update nav controls
        self._update_nav_state()
        self.chapter_changed.emit(index)

    def _scroll_to_anchor(self, anchor_id: str) -> None:
        """Scroll the web view to a specific anchor element."""
        js = f"""
        (function() {{
            var el = document.getElementById('{anchor_id}');
            if (el) {{ el.scrollIntoView({{behavior: 'smooth', block: 'start'}}); }}
        }})();
        """
        self._page.runJavaScript(js)

    def _process_html(self, html: str, file_path: str) -> str:
        """Callback from EpubSchemeHandler: injects CSS dynamically into HTML."""
        self._last_original_html = html
        
        # Strip XML declaration from the top to prevent injections/parsers from messing with it
        xml_decl = ""
        match = re.match(r'^(\s*<\?xml[^>]*\?>)', html, re.IGNORECASE)
        if match:
            xml_decl = match.group(1).strip() + "\n"
            html = html[match.end():]

        html = self._rewrite_asset_urls(html, file_path)
        
        html = self._inject_dark_css(html)
        html = self._inject_reading_style(html)
        
        # Inject the active table layout directly into the HTML so it takes effect instantly
        layout_css = f"<style id='table-column-toggles'>{self._get_table_layout_css()}</style>"
        html = self._inject_head_content(html, layout_css)
        
        html = self._inject_next_button(html)
        self._last_rendered_html = xml_decl + html
        
        # Unconditionally inject translation rows if it's not a Dante book.
        if not getattr(self._book, 'is_dante', False):
            from app.translation_parser import inject_translation_ids, inject_translated_text
            html = inject_translation_ids(html)
            
            # If we already have translations for this chapter, inject them right away
            if self._translation_manager and self._translation_manager.has_chapter(self._current_chapter):
                trans_dict = self._translation_manager.get_chapter(self._current_chapter)
                html = inject_translated_text(html, trans_dict)
                
        # Fix SVG attribute casing AFTER all BeautifulSoup manipulations have finished!
        html = re.sub(r'\bviewbox\s*=', 'viewBox=', html, flags=re.IGNORECASE)
        html = re.sub(r'\bpreserveaspectratio\s*=', 'preserveAspectRatio=', html, flags=re.IGNORECASE)
                
        self._last_rendered_html = xml_decl + html
        return self._last_rendered_html

    def _inject_head_content(self, html: str, content: str) -> str:
        """Robustly inject content into the <head> section, handling self-closing tags."""
        if re.search(r'</head>', html, re.IGNORECASE):
            return re.sub(r'</head>', f"{content}\n</head>", html, count=1, flags=re.IGNORECASE)
        elif re.search(r'<head\s*/>', html, re.IGNORECASE):
            return re.sub(r'<head\s*/>', f"<head>\n{content}\n</head>", html, count=1, flags=re.IGNORECASE)
        elif re.search(r'<body', html, re.IGNORECASE):
            return re.sub(r'(<body[^>]*>)', f"{content}\n" + r'\1', html, count=1, flags=re.IGNORECASE)
        elif re.search(r'<html[^>]*>', html, re.IGNORECASE):
            return re.sub(r'(<html[^>]*>)', r'\1' + f"\n{content}\n", html, count=1, flags=re.IGNORECASE)
        else:
            # Fallback: place at the very end to avoid disrupting XML declarations at the start
            return html + f"\n{content}"

    def _inject_next_button(self, html: str) -> str:
        """Inject a 'Next' button at the bottom of the page."""
        btn_html = """
        <div style="text-align: center; margin-top: 100px; margin-bottom: 80px;">
            <a href="epub://action/next-chapter" style="text-decoration: none; padding: 36px 72px; border-radius: 16px; background: #444444; color: #e0e0e0; cursor: pointer; font-family: sans-serif; font-size: 48px; font-weight: bold; box-shadow: 0 8px 12px rgba(0,0,0,0.3);">Next ⬇</a>
        </div>
        """
        if re.search(r'</body>', html, re.IGNORECASE):
            html = re.sub(r'</body>', f"{btn_html}\n</body>", html, count=1, flags=re.IGNORECASE)
        else:
            html = html + f"\n{btn_html}"
        return html

    def _rewrite_asset_urls(self, html: str, chapter_file: str) -> str:
        """Rewrite relative asset URLs to use the epub:// scheme."""
        chapter_dir = posixpath.dirname(chapter_file)

        def replace_url(match):
            attr = match.group(1)
            url = match.group(2)
            quote = match.group(3)

            # Skip absolute URLs, data URIs, and anchors
            if url.startswith(("http://", "https://", "data:", "#", "epub://")):
                return match.group(0)

            # Resolve relative path
            if chapter_dir:
                resolved = posixpath.normpath(posixpath.join(chapter_dir, url))
            else:
                resolved = url

            return f'{attr}="epub://content/{resolved}{quote}'

        # Match src="...", href="..." (for CSS links), url(...)
        html = re.sub(
            r'(src|href)\s*=\s*"([^"]*?)(")',
            replace_url,
            html,
            flags=re.IGNORECASE,
        )
        html = re.sub(
            r"(src|href)\s*=\s*'([^']*?)(')",
            replace_url,
            html,
            flags=re.IGNORECASE,
        )

        return html

    def _inject_dark_css(self, html: str) -> str:
        """Inject dark mode CSS into the chapter HTML."""
        dark_style = f"<style id='dark-reader-css'>\n{READER_DARK_CSS}\n</style>"
        return self._inject_head_content(html, dark_style)

    def _inject_reading_style(self, html: str) -> str:
        """Inject user-configurable reading styles (font, size, spacing)."""
        width_css = f"max-width: {self._page_width}px !important;" if self._page_width > 0 else "max-width: 100% !important;"
        style = f"""
        <style id='reader-prefs-css'>
            body {{
                font-family: "{self._font_family}", Georgia, "Times New Roman", serif !important;
                font-size: {self._font_size}px !important;
                line-height: {self._line_height} !important;
                {width_css}
                margin: 0 auto !important;
                padding: 30px 40px !important;
            }}
            p, div, span, li, td, th {{
                font-size: inherit !important;
                line-height: inherit !important;
            }}
        </style>
        """
        return self._inject_head_content(html, style)

    def _update_nav_state(self) -> None:
        """Update navigation buttons and label."""
        if not self._book:
            return

        count = self._book.get_chapter_count()
        self._btn_prev.setEnabled(self._current_chapter > 0)
        self._btn_next.setEnabled(self._current_chapter < count - 1)
        self._chapter_label.setText(
            f"  {self._current_chapter + 1} / {count}"
        )

        # Sync combo box
        self._chapter_combo.blockSignals(True)
        for i in range(self._chapter_combo.count()):
            if self._chapter_combo.itemData(i) == self._current_chapter:
                self._chapter_combo.setCurrentIndex(i)
                break
        self._chapter_combo.blockSignals(False)

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
            request.reject()
            if path == "next-chapter":
                QTimer.singleShot(0, self._next_chapter)
            elif path == "media":
                from PyQt6.QtCore import QUrlQuery
                query = QUrlQuery(url.query())
                media_type = query.queryItemValue("type")
                media_id = query.queryItemValue("id")
                
                if media_type == "audio":
                    QTimer.singleShot(0, lambda: self._handle_audio_click(media_id))
                elif media_type == "video":
                    QTimer.singleShot(0, lambda: self._handle_video_click(media_id))
                elif media_type == "foot":
                    QTimer.singleShot(0, lambda: self._handle_footnote_click(media_id))
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
                import webbrowser
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
                return

        except Exception as e:
            print(f"[reader] Error in navigation handler: {e!r}", flush=True)

    def _handle_audio_click(self, media_id: str) -> None:
        self.audio_play_requested.emit(media_id)

    def _handle_video_click(self, media_id: str) -> None:
        if not self._book or not hasattr(self._book, 'videos'):
            return
        video_data = self._book.videos.get(media_id)
        if not video_data:
            return
        import webbrowser
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
        footnote_text = self._book.footnotes.get(media_id)
        if not footnote_text:
            return
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Footnote", footnote_text)



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
        
        def _emit_cleaned(text: str):
            if not text:
                return
            # Remove multiple empty lines caused by table DOM gaps
            cleaned = "\n".join([line for line in text.splitlines() if line.strip()])
            if cleaned:
                self.text_selected.emit(cleaned)
                
        # Constrain selection to a single column in table/grid mode
        js = """
        (function() {
            var sel = window.getSelection();
            if (!sel || sel.rangeCount === 0) return '';
            
            var anchor = sel.anchorNode;
            if (!anchor) return window.getSelection().toString();
            var cell = anchor.nodeType === 3 ? anchor.parentElement.closest('[class*="track-"]') : anchor.closest('[class*="track-"]');
            if (!cell) return window.getSelection().toString();
            
            var className = Array.from(cell.classList).find(c => c.startsWith('track-'));
            if (!className) return window.getSelection().toString();
            
            var range = sel.getRangeAt(0);
            var fragment = range.cloneContents();
            
            var tempDiv = document.createElement('div');
            tempDiv.appendChild(fragment);
            
            var badCells = tempDiv.querySelectorAll('[class*="track-"]');
            badCells.forEach(node => {
                if (!node.classList.contains(className)) {
                    node.remove();
                }
            });
            
            return tempDiv.innerText.trim();
        })();
        """
        self._page.runJavaScript(js, _emit_cleaned)

    # ── Navigation ──

    def _prev_chapter(self) -> None:
        if self._current_chapter > 0:
            self._load_chapter(self._current_chapter - 1)

    def _next_chapter(self) -> None:
        if self._book and self._current_chapter < self._book.get_chapter_count() - 1:
            self._load_chapter(self._current_chapter + 1)

    def _on_chapter_selected(self, combo_index: int) -> None:
        chapter_index = self._chapter_combo.itemData(combo_index)
        if chapter_index is not None and chapter_index != self._current_chapter:
            self._load_chapter(chapter_index)

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

    def set_pdf_dark_mode(self, enabled: bool) -> None:
        self._pdf_dark_mode = enabled
        if self._book and getattr(self._book, 'is_pdf', False):
            # Tell PDF.js viewer to toggle the dark-mode class on the body
            js = f"document.body.classList.toggle('dark-mode', {'true' if enabled else 'false'});"
            self._page.runJavaScript(js)

    def reset_pdf_settings(self) -> None:
        if self._book and getattr(self._book, 'is_pdf', False):
            js = """
            localStorage.removeItem('pdfjs.preferences');
            localStorage.removeItem('pdfjs.history');
            try {
                PDFViewerApplicationOptions.set('defaultZoomValue', 'page-fit');
                PDFViewerApplicationOptions.set('spreadModeOnLoad', 0);
            } catch (e) {}
            // Prevent PDF.js from rewriting history during the unload event triggered by reload
            localStorage.setItem = function() {};
            location.reload();
            """
            self._page.runJavaScript(js)

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

    def set_tts_target(self, target: str) -> None:
        self._tts_target = target

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
            
        target_selector = ""
        target = self._table_tts_combo.currentText()
        if target == "Original":
            target_selector = ".track-original, .track-it"
        elif target == "Translation":
            target_selector = ".track-translation, .track-en"
        elif target == "IPA Pronunciation":
            target_selector = ".track-ipa"
        
        # JS to get text from selection/cursor to the end of the chapter.
        # If in Dante mode, it restricts extraction to the selected `target_selector`.
        js = f"""
        (function() {{
            var sel = window.getSelection();
            var targetClass = '{target_selector}';
            if (targetClass && document.querySelectorAll(targetClass).length === 0) {{
                targetClass = '';
            }}
            
            // Function to extract text from a specific target across all rows
            function extractDanteText(fromNode) {{
                var cells = Array.from(document.querySelectorAll(targetClass));
                var startIndex = 0;
                if (fromNode) {{
                    var closestCell = fromNode.nodeType === 3 ? fromNode.parentElement.closest('td, .track-original, .track-translation, .track-ipa') : fromNode.closest('td, .track-original, .track-translation, .track-ipa');
                    if (closestCell) {{
                        var tr = closestCell.closest('tr, .translation-row');
                        if (tr) {{
                            var targetCell = tr.querySelector(targetClass);
                            startIndex = cells.indexOf(targetCell);
                        }}
                        if (startIndex === -1) startIndex = 0;
                    }}
                }}
                
                var texts = [];
                for (var i = startIndex; i < cells.length; i++) {{
                    if (cells[i].innerText.trim()) {{
                        texts.push(cells[i].innerText.trim());
                    }}
                }}
                return texts.join('\\n');
            }}
            
            if (sel && sel.rangeCount > 0 && sel.anchorNode) {{
                // If there's a selection or cursor
                if (targetClass) {{
                    return extractDanteText(sel.anchorNode);
                }} else {{
                    var range = sel.getRangeAt(0).cloneRange();
                    var endRange = document.createRange();
                    endRange.selectNodeContents(document.body);
                    range.setEnd(endRange.endContainer, endRange.endOffset);
                    
                    var fragment = range.cloneContents();
                    var div = document.createElement('div');
                    div.appendChild(fragment);
                    document.body.appendChild(div);
                    div.style.display = 'none';
                    var text = div.innerText;
                    document.body.removeChild(div);
                    
                    if (text.trim().length > 0) {{
                        return text;
                    }}
                }}
            }}
            
            // Fallback: whole document or whole Dante column
            if (targetClass) {{
                return extractDanteText(null);
            }} else {{
                return document.body.innerText;
            }}
        }})()
        """
        self._get_active_page().runJavaScript(js, callback)

    def get_current_chapter_index(self) -> int:
        return self._current_chapter

    def highlight_sentence(self, text: str) -> None:
        """Find and highlight the given sentence in the DOM while clearing previous highlights."""
        import json
        safe_text = json.dumps(text) if text else "''"
        
        js = f"""
        (function() {{
            // Clear previous hiliteColor spans
            var spans = document.querySelectorAll('span[style*="background-color: rgba(201, 169, 110, 0.4)"]');
            spans.forEach(el => {{
                el.style.backgroundColor = 'transparent';
            }});
            
            if ({safe_text} === '') return;
            
            var sel = window.getSelection();
            var originalRange = null;
            if (sel.rangeCount > 0) {{
                originalRange = sel.getRangeAt(0).cloneRange();
            }}
            
            sel.removeAllRanges();
            
            // Search from top
            // 1. Exact Match
            var found = window.find({safe_text}, false, false, true, false, false, false);
            
            // 2. Normalized spaces
            if (!found) {{
                var normText = {safe_text}.replace(/\\s+/g, ' ').trim();
                found = window.find(normText, false, false, true, false, false, false);
            }}
            
            if (found) {{
                document.designMode = 'on';
                document.execCommand('hiliteColor', false, 'rgba(201, 169, 110, 0.4)');
                document.designMode = 'off';
                
                // Scroll into view only if out of bounds, placing it near the top
                var sel = window.getSelection();
                if (sel.rangeCount > 0) {{
                    var range = sel.getRangeAt(0);
                    var rect = range.getBoundingClientRect();
                    var viewHeight = window.innerHeight || document.documentElement.clientHeight;
                    
                    var isVisible = rect.top >= 0 && (rect.bottom <= viewHeight || rect.height > viewHeight);
                    if (!isVisible) {{
                        window.scrollBy({{top: rect.top - 20, behavior: 'smooth'}});
                    }}
                }}
                // Collapse selection to the START of the sentence.
                // This ensures if the user hits "Play" again, it restarts from here 
                // instead of jumping to the end of the chapter.
                sel.collapseToStart();
            }}
        }})()
        """
        self._get_active_page().runJavaScript(js)

    # ── Context Menu ──

    def _show_context_menu(self, pos) -> None:
        """Show custom right-click context menu with View Source option."""
        menu = QMenu(self)

        # Keep standard actions: Copy, Select All
        page = self._web.page()
        copy_action = page.action(QWebEnginePage.WebAction.Copy)
        copy_action.setShortcut("Ctrl+C")
        select_all_action = page.action(QWebEnginePage.WebAction.SelectAll)
        select_all_action.setShortcut("Ctrl+A")
        menu.addAction(copy_action)
        menu.addAction(select_all_action)
        menu.addSeparator()

        # Custom: View Page Source
        source_action = QAction("🔍 View Page Source", self)
        source_action.setShortcut("Ctrl+U")
        source_action.triggered.connect(self._open_source_viewer)
        menu.addAction(source_action)

        # Custom: Read Selection (if text is selected)
        selected_text = self._page.selectedText().strip()
        if selected_text:
            menu.addSeparator()
            
            read_sel_action = QAction("🗣 Read Selected Text", self)
            read_sel_action.setShortcut("Ctrl+Shift+S")
            read_sel_action.triggered.connect(lambda: self.read_selection_requested.emit(selected_text))
            menu.addAction(read_sel_action)
            
            explain_action = QAction("💡 AI Explain", self)
            explain_action.setShortcut("Ctrl+E")
            explain_action.triggered.connect(self.ai_explain_requested.emit)
            menu.addAction(explain_action)
            
            translate_action = QAction("🌍 AI Translate", self)
            translate_action.setShortcut("Ctrl+T")
            translate_action.triggered.connect(self.ai_translate_requested.emit)
            menu.addAction(translate_action)
            
        menu.addSeparator()
        play_action = QAction("▶ Play from Cursor / Play Chapter", self)
        play_action.setShortcut("F5")
        play_action.triggered.connect(self.play_chapter_requested.emit)
        menu.addAction(play_action)
        
        stop_action = QAction("⏹ Stop TTS", self)
        stop_action.setShortcut("F7")
        stop_action.triggered.connect(self.stop_tts_requested.emit)
        menu.addAction(stop_action)
        
        menu.addSeparator()
        prev_action = QAction("◀ Previous Page", self)
        prev_action.setShortcut("Left")
        prev_action.triggered.connect(self.prev_chapter_requested.emit)
        menu.addAction(prev_action)
        
        next_action = QAction("Next Page ▶", self)
        next_action.setShortcut("Right")
        next_action.triggered.connect(self.next_chapter_requested.emit)
        menu.addAction(next_action)

        menu.exec(self._web.mapToGlobal(pos))

    def _open_source_viewer(self) -> None:
        """Open a new window showing the current chapter's source and CSS."""
        if not self._book:
            return

        def on_html(rend_html: str):
            chapter = self._book.get_chapter(self._current_chapter)
            chapter_title = f"Chapter {self._current_chapter}"
            orig_html = self._last_original_html
            css_sheets = []

            if getattr(self._book, 'is_pdf', False):
                chapter_title = f"Page {self._current_chapter + 1}"
                if getattr(self._book, '_reading_mode', False):
                    if isinstance(chapter, str):
                        orig_html = chapter
                else:
                    orig_html = "<!-- PDF.js Native Viewer -->"
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
