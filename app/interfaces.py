from abc import ABC, abstractmethod
from PyQt6.QtCore import QObject, pyqtSignal

class BaseTTSEngine(QObject):
    """
    Abstract Base Class for all Text-to-Speech engines.
    Ensures a consistent interface for the UI to interact with.
    """
    sentence_started = pyqtSignal(int, str)  # Emitted when a sentence begins (index, text)
    sentence_finished = pyqtSignal(int)      # Emitted when a sentence finishes (index)
    playback_finished = pyqtSignal()         # Emitted when all sentences have been read or stopped
    error = pyqtSignal(str)                  # Emitted on TTS errors

    @abstractmethod
    def speak_text(self, text: str) -> None:
        """Start speaking the given text."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Pause playback."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resume playback."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop playback entirely."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """Return True if currently generating or playing audio."""
        pass

    @abstractmethod
    def is_paused(self) -> bool:
        """Return True if currently paused."""
        pass

    @abstractmethod
    def get_available_voices(self) -> list[dict]:
        """Return a list of available voices. Format: [{'id': str, 'name': str, ...}]"""
        pass

    @abstractmethod
    def set_voice(self, voice_id: str) -> None:
        """Set the active voice."""
        pass

    @abstractmethod
    def set_rate(self, rate: int) -> None:
        """Set the playback rate."""
        pass
        
    @abstractmethod
    def set_skip_footnotes(self, skip: bool) -> None:
        """Toggle whether inline footnote markers are spoken."""
        pass


class LLMBackend(ABC):
    """
    Abstract Base Class for AI/LLM providers.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Display name for the backend (e.g. 'Ollama (Local)')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is currently available/reachable."""
        pass

    @abstractmethod
    def get_models(self) -> list[str]:
        """Retrieve a list of model names supported by this backend."""
        pass

    @abstractmethod
    def generate(self, prompt: str, model: str) -> str:
        """Generate a response synchronously. Should raise exceptions on error."""
        pass
