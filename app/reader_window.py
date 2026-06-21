import sys
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
from .user_data import UserDataManager

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

class NoteDialog(QWidget):
    def __init__(self, title, prompt, text="", parent=None):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
        super().__init__(parent)
        self.dialog = QDialog(parent)
        self.dialog.setWindowTitle(title)
        self.dialog.resize(600, 400)
        layout = QVBoxLayout(self.dialog)
        
        layout.addWidget(QLabel(prompt))
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton(self.tr("Save"))
        save_btn.clicked.connect(self.dialog.accept)
        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.clicked.connect(self.dialog.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def exec(self):
        from PyQt6.QtWidgets import QDialog
        return self.dialog.exec() == QDialog.DialogCode.Accepted
        
    def textValue(self):
        return self.text_edit.toPlainText()
class ReaderWindow(QMainWindow):
    """Main application window for the EPUB Reader."""

    def __init__(self):
        super().__init__()
        self._prefs = load_prefs()
        self._current_book: EpubBook | None = None
        self._tts = OmniVoiceTTSEngine(self)
        self._media_player = None
        self._audio_output = None
        self._current_media_id = None
        
        # Lazy load the media player after the UI draws to avoid FFmpeg startup delays
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self._init_media_player)
        self._current_media_id = None

        self.setWindowTitle(self.tr("Dante EPUB Reader"))
        from PyQt6.QtCore import Qt
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setMinimumSize(1000, 600)
        self.resize(
            self._prefs.get("window_width", 1400),
            self._prefs.get("window_height", 900),
        )

        # ── Setup Dictionary ──
        self._dictionary = DictionaryEngine()

        self._setup_panels()
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
        from .search_panel import SearchPanel
        from .user_data import UserDataManager
        from .userdata_panel import UserDataPanel
        
        self._library = LibraryPanel(self)
        self._reader = ReaderPanel(self._scheme_handler, self)
        self._ai = AiPanel(api_key=load_api_key(), parent=self)
        self._footnotes_panel = FootnotesPanel(self)
        self._search_panel = SearchPanel(self)
        
        self._user_data: UserDataManager | None = None
        self._userdata_panel = UserDataPanel(self)

        # ── Right Sidebar (AI Companion / Search) ──
        import os
        from PyQt6.QtGui import QIcon
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
        self._right_tabs = QTabWidget()
        self._right_tabs.addTab(self._ai, QIcon(os.path.join(icon_dir, "ai_model.svg")), self.tr(" AI Companion"))
        self._right_tabs.addTab(self._footnotes_panel, QIcon(os.path.join(icon_dir, "footnotes.svg")), self.tr(" Footnotes"))
        self._right_tabs.addTab(self._search_panel, QIcon(os.path.join(icon_dir, "search.svg")), self.tr(" Search"))
        self._right_tabs.addTab(self._userdata_panel, QIcon(os.path.join(icon_dir, "bookmark.svg")), self.tr(" Notes"))
        self._right_tabs.setMinimumWidth(320)
        
        # Add a right-aligned close button to the tab bar
        corner_widget = QWidget(self)
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 4, 4)
    
        from PyQt6.QtGui import QIcon
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "close.svg")
        close_btn = QPushButton()
        close_btn.setIcon(QIcon(icon_path))
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("QPushButton { border: none; background: transparent; } QPushButton:hover { background: #30363d; border-radius: 4px; }")
        close_btn.clicked.connect(self._toggle_sidebar)
        
        corner_layout.addWidget(close_btn)
        self._right_tabs.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

        # ── Main Splitter ──
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.addWidget(self._library)
        self._splitter.addWidget(self._reader)
        
        # Wrap right tabs in a container for slide animation
        self._sidebar_container = QWidget()
        sidebar_layout = QHBoxLayout(self._sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_layout.addWidget(self._right_tabs)
        
        self._splitter.addWidget(self._sidebar_container)

        # Set proportional sizes
        self._splitter.setSizes([200, 680, 520])
        self._splitter.setStretchFactor(0, 0)  # Library: fixed-ish
        self._splitter.setStretchFactor(1, 1)  # Reader: stretches
        self._splitter.setStretchFactor(2, 0)  # Sidebar: fixed-ish

        from .ribbon_bar import CustomTitleBar, RibbonBar
        self._title_bar = CustomTitleBar(self)
        self._ribbon = RibbonBar(self)
        
        self._wire_ribbon_signals()
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._title_bar)
        main_layout.addWidget(self._ribbon)
        main_layout.addWidget(self._splitter)
        
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        main_widget.setObjectName("MainWrapper")
        main_widget.setStyleSheet("#MainWrapper { border: 1px solid #30363d; }")
        self.setCentralWidget(main_widget)

        # ── Loading Overlay ──
        self._loading_overlay = QLabel(self.tr("Loading Book..."), self)
        self._loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 180); color: white; font-size: 24px; border-radius: 10px; padding: 20px;")
        self._loading_overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay:
            self._loading_overlay.resize(self.width(), self.height())


    def nativeEvent(self, eventType, message):
        import ctypes
        from ctypes.wintypes import MSG
        from PyQt6.QtCore import QPoint
        try:
            msg = MSG.from_address(int(message))
            if msg.message == 0x0083: # WM_NCCALCSIZE
                if msg.wParam:
                    return True, 0
            elif msg.message == 0x0084: # WM_NCHITTEST
                from PyQt6.QtGui import QCursor
                pos = self.mapFromGlobal(QCursor.pos())
                margin = 8
                
                left = pos.x() < margin
                right = pos.x() > self.width() - margin
                top = pos.y() < margin
                bottom = pos.y() > self.height() - margin
                
                if left and top: return True, 13
                if right and top: return True, 14
                if left and bottom: return True, 16
                if right and bottom: return True, 17
                if left: return True, 10
                if right: return True, 11
                if top: return True, 12
                if bottom: return True, 15
        except Exception:
            pass
        return False, 0

    def showEvent(self, event):
        super().showEvent(event)
        import ctypes
        try:
            hwnd = int(self.winId())
            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            WS_CAPTION = 0x00C00000
            WS_MAXIMIZEBOX = 0x00010000
            WS_MINIMIZEBOX = 0x00020000
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            if not (style & WS_CAPTION):
                user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_CAPTION | WS_MAXIMIZEBOX | WS_MINIMIZEBOX)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027) # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
        except Exception:
            pass

    def changeEvent(self, event):
        super().changeEvent(event)
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, "_title_bar"):
                self._title_bar.set_maximized_icon(self.isMaximized())

    def _wire_ribbon_signals(self):
        tb = self._title_bar
        rb = self._ribbon
        
        # Title Bar
        tb.close_requested.connect(self.close)
        tb.maximize_requested.connect(lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        tb.minimize_requested.connect(self.showMinimized)
        
        tb.open_requested.connect(self._on_open_file)
        tb.prev_chapter_requested.connect(lambda: self._reader._prev_chapter())
        tb.next_chapter_requested.connect(lambda: self._reader._next_chapter())
        
        def on_chapter_combo(idx):
            if idx >= 0 and self._current_book:
                self._reader._load_chapter(idx)
        tb.chapter_selected.connect(on_chapter_combo)
        
        tb.search_requested.connect(self._on_search_requested)
        tb.toggle_library.connect(self._toggle_library)
        tb.toggle_sidebar.connect(self._toggle_sidebar)
        tb.bookmark_requested.connect(self._reader._trigger_add_bookmark)
        tb.scale_requested.connect(self._on_scale_requested)
        tb.lang_requested.connect(self._on_lang_requested)
        
        # Ribbon - View
        rb.theme_btn.setChecked(self._prefs.get("pdf_dark_mode", False))
        rb.theme_btn.toggled.connect(self._toggle_pdf_dark_mode)
        
        rb.pdf_mode_btn.setChecked(self._prefs.get("pdf_reading_mode", False))
        rb.pdf_mode_btn.toggled.connect(self._toggle_pdf_reading_mode)
        
        rb.epub_md_btn.setChecked(self._prefs.get("epub_markdown_mode", False))
        rb.epub_md_btn.toggled.connect(self._toggle_epub_md_mode)
        
        def create_exclusive_menu(btn, options, current_val, callback):
            from PyQt6.QtWidgets import QMenu
            from PyQt6.QtGui import QActionGroup
            menu = QMenu(self)
            group = QActionGroup(self)
            for val, label in options:
                action = menu.addAction(label)
                action.setCheckable(True)
                if val == current_val:
                    action.setChecked(True)
                group.addAction(action)
                action.triggered.connect(lambda checked, v=val: callback(v))
            btn.setMenu(menu)

        # Font popup
        create_exclusive_menu(
            rb.font_btn,
            [(f, f) for f in ["Georgia", "Times New Roman", "Segoe UI", "Inter", "Courier New"]],
            self._prefs.get("font_family", "Georgia"),
            self._set_font
        )
        
        create_exclusive_menu(
            rb.size_btn,
            [(s, f"{s}px") for s in [14, 16, 18, 20, 24, 28, 32]],
            self._prefs.get("font_size", 18),
            self._set_font_size
        )
        
        create_exclusive_menu(
            rb.spacing_btn,
            [(1.2, self.tr("Tight")), (1.5, self.tr("Normal")), (1.8, self.tr("Comfortable")), (2.4, self.tr("Airy"))],
            self._prefs.get("line_height", 1.8),
            self._set_line_height
        )
        
        create_exclusive_menu(
            rb.width_btn,
            [(600, self.tr("Narrow")), (750, self.tr("Medium")), (900, self.tr("Wide")), (0, self.tr("Full Width"))],
            self._prefs.get("page_width", 750),
            self._set_page_width
        )
        
        # Ribbon - Reading
        rb.play_btn.clicked.connect(self._tts_play)
        rb.stop_btn.clicked.connect(self._tts_stop)
        
        create_exclusive_menu(
            rb.voice_btn,
            [(v["id"], v["name"]) for v in self._tts.get_available_voices()],
            self._prefs.get("tts_voice", "jiang_voice"),
            self._set_tts_voice
        )
        
        rb.skip_fn_btn.setChecked(self._prefs.get("tts_skip_footnotes", True))
        rb.skip_fn_btn.toggled.connect(self._toggle_skip_footnotes)
        
        # Ribbon - AI
        native_names = {
            "Modern English": "English",
            "Spanish": "Español",
            "French": "Français",
            "German": "Deutsch",
            "Simplified Chinese": "简体中文",
            "Japanese": "日本語"
        }
        lang_names = {
            "Modern English": self.tr("Modern English"),
            "Spanish": self.tr("Spanish"),
            "French": self.tr("French"),
            "German": self.tr("German"),
            "Simplified Chinese": self.tr("Simplified Chinese"),
            "Japanese": self.tr("Japanese")
        }
        create_exclusive_menu(
            rb.translate_btn,
            [(l, f"{lang_names[l]} | {native_names[l]}") for l in ["Modern English", "Spanish", "French", "German", "Simplified Chinese", "Japanese"]],
            self._prefs.get("translation_lang", "Modern English"),
            self._set_translation_lang
        )
        
        rb.ai_model_btn.clicked.connect(self._toggle_ai_panel)

    def _setup_statusbar(self) -> None:
        """Create the status bar."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage(self.tr("Ready — Double-click a book to start reading"))

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
        
        self._reader.bookmark_requested.connect(self._on_add_bookmark)
        self._reader.note_requested.connect(self._on_add_note)
        
        # UserDataPanel → Actions
        self._userdata_panel.navigate_requested.connect(self._reader.navigate_to_percent)
        self._userdata_panel.delete_bookmark_requested.connect(self._on_delete_bookmark)
        self._userdata_panel.delete_note_requested.connect(self._on_delete_note)
        self._userdata_panel.edit_note_requested.connect(self._on_edit_note)
        self._userdata_panel.edit_bookmark_requested.connect(self._on_edit_bookmark)

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
        self._reader.ai_toggle_requested.connect(self._toggle_ai_panel)
        self._reader.focus_toggle_requested.connect(self._toggle_focus_mode)
        self._reader.search_requested.connect(self._on_search_requested)
        
        # Search panel
        self._search_panel.result_selected.connect(self._on_search_result_selected)
        self._search_panel.clear_requested.connect(self._on_search_clear_requested)

        # AI panel
        self._ai.close_requested.connect(self._toggle_sidebar)

        # TTS signals
        self._tts.playback_finished.connect(self._on_playback_finished)
        self._tts.sentence_started.connect(
            lambda idx, text: self._reader.highlight_sentence(text)
        )
        self._tts.error.connect(
            lambda e: self._statusbar.showMessage(self.tr("TTS Error: ") + str(e))
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

    def _on_scale_requested(self, scale: float) -> None:
        self._prefs["ui_scale"] = scale
        save_prefs(self._prefs)
        QMessageBox.information(self, self.tr("Restart Required"), self.tr("UI Scale set to {scale}%.\nPlease restart the application for the changes to fully take effect.").format(scale=int(scale*100)))

    def _on_lang_requested(self, lang_code: str) -> None:
        self._prefs["app_lang"] = lang_code
        save_prefs(self._prefs)
        QMessageBox.information(self, self.tr("Restart Required"), self.tr("Application language set.\nPlease restart the application for the changes to fully take effect."))

    # --- Bookmarks & Notes ---
    def _on_add_bookmark(self, chapter: int, pct: float):
        if not self._user_data:
            return
            
        from PyQt6.QtWidgets import QInputDialog
        label, ok = QInputDialog.getText(self, self.tr("Add Bookmark"), self.tr("Bookmark Label (optional):"))
        if ok:
            self._user_data.add_bookmark(chapter, pct, label)
            self._userdata_panel.populate_data(self._user_data.get_bookmarks(), self._user_data.get_notes())
            
            # Show the notes panel and switch to bookmarks tab
            if not self._sidebar_container.isVisible() or self._sidebar_container.width() == 0:
                self._toggle_sidebar()
            self._right_tabs.setCurrentWidget(self._userdata_panel)
            self._userdata_panel._tabs.setCurrentIndex(0)

    def _on_add_note(self, chapter: int, pct: float, text: str):
        if not self._user_data:
            return
            
        prompt = self.tr("Note for:\n\"{text}...\"\n").format(text=text[:50]) if text else self.tr("Enter your note:")
        dialog = NoteDialog(self.tr("Add Note"), prompt, parent=self)
        if dialog.exec():
            note = dialog.textValue()
            if note.strip():
                self._user_data.add_note(chapter, pct, text, note)
                self._userdata_panel.populate_data(self._user_data.get_bookmarks(), self._user_data.get_notes())
                
                if not self._sidebar_container.isVisible() or self._sidebar_container.width() == 0:
                    self._toggle_sidebar()
                self._right_tabs.setCurrentWidget(self._userdata_panel)
                self._userdata_panel._tabs.setCurrentIndex(1)

    def _on_delete_bookmark(self, b_id: str):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, self.tr("Delete Bookmark"), self.tr("Are you sure you want to delete this bookmark?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self._user_data and self._user_data.remove_bookmark(b_id):
                self._userdata_panel.populate_data(self._user_data.get_bookmarks(), self._user_data.get_notes())

    def _on_delete_note(self, n_id: str):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, self.tr("Delete Note"), self.tr("Are you sure you want to delete this note?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self._user_data and self._user_data.remove_note(n_id):
                self._userdata_panel.populate_data(self._user_data.get_bookmarks(), self._user_data.get_notes())

    def _on_edit_note(self, n_id: str, old_note: str):
        if not self._user_data:
            return
            
        dialog = NoteDialog(self.tr("Edit Note"), self.tr("Update your note:"), old_note, parent=self)
        if dialog.exec():
            note = dialog.textValue()
            if note.strip():
                self._user_data.update_note(n_id, note)
                self._userdata_panel.populate_data(self._user_data.get_bookmarks(), self._user_data.get_notes())

    def _on_edit_bookmark(self, b_id: str, old_label: str):
        if not self._user_data:
            return
            
        from PyQt6.QtWidgets import QInputDialog
        dialog = QInputDialog(self)
        dialog.setWindowTitle(self.tr("Edit Bookmark"))
        dialog.setLabelText(self.tr("Bookmark Label:"))
        dialog.setTextValue(old_label)
        dialog.resize(600, dialog.sizeHint().height())
        if dialog.exec():
            label = dialog.textValue()
            self._user_data.update_bookmark(b_id, label)
            self._userdata_panel.populate_data(self._user_data.get_bookmarks(), self._user_data.get_notes())

    # ═══════════════════════════════════
    # Book Loading
    # ═══════════════════════════════════

    def _on_open_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Open Book"), "", self.tr("EPUB Files (*.epub);;PDF Files (*.pdf);;Dante Packages (*.dante *.zip);;All Files (*)")
        )
        if path:
            self._open_book(path)

    def _open_book(self, path: str) -> None:
        """Load and display an EPUB book asynchronously."""
        try:
            self._statusbar.showMessage(self.tr("Loading: {path}...").format(path=path))
            
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
        self._statusbar.showMessage(self.tr("Error loading book: {error}").format(error=error_msg))
        QMessageBox.warning(self, self.tr("Load Error"), self.tr("Could not load book:\n{error}").format(error=error_msg))

    def _on_book_loaded(self, book_obj, path: str) -> None:
        self._loading_overlay.hide()
        self._current_book = book_obj
        
        # If it's an EPUB opened in Markdown mode, force it into Reading Mode 
        if path.lower().endswith(".epub") and getattr(self._current_book, 'is_pdf', False):
            self._current_book.set_reading_mode(True)
            self._reader._pdf_reading_mode = True
            
        # Update Title Bar combobox
        self._title_bar.chapter_combo.blockSignals(True)
        self._title_bar.chapter_combo.clear()
        if hasattr(self._current_book, 'get_chapter_count'):
            for i in range(self._current_book.get_chapter_count()):
                title = getattr(self._current_book, 'get_chapter_title', lambda x: f"Chapter {x+1}")(i)
                self._title_bar.chapter_combo.addItem(f"{i+1}. {title}")
        self._title_bar.chapter_combo.blockSignals(False)
            
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
        
        self._user_data = UserDataManager(self._current_book.path)
        self._userdata_panel.populate_data(self._user_data.get_bookmarks(), self._user_data.get_notes())
        
        self._reader.load_book(self._current_book)
        if saved_chapter > 0 and saved_chapter < self._current_book.get_chapter_count():
            self._reader._load_chapter(saved_chapter)
            
        self.setWindowTitle(f"{self._current_book.title} - " + self.tr("Dante Reader"))
        
        title = self._current_book.title
        if len(title) > 50:
            title = title[:47] + "..."
        self._title_bar.drag_area.setText(f"{title}")
        
        total = self._current_book.get_chapter_count()
        self._title_bar.chapter_info.setText(f"{saved_chapter+1} / {total}")
        self._ai.set_book_context(self._current_book.title)
        self._statusbar.showMessage(
            self.tr("Loaded: {title} ({count} chapters)").format(
                title=self._current_book.title,
                count=self._current_book.get_chapter_count()
            )
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
        self._statusbar.showMessage(self.tr("Detected book language: {lang}").format(lang=lang), 4000)

    def _on_footnote_requested(self, foot_id: str) -> None:
        target = 320
        current = self._right_tabs.width() if self._right_tabs.isVisible() else 0
        if not self._right_tabs.isVisible() or self._right_tabs.maximumWidth() == 0:
            self._animate_widget_width(self._right_tabs, current, target)
        self._right_tabs.setCurrentWidget(self._footnotes_panel)
        self._footnotes_panel.scroll_to_footnote(foot_id)

    def _on_search_requested(self, query: str) -> None:
        if not self._current_book:
            return
            
        # Open the search panel
        target = 320
        current = self._right_tabs.width() if self._right_tabs.isVisible() else 0
        if not self._right_tabs.isVisible() or self._right_tabs.maximumWidth() == 0:
            self._animate_widget_width(self._right_tabs, current, target)
            
        self._right_tabs.setCurrentWidget(self._search_panel)
        self._search_panel.show_loading(query)
        
        from .search_worker import SearchWorker
        self._search_worker = SearchWorker(self._current_book, query, self)
        self._search_worker.finished.connect(lambda results, q=query: self._search_panel.load_results(results, q))
        self._search_worker.error.connect(self._search_panel.show_error)
        self._search_worker.start()

    def _on_search_result_selected(self, chapter_idx: int, query: str) -> None:
        if not self._current_book:
            return
            
        self._reader._page.findText("")
        
        def on_search_load_ready(ok=True):
            if ok:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(250, lambda: self._reader._page.findText(query))
            try:
                self._reader._page.loadFinished.disconnect(on_search_load_ready)
            except TypeError:
                pass
                
        self._reader._page.loadFinished.connect(on_search_load_ready)
        self._reader._load_chapter(chapter_idx)

    def _on_search_clear_requested(self) -> None:
        """Clear the yellow text selection in the reader view."""
        self._reader._page.findText("")

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
                self._statusbar.showMessage(self.tr("Dictionary: No offline definition found for '{word}' and no AI available.").format(word=word))
                return
                
            QToolTip.showText(pos, self.tr("<i>Asking AI about '{word}'...</i>").format(word=word))
            
            # Keep reference to avoid garbage collection
            self._dict_worker = DictionaryLLMWorker(backend, model_name, word, source_lang, target_lang, self)
            
            self._dict_worker.finished_definition.connect(
                lambda result, p=pos, w=word: QToolTip.showText(p, f"<div style='margin-bottom: 4px; font-size: 14px;'><b>{w}</b> (" + self.tr("AI") + f")</div><div style='font-size: 12px;'>{result}</div>")
            )
            self._dict_worker.error.connect(
                lambda e: self._statusbar.showMessage(self.tr("AI Dictionary Error: {error}").format(error=str(e)), 3000)
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
            self.tr("Selected {length} characters — use AI panel or TTS to read").format(length=len(text))
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
                if widget == self._sidebar_container:
                    self._sidebar_container.setMinimumWidth(320)
                    self._right_tabs.setMinimumWidth(320)
                    self._right_tabs.setMaximumWidth(16777215)
                elif widget == self._library:
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
        target = 320 if not self._sidebar_container.isVisible() or self._sidebar_container.maximumWidth() == 0 else 0
        current = self._sidebar_container.width() if self._sidebar_container.isVisible() else 0
        
        if target > 0:
            # Opening: lock inner to target width so it slides out
            self._right_tabs.setFixedWidth(target)
        else:
            # Closing: lock inner to current width so it slides in
            self._right_tabs.setFixedWidth(self._right_tabs.width())
            
        self._animate_widget_width(self._sidebar_container, current, target)

    def _toggle_ai_panel(self) -> None:
        """Toggle the sidebar, but ensure it opens to the AI tab."""
        if self._sidebar_container.maximumWidth() > 0 and self._right_tabs.currentWidget() != self._ai:
            # Already open, just switch tabs
            self._right_tabs.setCurrentWidget(self._ai)
        else:
            # Either closed (so toggle it open), or already on AI tab (so toggle it closed)
            if self._sidebar_container.maximumWidth() == 0:
                self._right_tabs.setCurrentWidget(self._ai)
            self._toggle_sidebar()

    def _toggle_focus_mode(self) -> None:
        """Toggle both sidebars simultaneously for distraction-free reading."""
        is_visible = (self._library.isVisible() and self._library.maximumWidth() > 0) or \
                     (self._sidebar_container.isVisible() and self._sidebar_container.maximumWidth() > 0)
                     
        lib_target = 0 if is_visible else 200
        sidebar_target = 0 if is_visible else 320
        
        lib_current = self._library.width() if self._library.isVisible() else 0
        sidebar_current = self._sidebar_container.width() if self._sidebar_container.isVisible() else 0
        
        if sidebar_target > 0:
            self._right_tabs.setFixedWidth(sidebar_target)
        else:
            self._right_tabs.setFixedWidth(self._right_tabs.width())
        
        self._animate_widget_width(self._library, lib_current, lib_target)
        self._animate_widget_width(self._sidebar_container, sidebar_current, sidebar_target)

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
    def _init_media_player(self) -> None:
        if self._media_player is not None:
            return
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.playbackStateChanged.connect(self._on_media_playback_state_changed)

    def _on_media_playback_state_changed(self, state):
        from PyQt6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.StoppedState:
            if self._current_media_id:
                if hasattr(self, '_reader') and self._reader and hasattr(self._reader, '_page'):
                    self._reader._page.runJavaScript(f"if(window.setAudioButtonState) window.setAudioButtonState('{self._current_media_id}', false);")
                self._current_media_id = None

    def _play_media_audio(self, media_id: str) -> None:
        """Play or toggle an embedded audio clip via QMediaPlayer."""
        self._init_media_player()
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
        self._title_bar.chapter_combo.blockSignals(True)
        self._title_bar.chapter_combo.setCurrentIndex(index)
        self._title_bar.chapter_combo.blockSignals(False)
        
        if getattr(self, "_current_book", None):
            total = self._current_book.get_chapter_count()
            self._title_bar.chapter_info.setText(f"{index+1} / {total}")
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
