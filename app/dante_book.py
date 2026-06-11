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
            "button.media-btn { margin-top: 10px; cursor: pointer; background-color: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 5px 10px; border-radius: 6px; font-size: 0.9em; font-family: 'Segoe UI', system-ui; }",
            "button.media-btn:hover { background-color: #30363d; }",
            "[data-foot-id] { color: #58a6ff; cursor: pointer; text-decoration: underline; }",
            "[data-image-id] { width: 100%; max-width: 200px; height: auto; display: block; margin-bottom: 10px; border-radius: 4px; }",
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
            
            # V2 Schema
            block_id = block.get("id", f"block_{trans_id}")
            html.append(f'<tr class="block-row" id="{block_id}">')
            tracks = block.get("tracks", {})
            
            # Fetch metadata tracks from book to maintain order if possible
            book_metadata = getattr(self._book_ref, 'metadata', {})
            track_defs = book_metadata.get('tracks', {})
            
            for track_key in track_defs.keys():
                lines = tracks.get(track_key, [])
                
                html.append(f'<td class="track-{track_key}">')
                for line_text in lines:
                    html.append(f'<p class="line" data-trans-id="trans_{trans_id}">{line_text}</p>')
                    trans_id += 1
                html.append('</td>')
                
            html.append('</tr>')

        html.append("</table>")
        
        # Inject Media JS Bridge
        import json
        media_registry = {
            "audio": getattr(self._book_ref, 'audio_clips', {}),
            "video": getattr(self._book_ref, 'videos', {}),
            "foot": getattr(self._book_ref, 'footnotes', {})
        }
        js_script = f"""
        <script>
        (function() {{
            const media = {json.dumps(media_registry)};
            window._dante_media = media;
            
            window.setAudioButtonState = function(id, isPlaying) {{
                document.querySelectorAll('[data-audio-id]').forEach(el => {{
                    const btnId = el.getAttribute('data-audio-id');
                    if (!media.audio[btnId]) return;
                    
                    if (btnId === id && isPlaying) {{
                        el.innerHTML = '<button class="media-btn">⏸ ' + media.audio[btnId].title + ' (Stop)</button>';
                    }} else {{
                        el.innerHTML = '<button class="media-btn">▶ ' + media.audio[btnId].title + '</button>';
                    }}
                }});
            }};
            
            // Initial hydrate
            window.setAudioButtonState(null, false);
            
            document.querySelectorAll('[data-video-id]').forEach(el => {{
                const id = el.getAttribute('data-video-id');
                if (media.video[id] && media.video[id].title) {{
                    el.innerHTML = '<button class="media-btn">📺 ' + media.video[id].title + '</button>';
                }}
            }});
            
            document.addEventListener('click', e => {{
                const audioDiv = e.target.closest('[data-audio-id]');
                if (audioDiv) {{
                    window.location.href = 'epub://action/media?type=audio&id=' + audioDiv.getAttribute('data-audio-id');
                    return;
                }}
                
                const videoDiv = e.target.closest('[data-video-id]');
                if (videoDiv) {{
                    window.location.href = 'epub://action/media?type=video&id=' + videoDiv.getAttribute('data-video-id');
                    return;
                }}
                
                const footLink = e.target.closest('[data-foot-id]');
                if (footLink) {{
                    window.location.href = 'epub://action/media?type=foot&id=' + footLink.getAttribute('data-foot-id');
                    return;
                }}
            }});
        }})();
        </script>
        """
        html.append(js_script)
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
