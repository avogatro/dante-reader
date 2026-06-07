import os
import base64
import pymupdf4llm
import markdown

try:
    import fitz  # PyMuPDF
    HAVE_FITZ = True
except ImportError:
    HAVE_FITZ = False

class PdfBook:
    """
    A wrapper for PDF files that supports two modes:
    1. PDF.js Native Mode (default): Treated as 1 single chapter, rendering via Mozilla PDF.js.
    2. Reading Mode: Uses PyMuPDF to extract text and images into EPUB-like HTML chapters per page.
    """
    def __init__(self, path: str):
        self.path = path
        self.title = os.path.basename(path).replace('.pdf', '')
        self.is_pdf = True
        self._reading_mode = False
        
        self._doc = None
        if HAVE_FITZ:
            self._doc = fitz.open(path)

    def set_reading_mode(self, enabled: bool) -> None:
        self._reading_mode = enabled

    def get_chapter_count(self) -> int:
        if self._reading_mode and self._doc:
            return len(self._doc)
        return 1

    def get_toc_entries(self) -> list:
        if self._reading_mode and self._doc:
            return [(f"Page {i+1}", i) for i in range(len(self._doc))]
        return [(self.title, 0)]

    def get_cover_image(self) -> bytes | None:
        if self._doc and len(self._doc) > 0:
            try:
                page = self._doc.load_page(0)
                pix = page.get_pixmap()
                return pix.tobytes("png")
            except Exception:
                pass
        return None

    def get_chapter(self, index: int) -> str:
        """Extract reflowable markdown text from a specific PDF page and convert to HTML."""
        if not self._doc or not self._reading_mode:
            return "<html><body><h1>PDF Reading Mode Unavailable</h1></body></html>"
            
        if index < 0 or index >= len(self._doc):
            return "<html><body><h1>Page not found</h1></body></html>"

        try:
            # pymupdf4llm extracts markdown preserving columns, tables, and headers perfectly
            md_text = pymupdf4llm.to_markdown(self._doc, pages=[index])
            html_body = markdown.markdown(md_text, extensions=['tables'])
        except Exception as e:
            html_body = f"<p>Error extracting text: {e}</p>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Page {index+1}</title>
            <style>
                body {{
                    font-family: inherit;
                    line-height: inherit;
                    color: inherit;
                    background-color: transparent;
                    margin: 0;
                    padding: 0;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                }}
                th, td {{
                    border: 1px solid #555;
                    padding: 0.5em;
                }}
            </style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
