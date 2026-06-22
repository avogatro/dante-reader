from PyQt6.QtCore import QObject
import json

class TableLayoutManager(QObject):
    def __init__(self, reader_panel):
        super().__init__(reader_panel)
        self.rp = reader_panel

    def get_table_layout_css(self) -> str:
        css_lines = []
        
        if getattr(self.rp._book, 'is_dante', False):
            active_count = sum(1 for chk in self.rp._dynamic_checkboxes.values() if chk.isChecked())
            width_pct = (100.0 / active_count) if active_count > 0 else 100.0
            
            for key, chk in self.rp._dynamic_checkboxes.items():
                is_checked = chk.isChecked()
                css_lines.append(f".track-{key} {{ display: {'table-cell' if is_checked else 'none'} !important; width: {width_pct if is_checked else 0}% !important; padding: {'0 15px' if is_checked else '0'} !important; }}")
                
        else:
            show_orig = self.rp._dynamic_checkboxes.get("original", type('obj', (object,), {'isChecked': lambda: True})).isChecked()
            show_trans = self.rp._dynamic_checkboxes.get("translation", type('obj', (object,), {'isChecked': lambda: False})).isChecked()
            css_lines.append(f".track-original {{ display: {'block' if show_orig else 'none'} !important; flex: 1; padding: {'0 15px' if show_orig else '0'} !important; }}")
            css_lines.append(f".track-translation {{ display: {'block' if show_trans else 'none'} !important; flex: 1; padding: {'0 15px' if show_trans else '0'} !important; }}")
        
        return " ".join(css_lines)

    def update_table_layout(self):
        css_str = self.get_table_layout_css()
        safe_css = json.dumps(css_str)
        js = f"if (typeof window.updateTableLayoutCss === 'function') {{ window.updateTableLayoutCss({safe_css}); }}"
        self.rp._page.runJavaScript(js)
