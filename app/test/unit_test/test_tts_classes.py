import pytest
from unittest.mock import patch, MagicMock
from app.tts_engine import TTSEngine

def test_tts_engine_init_and_state():
    engine = TTSEngine()
    
    assert engine.is_playing() is False
    assert engine.is_paused() is False
    
    engine.set_rate(200)
    assert engine._rate == 200

@patch("app.tts_engine.pyttsx3")
def test_tts_engine_available_voices(mock_pyttsx3):
    # Mock the pyttsx3 engine and its getProperty method
    mock_engine = MagicMock()
    
    mock_voice1 = MagicMock()
    mock_voice1.id = "voice_1"
    mock_voice1.name = "Test Voice 1"
    mock_voice1.languages = ["en_US"]
    
    mock_voice2 = MagicMock()
    mock_voice2.id = "voice_2"
    mock_voice2.name = "Test Voice 2"
    mock_voice2.languages = ["en_GB"]
    
    mock_engine.getProperty.return_value = [mock_voice1, mock_voice2]
    mock_pyttsx3.init.return_value = mock_engine
    
    engine = TTSEngine()
    voices = engine.get_available_voices()
    
    assert len(voices) == 2
    assert voices[0]["id"] == "voice_1"
    assert voices[1]["name"] == "Test Voice 2"

@patch("app.tts_engine.pyttsx3")
def test_tts_engine_pause_resume_stop(mock_pyttsx3, qtbot):
    engine = TTSEngine()
    
    # State flags test
    engine.pause()
    assert engine.is_paused() is True
    
    engine.resume()
    assert engine.is_paused() is False
    
    # Check stopping
    engine.stop()
    assert engine._stop_flag.is_set() is True
    assert engine.is_playing() is False
