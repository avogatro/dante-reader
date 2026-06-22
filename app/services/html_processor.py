import re
import posixpath
import os

# We no longer strictly need READER_DARK_CSS here as it's part of StyleManager,
# but for WebView content, it might be easier to inject the QSS. Let's load the QSS.

class EpubHtmlProcessor:
    @staticmethod
    def process(html: str, chapter_file: str, settings: dict) -> str:
        """
        Process the raw HTML from EPUB to be ready for QWebEngineView.
        settings expects: 'page_width', 'font_family', 'font_size', 'line_height'
        """
        html = EpubHtmlProcessor._rewrite_asset_urls(html, chapter_file)
        html = EpubHtmlProcessor._inject_dark_css(html)
        html = EpubHtmlProcessor._inject_reading_style(html, settings)
        
        # Inject JavaScript dependencies
        html = EpubHtmlProcessor._inject_external_js(html, "dictionary.js")
        html = EpubHtmlProcessor._inject_external_js(html, "image_zoom.js")
        html = EpubHtmlProcessor._inject_external_js(html, "tts_highlighter.js")
        html = EpubHtmlProcessor._inject_external_js(html, "column_selection.js")
        html = EpubHtmlProcessor._inject_external_js(html, "chapter_text_extractor.js")
        html = EpubHtmlProcessor._inject_external_js(html, "update_table_layout.js")
        html = EpubHtmlProcessor._inject_external_js(html, "translation_helper.js")
        html = EpubHtmlProcessor._inject_external_js(html, "reader_bridge.js")
        
        html = EpubHtmlProcessor._inject_next_button(html)
        
        # Fix SVG attribute casing AFTER all BeautifulSoup manipulations have finished!
        html = re.sub(r'\bviewbox\s*=', 'viewBox=', html, flags=re.IGNORECASE)
        html = re.sub(r'\bpreserveaspectratio\s*=', 'preserveAspectRatio=', html, flags=re.IGNORECASE)
        
        return html

    @staticmethod
    def _inject_head_content(html: str, content: str) -> str:
        """Robustly inject content into the <head> section, handling self-closing tags."""
        if re.search(r'</head>', html, re.IGNORECASE):
            return re.sub(r'</head>', lambda m: f"{content}\n</head>", html, count=1, flags=re.IGNORECASE)
        elif re.search(r'<head\s*/>', html, re.IGNORECASE):
            return re.sub(r'<head\s*/>', lambda m: f"<head>\n{content}\n</head>", html, count=1, flags=re.IGNORECASE)
        elif re.search(r'<body', html, re.IGNORECASE):
            return re.sub(r'(<body[^>]*>)', lambda m: f"{content}\n" + m.group(1), html, count=1, flags=re.IGNORECASE)
        elif re.search(r'<html[^>]*>', html, re.IGNORECASE):
            return re.sub(r'(<html[^>]*>)', lambda m: m.group(1) + f"\n{content}\n", html, count=1, flags=re.IGNORECASE)
        else:
            return html + f"\n{content}"

    @staticmethod
    def _inject_external_js(html: str, js_filename: str) -> str:
        """Read a JS file from app/assets/js/ and inject it as an inline script."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "assets", "js", js_filename)
        if not os.path.exists(js_path):
            return html
        
        with open(js_path, "r", encoding="utf-8") as f:
            js_content = f.read()
            
        script_tag = f"\n<script id='{js_filename}'>\n//<![CDATA[\n{js_content}\n//]]>\n</script>\n"
        return EpubHtmlProcessor._inject_head_content(html, script_tag)

    @staticmethod
    def _inject_next_button(html: str) -> str:
        """Inject a 'Next' button at the bottom of the page."""
        btn_html = """
        <div style="text-align: center; margin-top: 100px; margin-bottom: 80px;">
            <a href="epub://action/next-chapter" style="text-decoration: none; padding: 36px 72px; border-radius: 16px; background: #444444; color: #e0e0e0; cursor: pointer; font-family: sans-serif; font-size: 48px; font-weight: bold; box-shadow: 0 8px 12px rgba(0,0,0,0.3);">Next »</a>
        </div>
        """
        if re.search(r'</body>', html, re.IGNORECASE):
            html = re.sub(r'</body>', lambda m: f"{btn_html}\n</body>", html, count=1, flags=re.IGNORECASE)
        else:
            html = html + f"\n{btn_html}"
        return html

    @staticmethod
    def _rewrite_asset_urls(html: str, chapter_file: str) -> str:
        """Rewrite relative asset URLs to use the epub:// scheme."""
        chapter_dir = posixpath.dirname(chapter_file)

        def replace_url(match):
            attr = match.group(1)
            url = match.group(2)
            quote = match.group(3)

            if url.startswith(("http://", "https://", "data:", "#", "epub://")):
                return match.group(0)

            if chapter_dir:
                resolved = posixpath.normpath(posixpath.join(chapter_dir, url))
            else:
                resolved = url

            return f'{attr}="epub://content/{resolved}{quote}'

        html = re.sub(r'(src|href)\s*=\s*"([^"]*?)(")', replace_url, html, flags=re.IGNORECASE)
        html = re.sub(r"(src|href)\s*=\s*'([^']*?)(')", replace_url, html, flags=re.IGNORECASE)
        return html

    @staticmethod
    def _inject_dark_css(html: str) -> str:
        """Inject dark mode CSS into the chapter HTML."""
        from app.dark_theme import READER_DARK_CSS # Keeping legacy READER_DARK_CSS since WebEngine doesn't support QSS variables easily
        dark_style = f"<style id='dark-reader-css'>\n/*<![CDATA[*/\n{READER_DARK_CSS}\n/*]]>*/\n</style>"
        return EpubHtmlProcessor._inject_head_content(html, dark_style)

    @staticmethod
    def _inject_reading_style(html: str, settings: dict) -> str:
        """Inject user-configurable reading styles (font, size, spacing)."""
        width_css = f"max-width: {settings['page_width']}px !important;" if settings['page_width'] > 0 else "max-width: 100% !important;"
        style = f"""
        <style id='reader-prefs-css'>
            /*<![CDATA[*/
            body {{
                font-family: "{settings['font_family']}", Georgia, "Times New Roman", serif !important;
                font-size: {settings['font_size']}px !important;
                line-height: {settings['line_height']} !important;
                {width_css}
                margin: 0 auto !important;
                padding: 30px 40px !important;
            }}
            p, div, span, li, td, th {{
                font-size: inherit !important;
                line-height: inherit !important;
            }}
            /*]]>*/
        </style>
        """
        return EpubHtmlProcessor._inject_head_content(html, style)
