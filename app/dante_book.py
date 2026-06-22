import os
import json
import zipfile
from typing import Optional

class DanteChapter:
    """Represents a single chapter/canto in a Dante book."""

    __slots__ = ("title", "file_name", "index", "_blocks", "_book_ref")

    def __init__(self, title: str, file_name: str, index: int, blocks: list, book_ref):
        self.title = title
        self.file_name = file_name
        self.index = index
        self._blocks = blocks
        self._book_ref = book_ref

    def get_html(self) -> str:
        """
        Generate a single-page HTML table containing all tracks.
        """
        rows = []
        trans_id = 0
        for block in self._blocks:
            # We add a spacer row between blocks/stanzas
            rows.append('<tr class="stanza-row"><td colspan="3" style="height: 1.5em;"></td></tr>')
            
            # V2 Schema
            block_id = block.get("id", f"block_{trans_id}")
            rows.append(f'<tr class="block-row" id="{block_id}">')
            tracks = block.get("tracks", {})
            
            # Fetch metadata tracks from book to maintain order if possible
            book_metadata = getattr(self._book_ref, 'metadata', {})
            track_defs = book_metadata.get('tracks', {})
            
            for track_key in track_defs.keys():
                lines = tracks.get(track_key, [])
                
                rows.append(f'<td class="track-{track_key}">')
                for line_text in lines:
                    rows.append(f'<p class="line" data-trans-id="trans_{trans_id}">{line_text}</p>')
                    trans_id += 1
                rows.append('</td>')
                
            rows.append('</tr>')
        
        media_registry = {
            "audio": getattr(self._book_ref, 'audio_clips', {}),
            "video": getattr(self._book_ref, 'videos', {}),
            "foot": getattr(self._book_ref, 'footnotes', {})
        }
        
        base_dir = os.path.dirname(__file__)
        template_path = os.path.join(base_dir, "assets", "html", "dante_template.html")
        js_path = os.path.join(base_dir, "assets", "js", "media_handler.js")
        
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                html_template = f.read()
            with open(js_path, "r", encoding="utf-8") as f:
                media_script = f.read()
        except Exception:
            return "<html><body>Error loading template</body></html>"
            
        html = html_template.replace("{title}", self.title)
        html = html.replace("{table_rows}", "\n".join(rows))
        html = html.replace("{media_json}", json.dumps(media_registry))
        html = html.replace("{media_handler_script}", media_script)
        
        return html

class DanteBook:
    """High-level wrapper around a custom .dante zip file."""

    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)
        self.title = self.filename.replace(".dante", "").replace("_", " ")
        self.author = "Dante Alighieri"
        self.is_pdf = False
        self.is_dante = True
        self.language = ""
        
        self.chapters: list[DanteChapter] = []
        self._toc: list[tuple[str, int]] = []
        
        # Global V2 registries
        self.metadata = {}
        self.footnotes = {}
        self.images = {}
        self.audio_clips = {}
        self.videos = {}
        
        self._load()

    def _load(self) -> None:
        with zipfile.ZipFile(self.path, 'r') as zf:
            with zf.open("content.json") as f:
                data = json.load(f)
                
            self.metadata = data.get("metadata", {})
            self.footnotes = data.get("footnotes", {})
            self.images = data.get("images", {})
            self.audio_clips = data.get("audio_clips", {})
            self.videos = data.get("videos", {})
            
            tracks = self.metadata.get("tracks", {})
            if "text" in tracks and "language" in tracks["text"]:
                self.language = tracks["text"]["language"]
                
            index = 0
            for b_idx, book in enumerate(data.get("books", [])):
                book_title = book.get("title", f"Book {b_idx+1}")
                for canto in book.get("cantos", []):
                    canto_num = canto.get("canto_number", 0)
                    title = f"{book_title} - Canto {canto_num}"
                    file_name = f"canto_{index}.html"
                    
                    self.chapters.append(
                        DanteChapter(
                            title=title,
                            file_name=file_name,
                            index=index,
                            blocks=canto.get("blocks", []),
                            book_ref=self
                        )
                    )
                    self._toc.append((title, index))
                    index += 1

    def get_chapter(self, index: int) -> Optional[DanteChapter]:
        if 0 <= index < len(self.chapters):
            return self.chapters[index]
        return None

    def get_chapter_count(self) -> int:
        return len(self.chapters)

    def get_toc_entries(self) -> list[tuple[str, int]]:
        return self._toc

    def get_cover_image(self) -> Optional[bytes]:
        try:
            with zipfile.ZipFile(self.path, 'r') as zf:
                if "cover.jpg" in zf.namelist():
                    return zf.read("cover.jpg")
        except Exception:
            pass
        return None

    def get_asset(self, file_name: str) -> Optional[bytes]:
        try:
            with zipfile.ZipFile(self.path, 'r') as zf:
                if file_name in zf.namelist():
                    return zf.read(file_name)
        except Exception:
            pass
        return None

    def get_asset_type(self, file_name: str) -> str:
        if file_name.endswith(".jpg") or file_name.endswith(".jpeg"):
            return "image/jpeg"
        elif file_name.endswith(".png"):
            return "image/png"
        return "application/octet-stream"
