import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import app.qwen_engine as qwen_engine

@pytest.fixture
def mock_sounddevice():
    with patch("app.qwen_engine.sd.OutputStream") as mock_sd:
        yield mock_sd

@pytest.fixture
def mock_torch():
    with patch("app.qwen_engine.torch") as mock_t:
        # Prevent it from actually trying to use CUDA/CPU during tests
        mock_t.cuda.is_available.return_value = False
        yield mock_t

def test_qwen_engine_init(mock_sounddevice):
    """Test that QwenTTSEngine initializes and starts the hardware stream."""
    engine = qwen_engine.QwenTTSEngine()
    
    # Verify the audio stream was created and started
    mock_sounddevice.assert_called_once()
    assert mock_sounddevice.return_value.start.called
    
    # State flags
    assert engine.is_playing() is False
    assert engine.is_paused() is False
    assert engine._audio_queue.empty()

def test_qwen_audio_callback_underflow(mock_sounddevice):
    """Test the hardware callback correctly pads with zeros when queue is empty (underflow)."""
    engine = qwen_engine.QwenTTSEngine()
    
    # Request 2048 frames (the blocksize)
    outdata = np.empty((2048, 1), dtype='float32')
    
    # Call the hardware callback directly
    engine._audio_callback(outdata, 2048, None, None)
    
    # Verify the outdata was zeroed out (silence)
    assert np.all(outdata == 0.0)

def test_qwen_audio_callback_reads_queue(mock_sounddevice):
    """Test the callback reads from the queue if data is available."""
    engine = qwen_engine.QwenTTSEngine()
    
    # Push 1000 frames into the queue
    test_chunk = np.ones((1000, 1), dtype='float32')
    engine._audio_queue.put(test_chunk)
    
    # Request 2000 frames
    outdata = np.empty((2000, 1), dtype='float32')
    engine._audio_callback(outdata, 2000, None, None)
    
    # First 1000 should be 1.0, the rest should be 0.0
    assert np.all(outdata[:1000] == 1.0)
    assert np.all(outdata[1000:] == 0.0)

def test_qwen_engine_voices(mock_sounddevice):
    """Test that we can retrieve the predefined voices for Qwen."""
    engine = qwen_engine.QwenTTSEngine()
    voices = engine.get_available_voices()
    
    assert len(voices) > 0
    assert any("Aiden" in v["name"] for v in voices)
    assert any("Serena" in v["name"] for v in voices)
    
    engine.set_voice("serena")
    assert engine._speaker == "serena"
