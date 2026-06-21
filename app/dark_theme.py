"""
Dark theme QSS stylesheet for the EPUB Reader.
Deep navy-dark palette with parchment-gold accents, inspired by classical Dante aesthetics.
"""

from app.style_manager import THEME

# CSS injected into QWebEngineView for dark reading mode
READER_DARK_CSS = f"""
html, body {{
    background-color: {THEME['bg_darkest']} !important;
    color: {THEME['text_primary']} !important;
    min-height: 100vh !important;
}}

a {{
    color: {THEME['accent_blue']} !important;
}}

a:hover {{
    color: {THEME['accent_hover']} !important;
}}



/* Fix for EPUB covers using SVG with height 100% but no parent height */
svg[height="100%"] {{
    height: 95vh !important;
    width: auto !important;
    object-fit: contain !important;
}}

/* Footnote anchor styling */
a.fnanchor, a.pginternal {{
    color: {THEME['accent_gold']} !important;
    text-decoration: none !important;
    font-weight: bold;
    cursor: pointer;
}}

a.fnanchor:hover, a.pginternal:hover {{
    color: {THEME['accent_hover']} !important;
    text-decoration: underline !important;
}}

/* TTS highlight for currently-spoken sentence */
.tts-active {{
    background-color: rgba(201, 169, 110, 0.2) !important;
    border-radius: 3px;
    outline: 1px solid rgba(201, 169, 110, 0.4);
}}

/* Hide line and page numbers */
.linenum, .pagenum {{
    display: none !important;
}}

/* Selection styling */
::selection {{
    background-color: {THEME['accent_gold']} !important;
    color: {THEME['bg_darkest']} !important;
}}

/* Custom Dark Scrollbars */
::-webkit-scrollbar {{
    width: 14px;
    height: 14px;
}}
::-webkit-scrollbar-track {{
    background: {THEME['bg_darkest']}; 
}}
::-webkit-scrollbar-thumb {{
    background: {THEME['bg_dark']}; 
    border-radius: 7px;
    border: 3px solid {THEME['bg_darkest']};
}}
::-webkit-scrollbar-thumb:hover {{
    background: {THEME['accent_blue']}; 
}}
"""
