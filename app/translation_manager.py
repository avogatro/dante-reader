import os
import json
import hashlib
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from app.translation_parser import extract_translation_blocks
import re

class TranslationWorker(QThread):
    """Background worker to translate a single chapter via LLM."""
    translation_done = pyqtSignal(int, dict, str)  # chapter_index, translations_dict, target_lang
    translation_error = pyqtSignal(int, str, str)  # chapter_index, error_msg, target_lang

    def __init__(self, chapter_index: int, blocks: list[dict], target_lang: str, backend, model_name: str):
        super().__init__()
        self.chapter_index = chapter_index
        self.blocks = blocks
        self.target_lang = target_lang
        self.backend = backend
        self.model_name = model_name

    def run(self):
        try:
            if not self.blocks:
                self.translation_done.emit(self.chapter_index, {}, self.target_lang)
                return

            # Extract just the html strings for the prompt, stripping <br> tags
            # so the LLM doesn't hallucinate invalid backspace escapes
            texts = [re.sub(r'<br\s*/?>', ' ', b["html"], flags=re.IGNORECASE) for b in self.blocks]
            
            prompt = f"""You are a master translator.
Translate the following text blocks into {self.target_lang}.
You MUST return ONLY a valid JSON array of strings, in the exact same order as the input.
Do NOT wrap the response in markdown code blocks. Just output raw JSON.
Maintain all HTML formatting (e.g. <b> tags).

Input blocks:
{json.dumps(texts, ensure_ascii=False, indent=2)}
"""
            # Call LLM
            response_text = self.backend.generate(prompt, self.model_name)
            
            # Clean up response in case LLM wrapped it in markdown
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            translated_texts = json.loads(response_text)
            
            if len(translated_texts) != len(self.blocks):
                raise ValueError(f"LLM returned {len(translated_texts)} items, expected {len(self.blocks)}")

            # Reconstruct the dict
            translations = {}
            for i, block in enumerate(self.blocks):
                text = translated_texts[i]
                # Fix common LLM formatting glitch where it replaces '<b' with '\b'
                # which json.loads then parses as a backspace character (\x08)
                if isinstance(text, str):
                    text = text.replace('\x08r/&gt', '<br>')
                    
                translations[block["id"]] = text
                
            self.translation_done.emit(self.chapter_index, translations, self.target_lang)

        except Exception as e:
            self.translation_error.emit(self.chapter_index, str(e), self.target_lang)


class TranslationManager(QObject):
    """Manages loading/saving translations and queuing translation workers."""
    chapter_translated = pyqtSignal(int)  # Emitted when a chapter is fully translated
    translation_error = pyqtSignal(int, str) # Emitted on error

    def __init__(self, book_path: str, target_lang: str, backend, model_name: str):
        super().__init__()
        self.book_path = book_path
        self.backend = backend
        self.model_name = model_name
        
        # Determine save path
        self._app_data = os.path.join(os.path.expanduser("~"), ".dante-reader", "translations")
        os.makedirs(self._app_data, exist_ok=True)
        
        # Hash book path to get unique id
        self._book_hash = hashlib.md5(book_path.encode('utf-8')).hexdigest()
        
        self.translations = {}  # { chapter_index: { "trans_0": "text" } }
        
        self._target_lang = None
        self.target_lang = target_lang
        
        self._workers = []  # Keep references to running threads
        self._translating_chapters = set()

    @property
    def target_lang(self) -> str:
        return self._target_lang

    @target_lang.setter
    def target_lang(self, lang: str):
        if self._target_lang == lang:
            return
            
        self._target_lang = lang
        lang_safe = "".join(c for c in lang if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_").lower()
        self.save_path = os.path.join(self._app_data, f"{self._book_hash}_{lang_safe}.json")
        
        self.translations.clear()
        self._load()

    def _load(self):
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert str keys to int
                    self.translations = {int(k): v for k, v in data.items()}
            except Exception as e:
                print(f"Error loading translations: {e}")

    def _save(self):
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(self.translations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving translations: {e}")

    def has_chapter(self, index: int) -> bool:
        return index in self.translations

    def get_chapter(self, index: int) -> dict:
        return self.translations.get(index, {})

    def translate_blocks(self, index: int, blocks: list[dict]):
        """Start a background worker to translate a subset of blocks."""
        needed_blocks = [b for b in blocks if b["id"] not in self.get_chapter(index)]
        if not needed_blocks:
            self.chapter_translated.emit(index)
            return
            
        if index in self._translating_chapters:
            print(f"[Translation] Chapter {index} is already translating, ignoring duplicate request.")
            return
            
        self._translating_chapters.add(index)

        worker = TranslationWorker(index, needed_blocks, self.target_lang, self.backend, self.model_name)
        worker.translation_done.connect(self._on_translation_done)
        worker.translation_error.connect(self._on_translation_error)
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._workers.remove(w) if w in self._workers else None)
        worker.start()

    def _on_translation_done(self, index: int, trans_dict: dict, lang: str):
        if lang != self.target_lang:
            print(f"[Translation] Ignoring completed translation for {lang} (current lang is {self.target_lang})")
            return
            
        if index in self._translating_chapters:
            self._translating_chapters.remove(index)
            
        if index not in self.translations:
            self.translations[index] = {}
        self.translations[index].update(trans_dict)
        self._save()
        self.chapter_translated.emit(index)

    def _on_translation_error(self, index: int, error: str, lang: str):
        if lang != self.target_lang:
            return
            
        if index in self._translating_chapters:
            self._translating_chapters.remove(index)
        print(f"[Translation] Error translating chapter {index}: {error}")
        self.translation_error.emit(index, error)
