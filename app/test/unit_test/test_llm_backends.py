import pytest
from unittest.mock import patch, MagicMock
from app.llm_backends import OllamaBackend, GeminiBackend

def test_ollama_backend_is_available():
    backend = OllamaBackend()
    
    # Mock a successful API response with models
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"models": [{"name": "llama3"}, {"name": "mistral"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        assert backend.is_available() is True
        assert backend.get_models() == ["llama3", "mistral"]
        
    # Mock a failed API response
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        assert backend.is_available() is False

def test_ollama_backend_generate():
    backend = OllamaBackend()
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"response": "Hello from Ollama!"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        result = backend.generate("Hello?", "llama3")
        assert result == "Hello from Ollama!"
        
        # Verify the request payload was correct
        req = mock_urlopen.call_args[0][0]
        assert "localhost:11434/api/generate" in req.full_url
        assert req.method == "POST"

def test_gemini_backend_initialization():
    backend = GeminiBackend(api_key="fake_key")
    assert backend.name == "Gemini (Cloud)"
    
    # We don't have the google-genai package installed in our test environment
    # or if we do, we want to mock it.
    with patch("app.llm_backends.HAS_GENAI", False):
        assert backend.is_available() is False
        
    # If we have no API key
    empty_backend = GeminiBackend(api_key="")
    with patch("app.llm_backends.HAS_GENAI", True):
        assert empty_backend.is_available() is False
