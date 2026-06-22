from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox
import json
from app.translation_parser import extract_translation_blocks

class TranslationHelper(QObject):
    def __init__(self, reader_panel):
        super().__init__(reader_panel)
        self.rp = reader_panel

    def translate_visible_page(self):
        trans_chk = self.rp._dynamic_checkboxes.get("ai_translation" if getattr(self.rp._book, 'is_dante', False) else "translation")
        if trans_chk and not trans_chk.isChecked():
            trans_chk.setChecked(True)
            
        js = "if (typeof window.translationHelper !== 'undefined') { window.translationHelper.getVisibleTransIds(); } else { []; }"
        self.rp._page.runJavaScript(js, self.on_visible_ids_received)

    def on_visible_ids_received(self, visible_ids):
        if not visible_ids:
            return
            
        all_blocks = extract_translation_blocks(self.rp._last_rendered_html)
        needed_blocks = [b for b in all_blocks if b["id"] in visible_ids]
        
        if needed_blocks:
            if hasattr(self.rp, "_btn_translate_page"):
                self.rp._btn_translate_page.setText(self.tr("⏳ Translating..."))
                self.rp._btn_translate_page.setEnabled(False)
            self.rp.translation_requested.emit(needed_blocks)

    def on_chapter_translated(self, index: int):
        if hasattr(self.rp, "_btn_translate_page"):
            self.rp._btn_translate_page.setText(self.tr("AI: Translate Page"))
            self.rp._btn_translate_page.setEnabled(True)
        if index == self.rp._current_chapter and self.rp._translation_manager:
            translations = self.rp._translation_manager.get_chapter(index)
            is_dante = getattr(self.rp._book, 'is_dante', False)
            safe_trans = json.dumps(translations)
            safe_is_dante = str(is_dante).lower()
            js = f"if (typeof window.translationHelper !== 'undefined') {{ window.translationHelper.injectTranslations({safe_trans}, {safe_is_dante}); }}"
            self.rp._page.runJavaScript(js)

    def on_translation_error(self, index: int, error_msg: str):
        if hasattr(self.rp, "_btn_translate_page"):
            self.rp._btn_translate_page.setText(self.tr("AI: Translate Page"))
            self.rp._btn_translate_page.setEnabled(True)
        QMessageBox.critical(self.rp, self.tr("Translation Error"), self.tr("Failed to translate chapter {index}:\n\n{error}").format(index=index, error=error_msg))
