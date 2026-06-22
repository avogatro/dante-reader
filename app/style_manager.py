import os
from app.ui_utils import get_icon_path

# ── Color Palette ──
THEME = {
    "bg_darkest": "#0d1117",       # Window background
    "bg_dark": "#161b22",          # Panel backgrounds
    "bg_panel": "#1c2333",         # Card / sidebar backgrounds
    "bg_input": "#22293a",         # Input fields, code areas
    "border": "#30363d",           # Subtle borders
    "text_primary": "#e6e1d8",     # Warm off-white reading text
    "text_secondary": "#8b949e",   # Muted labels
    "text_dim": "#6e7681",         # Placeholder, disabled text
    "accent_gold": "#c9a96e",      # Parchment gold — primary accent
    "accent_hover": "#dfc08a",     # Gold hover state
    "accent_blue": "#58a6ff",      # Links, interactive highlights
    "selection_border": "#1f6feb", # Selection border for lists
    "scrollbar_bg": "#1c2333",
    "scrollbar_handle": "#30363d",
    "scrollbar_hover": "#484f58",
    "error_red": "#f85149",        # Error text
    "accent_gold_15": "rgba(201, 169, 110, 0.15)",
    "accent_gold_08": "rgba(201, 169, 110, 0.08)",
    "arrow_down_path": get_icon_path("chevron-down.svg").replace("\\", "/"),
}

def load_qss(filename: str) -> str:
    """Loads a QSS file and replaces @variables with theme colors."""
    filepath = os.path.join(os.path.dirname(__file__), "assets", "style", filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            qss = f.read()
            # Sort keys by length descending to prevent shorter keys (like @accent_gold) 
            # from partially replacing longer keys (like @accent_gold_15)
            sorted_theme = sorted(THEME.items(), key=lambda x: len(x[0]), reverse=True)
            for key, value in sorted_theme:
                qss = qss.replace(f"@{key}", value)
            return qss
    except Exception as e:
        print(f"Error loading QSS {filename}: {e}")
        return ""
