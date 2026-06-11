"""
TTS Engine — Text-to-Speech wrapper with footnote-skip mode.
Uses pyttsx3 (SAPI5 on Windows) for instant, offline speech.
Supports sentence-by-sentence reading with signals for UI synchronization.
"""

import re
import threading
from typing import Optional

import pyttsx3
from app.interfaces import BaseTTSEngine


# Regex to match inline footnote markers like [137], [note], [*], etc.
_FOOTNOTE_PATTERN = re.compile(r"\[\d+\]|\[\*+\]|\[note\]", re.IGNORECASE)

# Simple sentence splitter (handles ., !, ? optionally followed by a closing quote, then space or end)
# _SENTENCE_SPLIT = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"'”’]))\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

def strip_footnote_markers(text: str) -> str:
    """Remove inline footnote markers like [137] from text."""
    return _FOOTNOTE_PATTERN.sub("", text)


def split_sentences(text: str, re_pattern=_SENTENCE_SPLIT) -> list[str]:
    """Split text into sentences for progressive reading."""
    sentences = []
    # Split by newlines first to prevent massive blocks from choking engines
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re_pattern.split(line)
        sentences.extend([p.strip() for p in parts if p.strip()])
    return sentences


class TTSEngine(BaseTTSEngine):
    """
    Thread-safe TTS engine wrapping pyttsx3.
    Implements BaseTTSEngine interface.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine: Optional[pyttsx3.Engine] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._paused = threading.Event()
        self._paused.set()  # Not paused initially
        self._skip_footnotes = True
        self._rate = 160
        self._voice_id: Optional[str] = None

    def _ensure_engine(self) -> pyttsx3.Engine:
        """Create or return the pyttsx3 engine (must be called from worker thread)."""
        engine = pyttsx3.init()
        engine.setProperty("rate", self._rate)
        if self._voice_id:
            engine.setProperty("voice", self._voice_id)
        return engine

    # ── Configuration ──

    def set_rate(self, rate: int) -> None:
        self._rate = rate

    def set_voice(self, voice_id: str) -> None:
        self._voice_id = voice_id

    def set_skip_footnotes(self, skip: bool) -> None:
        self._skip_footnotes = skip

    def get_available_voices(self) -> list[dict]:
        """Return list of available system voices (id, name, languages)."""
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            result = []
            for v in voices:
                result.append({
                    "id": v.id,
                    "name": v.name,
                    "languages": getattr(v, "languages", []),
                })
            engine.stop()
            return result
        except Exception as e:
            self.error.emit(f"Could not enumerate voices: {e}")
            return []

    # ── Playback Controls ──

    def speak_text(self, text: str) -> None:
        """Start reading text in a background thread."""
        self.stop()  # Stop any current playback

        print(f"[TTS ENGINE] speak_text called. Received raw text length: {len(text)}")
        if len(text) > 0:
            print(f"[TTS ENGINE] First 150 chars: {text[:150]!r}")

        sentences = split_sentences(text)
        if not sentences:
            self.playback_finished.emit()
            return

        self._stop_flag.clear()
        self._paused.set()
        self._thread = threading.Thread(
            target=self._worker, args=(sentences,), daemon=True
        )
        self._thread.start()

    def _worker(self, sentences: list[str]) -> None:
        """Worker thread: speak each sentence, checking for stop/pause."""
        try:
            for i, sentence in enumerate(sentences):
                if self._stop_flag.is_set():
                    break

                # Wait if paused
                self._paused.wait()
                if self._stop_flag.is_set():
                    break

                print(f"[TTS ENGINE] Speaking sentence {i+1}/{len(sentences)}: {sentence[:50]!r}...")

                # Emit raw sentence for UI highlighting
                self.sentence_started.emit(i, sentence)
                
                # Speak clean sentence
                speak_text = strip_footnote_markers(sentence) if self._skip_footnotes else sentence
                
                # We MUST initialize a fresh engine per-sentence. 
                # pyttsx3's runAndWait() on Windows (SAPI5) has a bug where it exhausts the 
                # COM message loop and skips subsequent say() calls if reused in a background thread loop.
                engine = pyttsx3.init()
                engine.setProperty("rate", self._rate)
                if self._voice_id:
                    engine.setProperty("voice", self._voice_id)
                
                engine.say(speak_text)
                engine.runAndWait()
                
                self.sentence_finished.emit(i)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.playback_finished.emit()

    def pause(self) -> None:
        """Pause playback (blocks worker thread at next sentence boundary)."""
        self._paused.clear()

    def resume(self) -> None:
        """Resume paused playback."""
        self._paused.set()

    def stop(self) -> None:
        """Stop playback completely."""
        self._stop_flag.set()
        self._paused.set()  # Unblock if paused so thread can exit
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_paused(self) -> bool:
        return not self._paused.is_set()
