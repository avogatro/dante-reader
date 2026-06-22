import ctypes
from ctypes.wintypes import MSG
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QMainWindow

class BorderlessWindow(QMainWindow):
    """Base class for a borderless window that can be resized and dragged natively."""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinMaxButtonsHint)

    def nativeEvent(self, eventType, message):
        try:
            msg = MSG.from_address(int(message))
            if msg.message == 0x0083: # WM_NCCALCSIZE
                if msg.wParam:
                    return True, 0
            elif msg.message == 0x0084: # WM_NCHITTEST
                pos = self.mapFromGlobal(QCursor.pos())
                margin = 8
                
                left = pos.x() < margin
                right = pos.x() > self.width() - margin
                top = pos.y() < margin
                bottom = pos.y() > self.height() - margin
                
                if left and top:
                    return True, 13
                if right and top:
                    return True, 14
                if left and bottom:
                    return True, 16
                if right and bottom:
                    return True, 17
                if left:
                    return True, 10
                if right:
                    return True, 11
                if top:
                    return True, 12
                if bottom:
                    return True, 15
        except Exception:
            pass
        return False, 0

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            WS_CAPTION = 0x00C00000
            WS_MAXIMIZEBOX = 0x00010000
            WS_MINIMIZEBOX = 0x00020000
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            if not (style & WS_CAPTION):
                user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_CAPTION | WS_MAXIMIZEBOX | WS_MINIMIZEBOX)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027) # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
        except Exception:
            pass
