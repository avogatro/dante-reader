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
        Columns have specific classes: track-it, track-en, track-ipa.
        Visibility is controlled dynamically by the viewer.
        """
        html = [
            "<?xml version='1.0' encoding='utf-8'?>",
            "<!DOCTYPE html>",
            "<html xmlns=\"http://www.w3.org/1999/xhtml\">",
            "<head>",
            f"<title>{self.title}</title>",
            "<style>",
            "body { font-family: 'Georgia', serif; padding: 20px; line-height: 1.6; }",
            "table.dante-grid { width: 100%; border-collapse: collapse; }",
            "td { vertical-align: top; padding: 0 15px; }",
            ".stanza-row { margin-bottom: 1.5em; }",
            ".line { margin: 0; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{self.title}</h1>",
            "<table class=\"dante-grid\">"
        ]

        trans_id = 0
        for block in self._blocks:
            # We add a spacer row between blocks/stanzas
            html.append('<tr class="stanza-row"><td colspan="3" style="height: 1.5em;"></td></tr>')
            for line in block:
                html.append('<tr>')
                
                # Italian (Original)
                text_it = line.get("text", "")
                html.append(f'<td class="track-it"><p class="line" data-trans-id="trans_{trans_id}">{text_it}</p></td>')
                
                # IPA
                text_ipa = line.get("ipa", "")
                html.append(f'<td class="track-ipa"><p class="line" data-trans-id="trans_{trans_id}">{text_ipa}</p></td>')
                
                # English (Longfellow)
                text_en = line.get("longfellow", "")
                html.append(f'<td class="track-en"><p class="line" data-trans-id="trans_{trans_id}">{text_en}</p></td>')
                
                html.append('</tr>')
                trans_id += 1

        html.append("</table>")
        html.append("</body>")
        html.append("</html>")
        
        return "\n".join(html)

class DanteBook:
    """High-level wrapper around a custom .dante zip file."""

    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)
        self.title = self.filename.replace(".dante", "").replace("_", " ")
        self.author = "Dante Alighieri"
        self.is_pdf = False
        self.is_dante = True
        
        self.chapters: list[DanteChapter] = []
        self._toc: list[tuple[str, int]] = []
        
        self._load()

    def _load(self) -> None:
        with zipfile.ZipFile(self.path, 'r') as zf:
            with zf.open("content.json") as f:
                data = json.load(f)
                
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
        # DanteBook doesn't currently serve complex internal HTML assets besides the cover
        if file_name == "cover.jpg":
            return self.get_cover_image()
        return None

    def get_asset_type(self, file_name: str) -> str:
        if file_name.endswith(".jpg") or file_name.endswith(".jpeg"):
            return "image/jpeg"
        elif file_name.endswith(".png"):
            return "image/png"
        return "application/octet-stream"
