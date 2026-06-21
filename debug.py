import sys
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication

def run():
    app = QApplication(sys.argv)
    try:
        from app.reader_window import ReaderWindow
        print("Imported ReaderWindow")
        w = ReaderWindow()
        print("Instantiated ReaderWindow")
    except Exception as e:
        print("CRASHED:", e)

if __name__ == '__main__':
    run()
