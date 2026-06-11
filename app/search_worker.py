import re
from html.parser import HTMLParser
from PyQt6.QtCore import QThread, pyqtSignal

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self):
        return "".join(self.text_parts)

def extract_text(html: str) -> str:
    parser = HTMLTextExtractor()
    try:
        parser.feed(html)
        return parser.get_text()
    except Exception:
        # Fallback to simple regex if parser fails
        return re.sub(r'<[^>]+>', '', html)

class SearchWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, book, query: str, parent=None):
        super().__init__(parent)
        self.book = book
        self.query = query

    def run(self):
        try:
            results = []
            query_lower = self.query.lower()
            chapter_count = self.book.get_chapter_count()
            
            for i in range(chapter_count):
                if self.isInterruptionRequested():
                    break
                    
                chapter = self.book.get_chapter(i)
                if not chapter:
                    continue
                    
                # Extract text based on book type
                raw_text = ""
                chapter_title = ""
                
                if hasattr(self.book, "is_dante") and self.book.is_dante:
                    chapter_title = chapter.title
                    # DanteChapter has _blocks containing text
                    for block in getattr(chapter, "_blocks", []):
                        tracks = block.get("tracks", {})
                        for track_key, lines in tracks.items():
                            raw_text += " ".join(lines) + " "
                else:
                    # EpubBook or PdfBook
                    if hasattr(chapter, "get_html"):
                        html_content = chapter.get_html()
                        chapter_title = getattr(chapter, "title", f"Chapter {i+1}")
                    elif isinstance(chapter, str):
                        html_content = chapter
                        chapter_title = f"Page {i+1}"
                    else:
                        continue
                        
                    raw_text = extract_text(html_content)
                
                # Search for query
                text_lower = raw_text.lower()
                start_idx = 0
                
                while True:
                    idx = text_lower.find(query_lower, start_idx)
                    if idx == -1:
                        break
                        
                    # Extract snippet
                    snippet_start = max(0, idx - 40)
                    snippet_end = min(len(raw_text), idx + len(self.query) + 40)
                    
                    snippet = raw_text[snippet_start:snippet_end]
                    # Add ellipsis if truncated
                    if snippet_start > 0:
                        snippet = "..." + snippet
                    if snippet_end < len(raw_text):
                        snippet = snippet + "..."
                        
                    # Highlight query in snippet via HTML
                    # Find query in snippet to wrap in bold tags
                    snippet_lower = snippet.lower()
                    s_idx = snippet_lower.find(query_lower)
                    if s_idx != -1:
                        orig = snippet[s_idx:s_idx + len(self.query)]
                        snippet = snippet[:s_idx] + f"<b>{orig}</b>" + snippet[s_idx + len(self.query):]
                    
                    results.append({
                        "chapter_idx": i,
                        "title": chapter_title,
                        "snippet": snippet.strip()
                    })
                    
                    # Move past this occurrence
                    start_idx = idx + len(self.query)
            
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(str(e))
