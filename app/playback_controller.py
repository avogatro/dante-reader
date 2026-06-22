import os
import tempfile
from PyQt6.QtCore import QObject, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

class PlaybackController(QObject):
    """Manages audio and TTS playback for the reader window."""
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self._media_player = None
        self._audio_output = None
        self._current_media_id = None
        
    def _init_media_player(self) -> None:
        if self._media_player is not None:
            return
        
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.playbackStateChanged.connect(self._on_media_playback_state_changed)

    def _on_media_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState:
            if self._current_media_id:
                if hasattr(self.mw, '_reader') and self.mw._reader and hasattr(self.mw._reader, '_page'):
                    self.mw._reader._page.runJavaScript(f"if(window.setAudioButtonState) window.setAudioButtonState('{self._current_media_id}', false);")
                self._current_media_id = None

    def play_media_audio(self, media_id: str) -> None:
        """Play or toggle an embedded audio clip via QMediaPlayer."""
        self._init_media_player()
        
        # Toggle if it's the same media and currently playing
        if self._current_media_id == media_id and self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.stop()
            self.mw._statusbar.showMessage("Audio playback stopped")
            return

        if not self.mw._current_book or not getattr(self.mw._current_book, 'audio_clips', None):
            return
            
        audio_data = self.mw._current_book.audio_clips.get(media_id)
        if not audio_data:
            return
            
        filename = audio_data.get("file")
        if not filename:
            return
            
        # Stop TTS if it happens to be running
        self.tts_stop()
            
        # We must extract the audio from the zip to a temporary file,
        # because QMediaPlayer (FFmpeg) does not understand our custom 'epub://' scheme.
        try:
            audio_bytes = self.mw._current_book.get_asset(filename)
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"dante_audio_{media_id}.mp3")
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
            url = QUrl.fromLocalFile(temp_path)
        except Exception as e:
            self.mw._statusbar.showMessage(f"Error loading audio: {e}")
            return
            
        start_ms = int(audio_data.get("start_timestamp", 0) * 1000)
        title = audio_data.get("title", "Audio Clip")
        
        def start_playback():
            if start_ms > 0:
                self._media_player.setPosition(start_ms)
            self._media_player.play()
            self.mw._statusbar.showMessage(f"Playing audio: {title}")
            self._current_media_id = media_id
            if hasattr(self.mw, '_reader') and self.mw._reader and hasattr(self.mw._reader, '_page'):
                self.mw._reader._page.runJavaScript(f"if(window.setAudioButtonState) window.setAudioButtonState('{media_id}', true);")

        if self._media_player.source() == url:
            start_playback()
            return

        self._media_player.setSource(url)
        
        def on_media_status_changed(status):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                start_playback()
                self._media_player.mediaStatusChanged.disconnect(on_media_status_changed)
                
        self._media_player.mediaStatusChanged.connect(on_media_status_changed)

    def tts_play(self) -> None:
        """Start reading the current chapter aloud."""
        self.tts_stop()  # Stop any running TTS to prevent overlapping or jumping
        self.mw._is_reading_selection = False
        self.mw._reader.get_current_chapter_text(self._on_chapter_text_ready)

    def _on_chapter_text_ready(self, text: str) -> None:
        if text:
            self.mw._tts.speak_text(text)
            self.mw._statusbar.showMessage("TTS playing...")

    def tts_pause_resume(self) -> None:
        if self.mw._tts.is_paused():
            self.mw._tts.resume()
            self.mw._statusbar.showMessage("TTS resumed")
        elif self.mw._tts.is_playing():
            self.mw._tts.pause()
            self.mw._statusbar.showMessage("TTS paused")

    def tts_stop(self) -> None:
        self.mw._tts.stop()
        self.mw._statusbar.showMessage("TTS stopped")
        self.mw._reader.highlight_sentence("")

    def tts_read_selection(self, text: str = "") -> None:
        if not text:
            text = getattr(self.mw, "_last_selected_text", "")
        if text:
            self.mw._is_reading_selection = True
            self.mw._tts.stop()
            self.mw._tts.speak_text(text)
            self.mw._statusbar.showMessage("Reading selection...")

    def on_playback_finished(self) -> None:
        self.mw._statusbar.showMessage("TTS finished")
        self.mw._reader.highlight_sentence("")
        
        # Don't auto-advance if the user manually hit Stop
        if getattr(self.mw._tts, '_stop_flag', None) and self.mw._tts._stop_flag.is_set():
            return
            
        # Don't auto-advance if we were only reading a selection
        if getattr(self.mw, '_is_reading_selection', False):
            return
            
        if self.mw._prefs.get("tts_auto_next", False):
            # Start next chapter and resume reading
            self.mw._reader._next_chapter()
            # Slight delay to let the chapter load before extracting text
            QTimer.singleShot(1000, self.tts_play)
