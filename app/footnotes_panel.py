from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame
from PyQt6.QtCore import Qt, QTimer

class FootnoteWidget(QFrame):
    def __init__(self, foot_id: str, text: str, parent=None):
        super().__init__(parent)
        self.foot_id = foot_id
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        
        layout.addWidget(self.label)
        self.reset_style()

    def highlight(self):
        self.setStyleSheet("""
            FootnoteWidget {
                background-color: #333311;
                border: 1px solid #ffcc00;
                border-radius: 5px;
                margin-bottom: 5px;
            }
        """)
        QTimer.singleShot(1500, self.reset_style)
        
    def reset_style(self):
        self.setStyleSheet("""
            FootnoteWidget {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 5px;
                margin-bottom: 5px;
            }
        """)

class FootnotesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        
        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)
        
        self.footnote_widgets = {}

    def load_footnotes(self, footnotes: dict):
        # Clear existing
        for i in reversed(range(self.content_layout.count())): 
            widget = self.content_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        self.footnote_widgets.clear()
        
        if not footnotes:
            lbl = QLabel("No footnotes available.")
            lbl.setStyleSheet("color: #8b949e;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(lbl)
            return

        for f_id, text in footnotes.items():
            fw = FootnoteWidget(f_id, text)
            self.content_layout.addWidget(fw)
            self.footnote_widgets[f_id] = fw

    def scroll_to_footnote(self, foot_id: str):
        if foot_id in self.footnote_widgets:
            fw = self.footnote_widgets[foot_id]
            # Ensure visible with some margin
            self.scroll_area.ensureWidgetVisible(fw, 0, 50)
            fw.highlight()
