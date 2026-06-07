from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

class SyncBridge(QObject):
    """Bridge for QWebChannel to synchronize scroll between two WebEngineViews."""
    
    # Emits percentage (0.0 to 1.0)
    scroll_changed = pyqtSignal(float)

    @pyqtSlot(float)
    def update_scroll(self, percentage: float):
        self.scroll_changed.emit(percentage)
