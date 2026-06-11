"""
Reader Window — Main application window assembling all panels.
Three-column layout: Library | Reader | Footnote/AI sidebar.
Includes menus for View, TTS, and AI controls.
"""

from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QAction, QActionGroup
from PyQt6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QMenuBar,
    QStatusBar,
    QSlider,
    QWidgetAction,
    QLabel,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
)

from .library_panel import LibraryPanel
from .reader_panel import ReaderPanel
from .ai_panel import AiPanel
from .omnivoice_engine import OmniVoiceTTSEngine
from .epub_loader import EpubBook
from .url_scheme_handler import EpubSchemeHandler
from .dictionary import DictionaryEngine
from .config import load_api_key, load_prefs, save_prefs


class BookLoaderThread(QThread):
    finished_loading = pyqtSignal(object, str)  # book_obj, path
    error = pyqtSignal(str)

    def __init__(self, path: str, is_dante: bool, use_pymupdf: bool, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_dante = is_dante
        self.use_pymupdf = use_pymupdf

    def run(self):
        try:
            if self.is_dante:
                from app.dante_book import DanteBook
                book = DanteBook(self.path)
            elif self.use_pymupdf:
                from app.pdf_book import PdfBook
                book = PdfBook(self.path)
            else:
                from app.epub_loader import EpubBook
                book = EpubBook(self.path)
            self.finished_loading.emit(book, self.path)
        except Exception as e:
            self.error.emit(str(e))

class DictionaryLLMWorker(QThread):
    finished_definition = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, backend, model_name: str, word: str, source_lang: str, target_lang: str, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.model_name = model_name
        self.word = word
        self.source_lang = source_lang
        self.target_lang = target_lang

    def run(self):
        # Incorporate the source language into the prompt if known
        lang_context = f"{self.source_lang} " if self.source_lang else ""
        prompt = f"Define the {lang_context}word '{self.word}' concisely in {self.target_lang} in one short sentence. Only output the definition, nothing else."
        try:
            result = self.backend.generate(prompt, self.model_name)
            self.finished_definition.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class LanguageDetectorWorker(QThread):
    finished_lang = pyqtSignal(str)
    
    def __init__(self, backend, model_name: str, text_sample: str, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.model_name = model_name
        self.text_sample = text_sample

    def run(self):
        prompt = (
            f"What language is the following text written in? "
            f"Reply ONLY with the language name (e.g. 'English', 'Italian', 'French'). "
            f"Do not write a full sentence. Just the language name.\n\n"
            f"Text:\n{self.text_sample[:1000]}"
        )
        try:
            result = self.backend.generate(prompt, self.model_name).strip()
            # Clean up potential LLM chattiness
            result = result.replace("The text is written in", "").replace("The language is", "").strip(" .\n\"'")
            if result:
                self.finished_lang.emit(result)
        except Exception:
            pass # Silent failure for background detection
class ReaderWindow(QMainWindow):
    """Main application window for the EPUB Reader."""

    def __init__(self):
        super().__init__()
        self._prefs = load_prefs()
        self._current_book: EpubBook | None = None
        self._tts = OmniVoiceTTSEngine(self)
        
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.playbackStateChanged.connect(self._on_media_playback_state_changed)
        self._current_media_id = None

        self.setWindowTitle("📖 Dante EPUB Reader")
        self.setMinimumSize(1000, 600)
        self.resize(
            self._prefs.get("window_width", 1400),
            self._prefs.get("window_height", 900),
        )

        # ── Setup Dictionary ──
        self._dictionary = DictionaryEngine()

        self._setup_panels()
        self._setup_menus()
        self._setup_statusbar()
        self._connect_signals()
        self._apply_prefs()

        # Restore last book
        last = self._prefs.get("last_book")
        if last:
            import os
            if os.path.isfile(last):
                self._open_book(last)

    def _setup_panels(self) -> None:
        """Create and arrange the three-column layout."""
        # ── Scheme Handler (must be shared between reader panel and window) ──
        self._scheme_handler = EpubSchemeHandler(self)

        # ── Panels ──
        from .footnotes_panel import FootnotesPanel
        self._library = LibraryPanel(self)
        self._reader = ReaderPanel(self._scheme_handler, self)
        self._ai = AiPanel(api_key=load_api_key(), parent=self)
        self._footnotes_panel = FootnotesPanel(self)

        # ── Right Sidebar (AI Companion) ──
        self._right_tabs = QTabWidget()
        self._right_tabs.addTab(self._ai, "🤖 AI Companion")
        self._right_tabs.addTab(self._footnotes_panel, "📝 Footnotes")
        self._right_tabs.setMinimumWidth(320)
        
        # Add a right-aligned close button to the tab bar
        corner_widget = QWidget(self)
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 8, 0)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 18px; border: none; background: transparent; color: #8b949e; padding: 0px; margin: 0px; } QPushButton:hover { background: #30363d; border-radius: 4px; color: #e6e1d8; }")
        close_btn.clicked.connect(self._toggle_sidebar)
        
        corner_layout.addWidget(close_btn)
        self._right_tabs.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

        # ── Main Splitter ──
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.addWidget(self._library)
        self._splitter.addWidget(self._reader)
        self._splitter.addWidget(self._right_tabs)

        # Set proportional sizes
        self._splitter.setSizes([200, 680, 520])
        self._splitter.setStretchFactor(0, 0)  # Library: fixed-ish
        self._splitter.setStretchFactor(1, 1)  # Reader: stretches
        self._splitter.setStretchFactor(2, 0)  # Sidebar: fixed-ish

        self.setCentralWidget(self._splitter)

        # ── Loading Overlay ──
        self._loading_overlay = QLabel("Loading Book...", self)
        self._loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 180); color: white; font-size: 24px; border-radius: 10px; padding: 20px;")
        self._loading_overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay:
            self._loading_overlay.resize(self.width(), self.height())

    def _setup_menus(self) -> None:
        """Build the menu bar."""
        menubar = self.menuBar()

        # ═══ View Menu ═══
        view_menu = menubar.addMenu("View")

        # Font Family submenu
        font_menu = view_menu.addMenu("Font Family")
        font_group = QActionGroup(self)
        current_font = self._prefs.get("font_family", "Georgia")
        for family in ["Georgia", "Times New Roman", "Palatino Linotype",
                        "Garamond", "Baskerville", "Segoe UI", "Inter",
                        "Courier New"]:
            action = QAction(family, self)
            action.setCheckable(True)
            action.setChecked(family == current_font)
            action.triggered.connect(lambda checked, f=family: self._set_font(f))
            font_group.addAction(action)
            font_menu.addAction(action)

        # Font Size submenu
        size_menu = view_menu.addMenu("Font Size")
        size_group = QActionGroup(self)
        current_size = self._prefs.get("font_size", 18)
        for size in [12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 40, 48, 56, 64, 72, 80, 96, 112, 128]:
            action = QAction(f"{size}px", self)
            action.setCheckable(True)
            action.setChecked(size == current_size)
            action.triggered.connect(lambda checked, s=size: self._set_font_size(s))
            size_group.addAction(action)
            size_menu.addAction(action)

        # Line Spacing submenu
        spacing_menu = view_menu.addMenu("Line Spacing")
        spacing_group = QActionGroup(self)
        current_lh = self._prefs.get("line_height", 1.8)
        for lh, label in [(1.2, "Tight"), (1.5, "Normal"), (1.8, "Comfortable"),
                           (2.0, "Relaxed"), (2.4, "Airy")]:
            action = QAction(f"{label} ({lh})", self)
            action.setCheckable(True)
            action.setChecked(abs(lh - current_lh) < 0.05)
            action.triggered.connect(lambda checked, h=lh: self._set_line_height(h))
            spacing_group.addAction(action)
            spacing_menu.addAction(action)

        # Page Width submenu
        width_menu = view_menu.addMenu("Page Width (Words per line)")
        width_group = QActionGroup(self)
        current_width = self._prefs.get("page_width", 750)
        for width, label in [(600, "Narrow (~60 chars)"), (750, "Medium (~75 chars)"), 
                             (900, "Wide (~90 chars)"), (1100, "Extra Wide"), (0, "Full Width")]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(width == current_width)
            action.triggered.connect(lambda checked, w=width: self._set_page_width(w))
            width_group.addAction(action)
            width_menu.addAction(action)

        view_menu.addSeparator()

        self._pdf_reading_mode_action = QAction("PDF Reading Mode (Extract Text)", self)
        self._pdf_reading_mode_action.setCheckable(True)
        self._pdf_reading_mode_action.setChecked(self._prefs.get("pdf_reading_mode", False))
        self._pdf_reading_mode_action.triggered.connect(self._toggle_pdf_reading_mode)
        view_menu.addAction(self._pdf_reading_mode_action)

        self._pdf_dark_action = QAction("PDF Dark Mode", self)
        self._pdf_dark_action.setCheckable(True)
        self._pdf_dark_action.setChecked(self._prefs.get("pdf_dark_mode", False))
        self._pdf_dark_action.triggered.connect(self._toggle_pdf_dark_mode)
        view_menu.addAction(self._pdf_dark_action)
        
        self._epub_md_action = QAction("EPUB Markdown Extraction Mode", self)
        self._epub_md_action.setCheckable(True)
        self._epub_md_action.setChecked(self._prefs.get("epub_markdown_mode", False))
        self._epub_md_action.triggered.connect(self._toggle_epub_md_mode)
        view_menu.addAction(self._epub_md_action)

        self._pdf_reset_action = QAction("Reset PDF Settings", self)
        self._pdf_reset_action.triggered.connect(self._reset_pdf_settings)
        view_menu.addAction(self._pdf_reset_action)

        view_menu.addSeparator()

        # (Parallel Reading Mode removed in favor of inline columns)

        # Translation Language
        lang_menu = view_menu.addMenu("Translation Language")
        lang_group = QActionGroup(self)
        current_lang = self._prefs.get("translation_lang", "Modern English")
        for lang in ["Modern English", "Spanish", "German", "French", "Italian", "Simplified Chinese", "Japanese"]:
            action = QAction(lang, self)
            action.setCheckable(True)
            action.setChecked(lang == current_lang)
            action.triggered.connect(lambda checked, l=lang: self._set_translation_lang(l))
            lang_group.addAction(action)
            lang_menu.addAction(action)

        view_menu.addSeparator()

        # Toggle panels
        toggle_library = QAction("Toggle Library Panel", self)
        toggle_library.setShortcut("Ctrl+L")
        toggle_library.triggered.connect(self._toggle_library)
        view_menu.addAction(toggle_library)

        toggle_sidebar = QAction("Toggle Sidebar", self)
        toggle_sidebar.setShortcut("Ctrl+B")
        toggle_sidebar.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(toggle_sidebar)

        # ═══ TTS Menu ═══
        tts_menu = menubar.addMenu("TTS")

        play_action = QAction("▶ Play from Cursor / Play Chapter", self)
        play_action.setShortcut("F5")
        play_action.triggered.connect(self._tts_play)
        tts_menu.addAction(play_action)

        stop_action = QAction("⏹ Stop", self)
        stop_action.setShortcut("F7")
        stop_action.triggered.connect(self._tts_stop)
        tts_menu.addAction(stop_action)

        tts_menu.addSeparator()

        # (TTS Target Source removed: TTS now reads from selected column)

        tts_menu.addSeparator()

        voice_action = QAction("Change Voice...", self)
        read_sel_action = QAction("🗣 Read Selected Text", self)
        read_sel_action.setShortcut("Ctrl+Shift+S")
        read_sel_action.triggered.connect(self._tts_read_selection)
        tts_menu.addAction(read_sel_action)

        tts_menu.addSeparator()

        self._skip_fn_action = QAction("Skip Footnotes [N]", self)
        self._skip_fn_action.setCheckable(True)
        self._skip_fn_action.setChecked(self._prefs.get("tts_skip_footnotes", True))
        self._skip_fn_action.triggered.connect(self._toggle_skip_footnotes)
        tts_menu.addAction(self._skip_fn_action)

        # TTS Speaker submenu
        speaker_menu = tts_menu.addMenu("Voice Selection")
        speaker_group = QActionGroup(self)
        current_voice = self._prefs.get("tts_voice", "jiang_voice")
        
        self._auto_next_action = QAction("Auto-Continue Next Chapter", self)
        self._auto_next_action.setCheckable(True)
        self._auto_next_action.setChecked(self._prefs.get("tts_auto_next", False))
        self._auto_next_action.triggered.connect(self._toggle_auto_next)
        tts_menu.addAction(self._auto_next_action)
        tts_menu.addSeparator()
        
        # Add language hints for known voices
        voice_hints = {
            "aiden": " (EN)", "ryan": " (EN)", "aria": " (EN)", "sarah": " (EN)",
            "cora": " (EN)", "lucas": " (EN)", "nova": " (EN)", "oliver": " (EN)",
            "jiang_voice": " (EN)"
        }
        for voice in self._tts.get_available_voices():
            v_id = voice["id"]
            hint = voice_hints.get(v_id, "")
            action = QAction(f"{voice['name']}{hint}", self)
            action.setCheckable(True)
            action.setChecked(v_id == current_voice)
            action.triggered.connect(lambda checked, v=v_id: self._set_tts_voice(v))
            speaker_group.addAction(action)
            speaker_menu.addAction(action)

        # ═══ AI Menu ═══
        ai_menu = menubar.addMenu("AI")

        explain_action = QAction("💡 Explain Selection", self)
        explain_action.setShortcut("Ctrl+E")
        explain_action.triggered.connect(lambda: self._ai._explain())
        ai_menu.addAction(explain_action)

        translate_action = QAction("🌍 Translate Selection", self)
        translate_action.setShortcut("Ctrl+T")
        translate_action.triggered.connect(lambda: self._ai._translate())
        ai_menu.addAction(translate_action)

        research_action = QAction("🔍 Research Selection", self)
        research_action.setShortcut("Ctrl+R")
        research_action.triggered.connect(lambda: self._ai._research())
        ai_menu.addAction(research_action)

    def _setup_statusbar(self) -> None:
        """Create the status bar."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — Double-click a book to start reading")

    def _connect_signals(self) -> None:
        """Wire up all inter-panel signals."""
        # Library → open book
        self._library.book_selected.connect(self._open_book)
        self._library.close_requested.connect(self._toggle_library)

        # Reader → Window (save progress)
        self._reader.chapter_changed.connect(self._on_chapter_changed)
        self._reader.translation_requested.connect(self._on_translation_requested)

        # Reader → AI panel (text selection)
        self._reader.text_selected.connect(self._on_text_selected)
        self._reader.ai_explain_requested.connect(self._ai._explain)
        self._reader.ai_translate_requested.connect(self._ai._translate)
        
        # Connect Context Menu TTS actions
        self._reader.play_chapter_requested.connect(self._tts_play)
        self._reader.stop_tts_requested.connect(self._tts_stop)
        self._reader.prev_chapter_requested.connect(lambda: self._reader._prev_chapter())
        self._reader.next_chapter_requested.connect(lambda: self._reader._next_chapter())
        self._reader.audio_play_requested.connect(self._play_media_audio)
        self._reader.footnote_requested.connect(self._on_footnote_requested)
        self._reader.dictionary_lookup_requested.connect(self._on_dictionary_lookup_requested)

        # Keyboard shortcuts for Navigation
        from PyQt6.QtGui import QKeySequence
        from PyQt6.QtCore import Qt
        
        prev_shortcut = QAction(self)
        prev_shortcut.setShortcut(QKeySequence(Qt.Key.Key_Left))
        prev_shortcut.triggered.connect(lambda: self._reader._prev_chapter())
        self.addAction(prev_shortcut)
        
        next_shortcut = QAction(self)
        next_shortcut.setShortcut(QKeySequence(Qt.Key.Key_Right))
        next_shortcut.triggered.connect(lambda: self._reader._next_chapter())
        self.addAction(next_shortcut)
        
        translate_page_shortcut = QAction(self)
        translate_page_shortcut.setShortcut("Ctrl+Shift+T")
        translate_page_shortcut.triggered.connect(lambda: self._reader._translate_visible_page())
        self.addAction(translate_page_shortcut)
        
        # Reader → TTS (read selection)
        self._reader.read_selection_requested.connect(self._tts_read_selection)

        # Reader → Window toggle
        self._reader.library_toggle_requested.connect(self._toggle_library)
        self._reader.ai_toggle_requested.connect(self._toggle_sidebar)
        self._reader.focus_toggle_requested.connect(self._toggle_focus_mode)

        # AI panel
        self._ai.close_requested.connect(self._toggle_sidebar)

        # TTS signals
        self._tts.playback_finished.connect(self._on_playback_finished)
        self._tts.sentence_started.connect(
            lambda idx, text: self._reader.highlight_sentence(text)
        )
        self._tts.error.connect(
            lambda e: self._statusbar.showMessage(f"TTS Error: {e}")
        )

    def _apply_prefs(self) -> None:
        """Apply saved preferences to the reader."""
        self._reader.set_font_family(self._prefs.get("font_family", "Georgia"))
        self._reader.set_font_size(self._prefs.get("font_size", 18))
        self._reader.set_line_height(self._prefs.get("line_height", 1.8))
        self._reader.set_page_width(self._prefs.get("page_width", 750))
        if hasattr(self._reader, "set_pdf_reading_mode"):
            self._reader.set_pdf_reading_mode(self._prefs.get("pdf_reading_mode", False))
        if hasattr(self._reader, "set_pdf_dark_mode"):
            self._reader.set_pdf_dark_mode(self._prefs.get("pdf_dark_mode", False))
            
        # Note: OmniVoiceTTSEngine does not use rate, it uses speaker
        self._tts.set_voice(self._prefs.get("tts_voice", "jiang_voice"))
        self._tts.set_skip_footnotes(self._prefs.get("tts_skip_footnotes", True))

    # ═══════════════════════════════════
    # Book Loading
    # ═══════════════════════════════════

    def _open_book(self, path: str) -> None:
        """Load and display an EPUB book asynchronously."""
        try:
            self._statusbar.showMessage(f"Loading: {path}...")
            
            use_pymupdf = path.lower().endswith(".pdf")
            if path.lower().endswith(".epub") and self._prefs.get("epub_markdown_mode", False):
                use_pymupdf = True
                
            is_dante = path.lower().endswith((".dante", ".zip"))
                
            self._loading_overlay.resize(self.width(), self.height())
            self._loading_overlay.show()
            self._loading_overlay.raise_()
            
            self._loader_thread = BookLoaderThread(path, is_dante, use_pymupdf, self)
            self._loader_thread.finished_loading.connect(self._on_book_loaded)
            self._loader_thread.error.connect(self._on_book_load_error)
            self._loader_thread.start()

        except Exception as e:
            self._on_book_load_error(str(e))

    def _on_book_load_error(self, error_msg: str) -> None:
        self._loading_overlay.hide()
        self._statusbar.showMessage(f"Error loading book: {error_msg}")
        QMessageBox.warning(self, "Load Error", f"Could not load book:\n{error_msg}")

    def _on_book_loaded(self, book_obj, path: str) -> None:
        self._loading_overlay.hide()
        self._current_book = book_obj
        
        # If it's an EPUB opened in Markdown mode, force it into Reading Mode 
        if path.lower().endswith(".epub") and getattr(self._current_book, 'is_pdf', False):
            self._current_book.set_reading_mode(True)
            self._reader._pdf_reading_mode = True
            
        # ── Language Detection ──
        if not getattr(self._current_book, "language", ""):
            cached_langs = self._prefs.setdefault("book_languages", {})
            if path in cached_langs:
                self._current_book.language = cached_langs[path]
            else:
                backend_name = self._ai._backend_combo.currentText()
                model_name = self._ai._model_combo.currentText()
                backend = self._ai._backends.get(backend_name)
                
                if backend and model_name and self._current_book.get_chapter_count() > 0:
                    text_sample = ""
                    try:
                        first_chap = self._current_book.get_chapter(0)
                        if hasattr(first_chap, "get_html"):
                            text_sample = first_chap.get_html()
                        elif isinstance(first_chap, str):
                            text_sample = first_chap
                    except Exception:
                        pass
                        
                    if len(text_sample) > 50:
                        self._lang_worker = LanguageDetectorWorker(backend, model_name, text_sample, self)
                        self._lang_worker.finished_lang.connect(lambda lang, p=path: self._on_language_detected(p, lang))
                        self._lang_worker.start()
            
        progress = self._prefs.get("book_progress", {}).get(path, {})
        saved_chapter = progress.get("chapter", 0)
        
        self._reader.load_book(self._current_book)
        if saved_chapter > 0 and saved_chapter < self._current_book.get_chapter_count():
            self._reader._load_chapter(saved_chapter)
            
        self.setWindowTitle(f"📖 {self._current_book.title}")
        self._ai.set_book_context(self._current_book.title)
        self._statusbar.showMessage(
            f"Loaded: {self._current_book.title} "
            f"({self._current_book.get_chapter_count()} chapters)"
        )

        # Save as last book
        self._prefs["last_book"] = path
        save_prefs(self._prefs)
        
        if hasattr(self._current_book, 'footnotes'):
            self._footnotes_panel.load_footnotes(self._current_book.footnotes)
        else:
            self._footnotes_panel.load_footnotes({})

    def _on_language_detected(self, path: str, lang: str) -> None:
        if self._current_book and getattr(self._current_book, "path", "") == path:
            self._current_book.language = lang
        self._prefs.setdefault("book_languages", {})[path] = lang
        save_prefs(self._prefs)
        self._statusbar.showMessage(f"Detected book language: {lang}", 4000)

    def _on_footnote_requested(self, foot_id: str) -> None:
        target = 320
        current = self._right_tabs.width() if self._right_tabs.isVisible() else 0
        if not self._right_tabs.isVisible() or self._right_tabs.maximumWidth() == 0:
            self._animate_widget_width(self._right_tabs, current, target)
        self._right_tabs.setCurrentWidget(self._footnotes_panel)
        self._footnotes_panel.scroll_to_footnote(foot_id)

    def _on_dictionary_lookup_requested(self, word: str) -> None:
        """Handle double-click word lookup requests."""
        target_lang = self._prefs.get("translation_lang", "Modern English")
        source_lang = getattr(self._current_book, "language", "")
        
        definition = self._dictionary.lookup(word, source_lang, target_lang)
        from PyQt6.QtWidgets import QToolTip
        from PyQt6.QtGui import QCursor
        
        pos = QCursor.pos()
        
        if definition:
            QToolTip.showText(pos, definition)
        else:
            # Fallback to LLM
            backend_name = self._ai._backend_combo.currentText()
            model_name = self._ai._model_combo.currentText()
            backend = self._ai._backends.get(backend_name)
            
            if not backend or not model_name:
                self._statusbar.showMessage(f"Dictionary: No offline definition found for '{word}' and no AI available.")
                return
                
            QToolTip.showText(pos, f"<i>Asking AI about '{word}'...</i>")
            
            # Keep reference to avoid garbage collection
            self._dict_worker = DictionaryLLMWorker(backend, model_name, word, source_lang, target_lang, self)
            
            # Using default argument trick in lambda to capture `pos` and `word` accurately
            self._dict_worker.finished_definition.connect(
                lambda result, p=pos, w=word: QToolTip.showText(p, f"<div style='margin-bottom: 4px; font-size: 14px;'><b>{w}</b> (AI)</div><div style='font-size: 12px;'>{result}</div>")
            )
            self._dict_worker.error.connect(
                lambda e: self._statusbar.showMessage(f"AI Dictionary Error: {e}", 3000)
            )
            self._dict_worker.start()

    # ═══════════════════════════════════
    # Text Selection → AI
    # ═══════════════════════════════════

    def _on_text_selected(self, text: str) -> None:
        """Handle text selection from the reader."""
        self._last_selected_text = text
        self._ai.set_selected_text(text)
        self._statusbar.showMessage(
            f"Selected {len(text)} characters — use AI panel or TTS to read"
        )

    # ═══════════════════════════════════
    # View Controls
    # ═══════════════════════════════════

    def _set_font(self, family: str) -> None:
        self._prefs["font_family"] = family
        self._reader.set_font_family(family)
        save_prefs(self._prefs)

    def _set_font_size(self, size: int) -> None:
        self._prefs["font_size"] = size
        self._reader.set_font_size(size)
        save_prefs(self._prefs)

    def _set_line_height(self, height: float) -> None:
        self._prefs["line_height"] = height
        self._reader.set_line_height(height)

    def _set_page_width(self, width: int) -> None:
        self._prefs["page_width"] = width
        self._reader.set_page_width(width)
        save_prefs(self._prefs)

    def _animate_widget_width(self, widget: QWidget, start_width: int, end_width: int, max_reset: int = 16777215) -> None:
        if end_width > 0 and not widget.isVisible():
            widget.show()
            
        anim = QPropertyAnimation(widget, b"maximumWidth", self)
        anim.setDuration(150)
        anim.setStartValue(start_width)
        anim.setEndValue(end_width)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        anim_min = QPropertyAnimation(widget, b"minimumWidth", self)
        anim_min.setDuration(150)
        anim_min.setStartValue(start_width)
        anim_min.setEndValue(end_width)
        anim_min.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        if end_width == 0:
            anim.finished.connect(widget.hide)
        else:
            def on_finished():
                widget.setMaximumWidth(max_reset)
                if widget == self._right_tabs:
                    widget.setMinimumWidth(320)
                else:
                    widget.setMinimumWidth(0)
            anim.finished.connect(on_finished)
            
        if not hasattr(self, '_animations'):
            self._animations = []
        self._animations.extend([anim, anim_min])
        anim.start()
        anim_min.start()
        
        self._animations = [a for a in self._animations if a.state() == QPropertyAnimation.State.Running]

    def _toggle_library(self) -> None:
        target = 200 if not self._library.isVisible() or self._library.maximumWidth() == 0 else 0
        current = self._library.width() if self._library.isVisible() else 0
        self._animate_widget_width(self._library, current, target)

    def _toggle_sidebar(self) -> None:
        target = 320 if not self._right_tabs.isVisible() or self._right_tabs.maximumWidth() == 0 else 0
        current = self._right_tabs.width() if self._right_tabs.isVisible() else 0
        self._animate_widget_width(self._right_tabs, current, target)

    def _toggle_focus_mode(self) -> None:
        """Toggle both sidebars simultaneously for distraction-free reading."""
        is_visible = (self._library.isVisible() and self._library.maximumWidth() > 0) or \
                     (self._right_tabs.isVisible() and self._right_tabs.maximumWidth() > 0)
                     
        lib_target = 0 if is_visible else 200
        sidebar_target = 0 if is_visible else 320
        
        lib_current = self._library.width() if self._library.isVisible() else 0
        sidebar_current = self._right_tabs.width() if self._right_tabs.isVisible() else 0
        
        self._animate_widget_width(self._library, lib_current, lib_target)
        self._animate_widget_width(self._right_tabs, sidebar_current, sidebar_target)

    def _toggle_pdf_reading_mode(self, checked: bool) -> None:
        self._prefs["pdf_reading_mode"] = checked
        save_prefs(self._prefs)
        if hasattr(self._reader, "set_pdf_reading_mode"):
            self._reader.set_pdf_reading_mode(checked)

    def _toggle_pdf_dark_mode(self, checked: bool) -> None:
        self._prefs["pdf_dark_mode"] = checked
        save_prefs(self._prefs)
        if hasattr(self._reader, "set_pdf_dark_mode"):
            self._reader.set_pdf_dark_mode(checked)

    def _toggle_epub_md_mode(self, checked: bool) -> None:
        self._prefs["epub_markdown_mode"] = checked
        save_prefs(self._prefs)
        if self._current_book and self._current_book.path.lower().endswith(".epub"):
            # Reload the book to apply the new engine
            self._open_book(self._current_book.path)

    def _reset_pdf_settings(self) -> None:
        if hasattr(self._reader, "reset_pdf_settings"):
            self._reader.reset_pdf_settings()

    # ═══════════════════════════════════
    # TTS Controls
    # ═══════════════════════════════════

    def _tts_play(self) -> None:
        """Start reading the current chapter aloud."""
        self._tts_stop()  # Stop any running TTS to prevent overlapping or jumping
        self._is_reading_selection = False
        self._reader.get_current_chapter_text(self._on_chapter_text_ready)

    def _on_chapter_text_ready(self, text: str) -> None:
        if text:
            self._tts.speak_text(text)
            self._statusbar.showMessage("TTS playing...")

    def _tts_pause_resume(self) -> None:
        if self._tts.is_paused():
            self._tts.resume()
            self._statusbar.showMessage("TTS resumed")
        elif self._tts.is_playing():
            self._tts.pause()
            self._statusbar.showMessage("TTS paused")

    def _tts_stop(self) -> None:
        self._tts.stop()
        self._statusbar.showMessage("TTS stopped")
        self._reader.highlight_sentence("")

    def _tts_read_selection(self, text: str = "") -> None:
        if not text:
            text = getattr(self, "_last_selected_text", "")
        if text:
            self._is_reading_selection = True
            self._tts.stop()
            self._tts.speak_text(text)
            self._statusbar.showMessage("Reading selection...")

    def _toggle_skip_footnotes(self, checked: bool) -> None:
        self._prefs["tts_skip_footnotes"] = checked
        self._tts.set_skip_footnotes(checked)
        save_prefs(self._prefs)
    def _set_tts_voice(self, speaker_id: str) -> None:
        self._prefs["tts_voice"] = speaker_id
        self._tts.set_voice(speaker_id)
        save_prefs(self._prefs)

    # (TTS target removed)

    def _toggle_auto_next(self, checked: bool) -> None:
        self._prefs["tts_auto_next"] = checked
        save_prefs(self._prefs)

    def _on_playback_finished(self) -> None:
        self._statusbar.showMessage("TTS finished")
        self._reader.highlight_sentence("")
        
        # Don't auto-advance if the user manually hit Stop
        if getattr(self._tts, '_stop_flag', None) and self._tts._stop_flag.is_set():
            return
            
        # Don't auto-advance if we were only reading a selection
        if getattr(self, '_is_reading_selection', False):
            return
            
        if self._prefs.get("tts_auto_next", False):
            # Start next chapter and resume reading
            self._reader._next_chapter()
            # Slight delay to let the chapter load before extracting text
            QTimer.singleShot(1000, self._tts_play)

    # ═══════════════════════════════════
    # Media Playback
    # ═══════════════════════════════════
    def _on_media_playback_state_changed(self, state):
        from PyQt6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.StoppedState:
            if self._current_media_id:
                if hasattr(self, '_reader') and self._reader and hasattr(self._reader, '_page'):
                    self._reader._page.runJavaScript(f"if(window.setAudioButtonState) window.setAudioButtonState('{self._current_media_id}', false);")
                self._current_media_id = None

    def _play_media_audio(self, media_id: str) -> None:
        """Play or toggle an embedded audio clip via QMediaPlayer."""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QMediaPlayer
        
        # Toggle if it's the same media and currently playing
        if self._current_media_id == media_id and self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.stop()
            self._statusbar.showMessage("Audio playback stopped")
            return

        if not self._current_book or not getattr(self._current_book, 'audio_clips', None):
            return
            
        audio_data = self._current_book.audio_clips.get(media_id)
        if not audio_data:
            return
            
        filename = audio_data.get("file")
        if not filename:
            return
            
        # Stop TTS if it happens to be running
        self._tts_stop()
            
        # We must extract the audio from the zip to a temporary file,
        # because QMediaPlayer (FFmpeg) does not understand our custom 'epub://' scheme.
        import os
        import tempfile
        try:
            audio_bytes = self._current_book.get_asset(filename)
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"dante_audio_{media_id}.mp3")
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
            url = QUrl.fromLocalFile(temp_path)
        except Exception as e:
            self._statusbar.showMessage(f"Error loading audio: {e}")
            return
            
        start_ms = int(audio_data.get("start_timestamp", 0) * 1000)
        title = audio_data.get("title", "Audio Clip")
        
        def start_playback():
            if start_ms > 0:
                self._media_player.setPosition(start_ms)
            self._media_player.play()
            self._statusbar.showMessage(f"Playing audio: {title}")
            self._current_media_id = media_id
            if hasattr(self, '_reader') and self._reader and hasattr(self._reader, '_page'):
                self._reader._page.runJavaScript(f"if(window.setAudioButtonState) window.setAudioButtonState('{media_id}', true);")

        if self._media_player.source() == url:
            start_playback()
            return

        self._media_player.setSource(url)
        
        def on_media_status_changed(status):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                start_playback()
                self._media_player.mediaStatusChanged.disconnect(on_media_status_changed)
                
        self._media_player.mediaStatusChanged.connect(on_media_status_changed)

    # ═══════════════════════════════════
    def _set_translation_lang(self, lang: str) -> None:
        self._prefs["translation_lang"] = lang
        save_prefs(self._prefs)
        # We don't auto-translate immediately on language change anymore.

    # ═══════════════════════════════════
    # Window Events
    # ═══════════════════════════════════

    def closeEvent(self, event) -> None:
        """Save window size and stop TTS on close."""
        self._tts.stop()
        self._prefs["window_width"] = self.width()
        self._prefs["window_height"] = self.height()
        save_prefs(self._prefs)
        
        # Safely shut down WebEngine to ensure localStorage flushes
        # If we don't manually delete the page before the profile, Chromium aborts saving.
        if hasattr(self, '_reader') and self._reader:
            self._reader._page.deleteLater()
            
        super().closeEvent(event)

    def _on_chapter_changed(self, index: int) -> None:
        """Save the current chapter progress for the active EPUB."""
        if not getattr(self, "_current_book", None) or getattr(self._current_book, 'is_pdf', False):
            return
        
        if hasattr(self._current_book, "progress"):
            self._current_book.progress = index
            self._current_book.save()
            return
            
        progress_dict = self._prefs.setdefault("book_progress", {})
        book_data = progress_dict.setdefault(self._current_book.path, {})
        book_data["chapter"] = index
        save_prefs(self._prefs)

    def _on_translation_requested(self, needed_blocks: list) -> None:
        from app.translation_manager import TranslationManager
        from app.llm_backends import get_all_backends
        
        backend_name = self._ai._backend_combo.currentText()
        model_name = self._ai._model_combo.currentText()
        target_lang = self._prefs.get("translation_lang", "Modern English")
        
        # Grab the EXACT SAME backend instance the AI Panel is currently using!
        backend = self._ai._backends.get(backend_name)
        if not backend:
            self._statusbar.showMessage("No AI Backend available for translation!")
            return
        if not model_name and backend.get_models():
            model_name = backend.get_models()[0]
            
        if not self._reader._translation_manager:
            self._reader._translation_manager = TranslationManager(self._reader._book.path, target_lang, backend, model_name)
            self._reader._translation_manager.chapter_translated.connect(self._reader._on_chapter_translated)
            self._reader._translation_manager.translation_error.connect(self._reader._on_translation_error)
        else:
            # Update existing manager with current AI panel selections
            self._reader._translation_manager.backend = backend
            self._reader._translation_manager.model_name = model_name
            self._reader._translation_manager.target_lang = target_lang
            
        self._reader._translation_manager.translate_blocks(self._reader._current_chapter, needed_blocks)
        self._statusbar.showMessage(f"Translating {len(needed_blocks)} blocks...")
