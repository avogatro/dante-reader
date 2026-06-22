from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineCore import QWebEnginePage
from app.ui_utils import get_icon

class ReaderContextMenu:
    @staticmethod
    def show_menu(reader_panel, pos):
        """Build and show the custom right-click context menu for the reader."""
        menu = QMenu(reader_panel)

        page = reader_panel._web.page()
        copy_action = page.action(QWebEnginePage.WebAction.Copy)
        copy_action.setText(reader_panel.tr("Copy") + "\tCtrl+C")
        copy_action.setIcon(get_icon("copy.svg"))
        copy_action.setShortcut("Ctrl+C")
        
        select_all_action = page.action(QWebEnginePage.WebAction.SelectAll)
        select_all_action.setText(reader_panel.tr("Select All") + "\tCtrl+A")
        select_all_action.setIcon(get_icon("select_all.svg"))
        select_all_action.setShortcut("Ctrl+A")
        
        menu.addAction(copy_action)
        menu.addAction(select_all_action)
        menu.addSeparator()

        # View Page Source
        source_action = QAction(get_icon("code.svg"), reader_panel.tr("View Page Source"), reader_panel)
        source_action.setShortcut("Ctrl+U")
        source_action.triggered.connect(reader_panel._open_source_viewer)
        menu.addAction(source_action)

        selected_text = reader_panel._page.selectedText().strip()
        if selected_text:
            menu.addSeparator()
            
            read_sel_action = QAction(get_icon("read.svg"), reader_panel.tr("Read Selected Text"), reader_panel)
            read_sel_action.setShortcut("Ctrl+Shift+S")
            read_sel_action.triggered.connect(lambda: reader_panel.read_selection_requested.emit(selected_text))
            menu.addAction(read_sel_action)
            
            explain_action = QAction(get_icon("explain.svg"), reader_panel.tr("AI Explain"), reader_panel)
            explain_action.setShortcut("Ctrl+E")
            explain_action.triggered.connect(reader_panel.ai_explain_requested.emit)
            menu.addAction(explain_action)
            
            translate_action = QAction(get_icon("translate.svg"), reader_panel.tr("AI Translate"), reader_panel)
            translate_action.setShortcut("Ctrl+T")
            translate_action.triggered.connect(reader_panel.ai_translate_requested.emit)
            menu.addAction(translate_action)
            
        else:
            menu.addSeparator()
            bm_action = QAction(get_icon("bookmark.svg"), reader_panel.tr("Add Bookmark"), reader_panel)
            bm_action.setShortcut("Ctrl+B")
            bm_action.triggered.connect(reader_panel._trigger_add_bookmark)
            menu.addAction(bm_action)
            
        note_action = QAction(get_icon("note.svg"), reader_panel.tr("Add Note"), reader_panel)
        note_action.setShortcut("Ctrl+N")
        note_action.triggered.connect(lambda: reader_panel._trigger_add_note(selected_text))
        menu.addAction(note_action)
            
        menu.addSeparator()

        if selected_text and " " not in selected_text and len(selected_text) < 30:
            dict_action = QAction(get_icon("book-a.svg"), reader_panel.tr("Dictionary Lookup"), reader_panel)
            dict_action.triggered.connect(lambda: reader_panel.dictionary_lookup_requested.emit(selected_text))
            menu.addAction(dict_action)
            
        menu.addSeparator()
        play_action = QAction(get_icon("play.svg"), reader_panel.tr("Play from Cursor / Play Chapter"), reader_panel)
        play_action.setShortcut("F5")
        play_action.triggered.connect(reader_panel.play_chapter_requested.emit)
        menu.addAction(play_action)
        
        stop_action = QAction(get_icon("stop.svg"), reader_panel.tr("Stop TTS") + "\tF7", reader_panel)
        stop_action.setShortcut("F7")
        stop_action.triggered.connect(reader_panel.stop_tts_requested.emit)
        menu.addAction(stop_action)
        
        menu.addSeparator()
        prev_action = QAction(get_icon("prev.svg"), reader_panel.tr("Previous Page") + "\tLeft", reader_panel)
        prev_action.setShortcut("Left")
        prev_action.triggered.connect(reader_panel.prev_chapter_requested.emit)
        menu.addAction(prev_action)
        
        next_action = QAction(get_icon("next.svg"), reader_panel.tr("Next Page") + "\tRight", reader_panel)
        next_action.setShortcut("Right")
        next_action.triggered.connect(reader_panel.next_chapter_requested.emit)
        menu.addAction(next_action)

        menu.exec(reader_panel._web.mapToGlobal(pos))
