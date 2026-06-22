from PyQt6.QtWidgets import QMainWindow, QTabWidget, QPlainTextEdit

class SourceViewerWindow(QMainWindow):
    """
    Window that displays the page source (rendered HTML, original EPUB HTML,
    and CSS stylesheets) in separate tabs.
    """

    def __init__(self, rendered_html: str, original_html: str,
                 css_sheets: list[tuple[str, str]], chapter_title: str,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Source — {chapter}").format(chapter=chapter_title))
        self.resize(900, 700)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        # Tab 1: Rendered HTML (with injected styles and bridge)
        rendered_edit = self._make_editor(rendered_html, "html")
        tabs.addTab(rendered_edit, self.tr("Rendered HTML"))

        # Tab 2: Original EPUB HTML (before our injections)
        original_edit = self._make_editor(original_html, "html")
        tabs.addTab(original_edit, self.tr("Original EPUB HTML"))

        # Tab 3+: CSS stylesheets from the EPUB
        if css_sheets:
            for name, css_content in css_sheets:
                css_edit = self._make_editor(css_content, "css")
                short_name = name.rsplit("/", 1)[-1] if "/" in name else name
                tabs.addTab(css_edit, self.tr("CSS: {name}").format(name=short_name))
        else:
            no_css = self._make_editor(self.tr("/* No CSS stylesheets found in this EPUB */"), "css")
            tabs.addTab(no_css, self.tr("CSS"))

    def _make_editor(self, content: str, lang: str) -> QPlainTextEdit:
        """Create a read-only code editor widget."""
        editor = QPlainTextEdit()
        editor.setPlainText(content)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setObjectName("editorInput")
        return editor
