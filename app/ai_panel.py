"""
AI Panel — Multi-backend AI integration for explaining, translating, and
researching selected text from the EPUB reader.
Supports: Ollama (local, free) and Gemini (cloud, API key required).
"""

import markdown
import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QTextBrowser,
    QComboBox,
    QSizePolicy,
)

from app.llm_backends import OllamaBackend, GeminiBackend


class AiPanel(QWidget):
    """
    AI chat panel supporting Ollama (local) and Gemini (cloud) backends.

    Features:
    - Backend selector: switch between Ollama and Gemini
    - "Explain" button: auto-prompt to explain selected text in modern English
    - "Translate" button: auto-prompt to translate Italian/archaic text
    - "Ask..." free-form question about the selected text
    """

    # Signals for thread-safe UI updates from the background worker
    _response_ready = pyqtSignal(str)
    _error_ready = pyqtSignal(str)
    _backend_checked = pyqtSignal(str, bool, list)
    close_requested = pyqtSignal()

    def __init__(self, api_key: str = "", parent=None):
        super().__init__(parent)
        
        # Initialize backends
        self._backends = {
            "Ollama (Local)": OllamaBackend(),
            "Gemini (Cloud)": GeminiBackend(api_key=api_key)
        }
        
        self._active_models: dict[str, str] = {}
        
        self._active_models: dict[str, str] = {}
        
        self._selected_text = ""
        self._book_context = "a book"
        self._is_processing = False
        self._setup_ui()
        self._init_backends()

        # Connect worker signals to UI update slots
        self._response_ready.connect(self._display_response)
        self._error_ready.connect(self._display_error)
        self._backend_checked.connect(self._on_backend_checked)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Header ──
        header_layout = QHBoxLayout()
        
        header_icon = QLabel()
        import os
        from PyQt6.QtGui import QPixmap, QIcon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "ai_model.svg")
        header_icon.setPixmap(QIcon(icon_path).pixmap(24, 24))
        header_layout.addWidget(header_icon)

        header_label = QLabel(self.tr("AI Companion"))
        f = header_label.font()
        f.setPointSize(13)
        f.setWeight(QFont.Weight.Bold)
        header_label.setFont(f)
        header_label.setStyleSheet("color: #c9a96e; background: transparent;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # ── Backend Selector ──
        backend_row = QHBoxLayout()
        backend_row.setSpacing(6)

        backend_label = QLabel(self.tr("Backend:"))
        backend_label.setStyleSheet("color: #8b949e; font-size: 12px; background: transparent;")
        backend_row.addWidget(backend_label)

        self._backend_combo = QComboBox()
        for name in self._backends.keys():
            self._backend_combo.addItem(self.tr(name), name)
        # Find index for Ollama (Local) and set it
        idx = self._backend_combo.findData("Ollama (Local)")
        if idx >= 0:
            self._backend_combo.setCurrentIndex(idx)
        self._backend_combo.currentTextChanged.connect(self._on_backend_changed)
        backend_row.addWidget(self._backend_combo, 1)

        layout.addLayout(backend_row)

        model_row = QHBoxLayout()
        model_row.setSpacing(6)

        model_label = QLabel(self.tr("Model:"))
        model_label.setStyleSheet("color: #8b949e; font-size: 12px; background: transparent;")
        model_row.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        model_row.addWidget(self._model_combo, 1)

        layout.addLayout(model_row)

        # ── Status ──
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: #8b949e; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._status_label)

        # ── Selected Text Preview ──
        self._selection_label = QTextEdit(self.tr("No text selected"))
        self._selection_label.setReadOnly(True)
        self._selection_label.setMinimumHeight(150)
        self._selection_label.setMaximumHeight(250)
        self._selection_label.setStyleSheet("""
            QTextEdit {
                color: #8b949e;
                background-color: #1c2333;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 8px;
                font-size: 16px;
            }
        """)
        self._selection_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._selection_label.customContextMenuRequested.connect(lambda pos: self._show_text_context_menu(pos, self._selection_label))
        layout.addWidget(self._selection_label)

        # ── Quick Action Buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        import os
        from PyQt6.QtGui import QIcon
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")

        self._btn_explain = QPushButton(self.tr(" Explain"))
        self._btn_explain.setIcon(QIcon(os.path.join(icon_dir, "explain.svg")))
        self._btn_explain.setToolTip(self.tr("Explain the selected text in modern English"))
        self._btn_explain.clicked.connect(self._explain)
        btn_row.addWidget(self._btn_explain)

        self._btn_translate = QPushButton(self.tr(" Translate"))
        self._btn_translate.setIcon(QIcon(os.path.join(icon_dir, "translate.svg")))
        self._btn_translate.setToolTip(self.tr("Translate to English"))
        self._btn_translate.clicked.connect(self._translate)
        btn_row.addWidget(self._btn_translate)

        self._btn_search = QPushButton(self.tr(" Research"))
        self._btn_search.setIcon(QIcon(os.path.join(icon_dir, "search.svg")))
        self._btn_search.setToolTip(self.tr("Search for related content and context"))
        self._btn_search.clicked.connect(self._research)
        btn_row.addWidget(self._btn_search)

        layout.addLayout(btn_row)

        # ── Free-form Question Input ──
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText(self.tr("Ask a question about the selected text..."))
        self._input.returnPressed.connect(self._ask_question)
        self._input.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._input.customContextMenuRequested.connect(lambda pos: self._show_text_context_menu(pos, self._input))
        input_row.addWidget(self._input, 1)

        self._btn_ask = QPushButton(self.tr("Ask"))
       
        self._btn_ask.clicked.connect(self._ask_question)
        input_row.addWidget(self._btn_ask)

        layout.addLayout(input_row)

        # ── Response Display ──
        self._response = QTextBrowser()
        self._response.setOpenExternalLinks(True)
        self._response.setStyleSheet("""
            QTextBrowser {
                background-color: #161b22;
                color: #e6e1d8;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 12px;
                font-size: 16px;
            }
        """)
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "ai_model.svg").replace("\\", "/")
        text = self.tr("Select text in the reader, then use the buttons above<br>or ask a free-form question.")
        self._response.setHtml(
            '<div style="text-align: center; padding: 30px; color: #6e7681;">'
            f'<p><img src="{icon_path}" width="32" height="32"></p>'
            f'<p>{text}</p></div>'
        )
        self._response.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._response.customContextMenuRequested.connect(lambda pos: self._show_text_context_menu(pos, self._response))
        layout.addWidget(self._response, 1)

        # ── Clear button ──
        self._btn_clear = QPushButton(self.tr("Clear Chat"))
        self._btn_clear.setStyleSheet("font-size: 11px;")
        self._btn_clear.clicked.connect(self._clear_response)
        layout.addWidget(self._btn_clear, alignment=Qt.AlignmentFlag.AlignRight)

    def _show_text_context_menu(self, pos, widget) -> None:
        if isinstance(widget, QLineEdit):
            menu = widget.createStandardContextMenu()
        else:
            menu = widget.createStandardContextMenu(pos)
            
        import os
        from PyQt6.QtGui import QIcon
        icon_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
        
        actions_to_remove = []
        for action in menu.actions():
            raw_text = action.text().replace("&", "")
            text = raw_text.split('\t')[0]
            
            if text == "Copy" or text == self.tr("Copy"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Copy") + shortcut)
                action.setIcon(QIcon(os.path.join(icon_dir, "copy.svg")))
            elif text == "Select All" or text == self.tr("Select All"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Select All") + shortcut)
                action.setIcon(QIcon(os.path.join(icon_dir, "select_all.svg")))
            elif text == "Paste" or text == self.tr("Paste"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Paste") + shortcut)
                action.setIcon(QIcon(os.path.join(icon_dir, "copy.svg")))
            elif text == "Undo" or text == self.tr("Undo"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Undo") + shortcut)
            elif text == "Redo" or text == self.tr("Redo"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Redo") + shortcut)
            elif text == "Cut" or text == self.tr("Cut"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Cut") + shortcut)
            elif text == "Delete" or text == self.tr("Delete"):
                shortcut = ("\t" + raw_text.split('\t')[1]) if '\t' in raw_text else ""
                action.setText(self.tr("Delete") + shortcut)
            elif "Copy Link Location" in raw_text:
                actions_to_remove.append(action)
                
        for action in actions_to_remove:
            menu.removeAction(action)
                
        menu.exec(widget.mapToGlobal(pos))
        del menu

    # ── Backend Initialization ──

    def _init_backends(self) -> None:
        """Probe available backends asynchronously so we don't freeze the UI."""
        self._status_label.setText(self.tr("⏳ Checking AI connections..."))
        self._set_buttons_enabled(False)
        
        def worker():
            for name, backend in self._backends.items():
                available = backend.is_available()
                models = backend.get_models() if available else []
                self._backend_checked.emit(name, available, models)
                
        threading.Thread(target=worker, daemon=True).start()

    def _on_backend_checked(self, name: str, available: bool, models: list) -> None:
        """Slot called when a backend finishes its network check."""
        if available and models:
            self._active_models[name] = models[0]
            
        # Update the UI if this is the currently selected backend
        if self._backend_combo.currentData() == name:
            self._on_backend_changed()

    def _on_backend_changed(self, *args) -> None:
        """Handle backend selector change."""
        backend_name = self._backend_combo.currentData()
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        
        backend = self._backends.get(backend_name)
        if backend:
            models = backend.get_models()
            if models:
                self._model_combo.addItems(models)
                
                active = self._active_models.get(backend_name)
                if active in models:
                    self._model_combo.setCurrentText(active)
                else:
                    self._model_combo.setCurrentText(models[0])
                    self._active_models[backend_name] = models[0]
                
        self._model_combo.blockSignals(False)
        self._update_backend_status()

    def _on_model_changed(self, model: str) -> None:
        if not model:
            return
        backend_name = self._backend_combo.currentData()
        self._active_models[backend_name] = model
        self._update_backend_status()

    def _update_backend_status(self) -> None:
        """Update status label based on current backend selection."""
        backend_name = self._backend_combo.currentData()
        model = self._model_combo.currentText()
        backend = self._backends.get(backend_name)

        if backend and backend.get_models():
            import os
            check_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "check.svg").replace("\\", "/")
            msg = self.tr("{backend} connected — model: {model}").format(backend=backend_name, model=model)
            self._status_label.setText(f"<img src='{check_path}' width='14' height='14'> {msg}")
            self._set_buttons_enabled(True)
        else:
            import os
            err_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "error.svg").replace("\\", "/")
            msg = self.tr("{backend} unavailable. Check connection or API keys.").format(backend=backend_name)
            self._status_label.setText(f"<img src='{err_path}' width='14' height='14'> {msg}")
            self._set_buttons_enabled(False)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._btn_explain.setEnabled(enabled)
        self._btn_translate.setEnabled(enabled)
        self._btn_search.setEnabled(enabled)
        self._btn_ask.setEnabled(enabled)
        self._input.setEnabled(enabled)

    # ── Public API ──

    def set_selected_text(self, text: str) -> None:
        """Update the currently selected text available for prompts."""
        self._selected_text = text.strip()
        self._selection_label.setPlainText(text)
        self._selection_label.setStyleSheet("""
            QTextEdit {
                color: #e6e1d8;
                background-color: #1c2333;
                border: 1px solid #c9a96e;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
        """)

    def set_book_context(self, title: str) -> None:
        """Set the book title context for AI prompts."""
        self._book_context = title.strip() if title else "a book"

    def set_api_key(self, key: str) -> None:
        """Update the API key and reinitialize Gemini."""
        if "Gemini (Cloud)" in self._backends:
            # Recreate Gemini backend with new key
            from app.llm_backends import GeminiBackend
            self._backends["Gemini (Cloud)"] = GeminiBackend(api_key=key)
        self._init_backends()

    # ── Actions ──

    def _explain(self) -> None:
        if not self._selected_text:
            return
        from app.config import load_prefs
        target_lang = load_prefs().get("translation_lang", "Modern English")
        prompt = (
            f"Explain the following passage from {self._book_context} in plain, {target_lang}. "
            "Break down any complex metaphors or archaic phrasing. "
            "Provide historical and literary context where relevant:\n\n"
            f'"{self._selected_text}"'
        )
        self._send_prompt(prompt)

    def _translate(self) -> None:
        if not self._selected_text:
            return
        from app.config import load_prefs
        target_lang = load_prefs().get("translation_lang", "Modern English")
        prompt = (
            f"Translate the following text into {target_lang}. "
            "If it's already in the target language but uses archaic language, modernize it. "
            "Preserve the poetic structure if applicable:\n\n"
            f'"{self._selected_text}"'
        )
        self._send_prompt(prompt)

    def _research(self) -> None:
        if not self._selected_text:
            return
        from app.config import load_prefs
        target_lang = load_prefs().get("translation_lang", "Modern English")
        prompt = (
            f"You are a research assistant for studying {self._book_context}. "
            f"Please respond in {target_lang}. "
            "Analyze this passage and provide:\n"
            "1. Historical context and references\n"
            "2. Key characters or figures mentioned\n"
            "3. Symbolic meaning\n"
            "4. Related passages or thematic connections\n\n"
            f'"{self._selected_text}"'
        )
        self._send_prompt(prompt)

    def _ask_question(self) -> None:
        question = self._input.text().strip()
        if not question:
            return

        self._input.clear()
        
        from app.config import load_prefs
        target_lang = load_prefs().get("translation_lang", "Modern English")
        
        if self._selected_text:
            prompt = (
                f"Context from {self._book_context}:\n\"{self._selected_text}\"\n\n"
                f"Question: {question}\n\n"
                f"Please respond in {target_lang}."
            )
        else:
            prompt = f"Regarding {self._book_context}: {question}\nPlease respond in {target_lang}."
            
        self._send_prompt(prompt)

    def _send_prompt(self, prompt: str) -> None:
        """Send a prompt to the selected backend in a background thread."""
        if self._is_processing:
            return

        backend_key = self._backend_combo.currentData()
        backend = self._backends.get(backend_key)
        model = self._model_combo.currentText()
        if not model:
            self._display_error(self.tr("Please select a model first."))
            return

        if backend_key == "Gemini (Cloud)" and not backend.is_available():
            self._display_error(self.tr("Gemini client not initialized. Check your API key."))
            return

        self._is_processing = True
        self._set_buttons_enabled(False)
        self._status_label.setText(self.tr("⏳ Thinking..."))
        msg = self.tr("⏳ Generating response...")
        self._response.setHtml(
            '<div style="color: #c9a96e; padding: 12px;">'
            f'{msg}</div>'
        )

        thread = threading.Thread(
            target=self._worker, args=(prompt, backend_key, model), daemon=True
        )
        thread.start()

    def _worker(self, prompt: str, backend_name: str, model: str) -> None:
        """Background worker — routes to the selected LLMBackend."""
        try:
            backend = self._backends.get(backend_name)
            if not backend:
                raise RuntimeError(f"Backend '{backend_name}' not found.")
                
            text = backend.generate(prompt, model)
            html = self._format_response(text)
            self._response_ready.emit(html)

        except Exception as e:
            self._error_ready.emit(str(e))

    # ── UI Updates (called on main thread via signals) ──

    def _display_response(self, html: str) -> None:
        """Display the AI response."""
        self._response.setHtml(html)
        self._is_processing = False
        self._set_buttons_enabled(True)
        backend = self._backend_combo.currentText()
        model = self._model_combo.currentText()
        import os
        check_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "check.svg").replace("\\", "/")
        self._status_label.setText(f"<img src='{check_path}' width='14' height='14'> {backend} — {model}")

    def _display_error(self, error: str) -> None:
        """Display an error message."""
        # Escape HTML in error text
        safe_error = error.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_error = safe_error.replace("\n", "<br>")
        import os
        err_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "error.svg").replace("\\", "/")
        self._response.setHtml(
            f'<div style="color: #f85149; padding: 12px; '
            f'font-size: 14px; line-height: 1.6;">'
            f"<img src='{err_path}' width='14' height='14'> {safe_error}</div>"
        )
        self._is_processing = False
        self._set_buttons_enabled(True)
        self._status_label.setText(f"<img src='{err_path}' width='14' height='14'> " + self.tr("Last request failed"))

    def _format_response(self, text: str) -> str:
        """Convert markdown response to styled HTML."""
        # Pre-process common LaTeX math symbols that the LLM might generate
        # since QTextBrowser cannot render MathJax JavaScript.
        text = text.replace("$\\rightarrow$", "→").replace("\\rightarrow", "→")
        text = text.replace("$\\leftarrow$", "←").replace("\\leftarrow", "←")
        text = text.replace("$\\Rightarrow$", "⇒").replace("\\Rightarrow", "⇒")
        
        try:
            import markdown
            # Convert markdown to HTML using extensions for better formatting
            html_content = markdown.markdown(text, extensions=['fenced_code', 'tables', 'nl2br'])
        except ImportError:
            # Fallback if markdown is not installed
            html_content = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_content = html_content.replace("\n", "<br>")

        # Wrap in a styled div for the QTextBrowser
        return (
            f'<div style="font-size: 14px; '
            f'color: #e6e1d8; line-height: 1.6; padding: 8px;">'
            f"{html_content}</div>"
        )

    def _clear_response(self) -> None:
        """Clear the response area."""
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "ai_model.svg").replace("\\", "/")
        text = self.tr("Select text in the reader, then use the buttons above<br>or ask a free-form question.")
        self._response.setHtml(
            '<div style="text-align: center; padding: 30px; color: #6e7681;">'
            f'<p><img src="{icon_path}" width="32" height="32"></p>'
            f'<p>{text}</p></div>'
        )
        self._selected_text = ""
        self._selection_label.setText(self.tr("No text selected"))
        self._selection_label.setStyleSheet("""
            QTextEdit {
                color: #8b949e;
                background-color: #1c2333;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }
        """)
