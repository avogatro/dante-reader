"""
Configuration manager for the EPUB Reader application.
Loads API keys from config.json and manages user reading preferences.
"""

import json
import os

# Resolve paths relative to the project root (parent of app/)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_EPUBS_DIR = os.path.join(PROJECT_ROOT, "e-book")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
PREFS_PATH = os.path.join(PROJECT_ROOT, "app", "user_prefs.json")

# Default reading preferences
DEFAULT_PREFS = {
    "font_family": "Georgia",
    "font_size": 18,
    "line_height": 1.8,
    "page_width": 750,
    "last_book": None,
    "book_progress": {},
    "tts_skip_footnotes": True,
    "tts_voice_id": None,
    "tts_rate": 160,
    "window_width": 1400,
    "window_height": 900,
    "library_dir": None,
    "pdf_dark_mode": False,
}


def load_api_key() -> str:
    """Load the Gemini API key from config.json."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("gemini_api_key", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def load_prefs() -> dict:
    """Load user preferences, falling back to defaults for missing keys."""
    prefs = dict(DEFAULT_PREFS)
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        prefs.update(saved)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return prefs


def save_prefs(prefs: dict) -> None:
    """Persist user preferences to disk."""
    try:
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[config] Warning: could not save preferences: {e}")


def get_epubs_dir() -> str:
    """Get the user's preferred epubs directory, falling back to the default."""
    prefs = load_prefs()
    custom_dir = prefs.get("library_dir")
    if custom_dir and os.path.isdir(custom_dir):
        return custom_dir
    return DEFAULT_EPUBS_DIR

def get_max_width_px() -> int:
    """Return a large page width for full‑width layout.
    Uses the stored page_width preference or defaults to 2000px.
    """
    prefs = load_prefs()
    width = prefs.get("page_width", 750)
    return max(width, 2000)
