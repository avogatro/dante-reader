import os
from PyQt6.QtGui import QIcon

_ICON_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")

def get_icon_path(icon_name: str) -> str:
    """Return the absolute path to an icon file."""
    if not icon_name.endswith(".svg"):
        icon_name += ".svg"
    return os.path.join(_ICON_DIR, icon_name).replace("\\", "/")

def get_icon(icon_name: str) -> QIcon:
    """Return a QIcon object for the given icon name."""
    return QIcon(get_icon_path(icon_name))
