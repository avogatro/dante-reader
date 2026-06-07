import pytest
from app.tts_engine import split_sentences, strip_footnote_markers

def test_strip_footnote_markers():
    """Test that bracketed and superscript footnote markers are stripped out."""
    assert strip_footnote_markers("Hello world[1].") == "Hello world."
    assert strip_footnote_markers("Dante[23] Alighieri") == "Dante Alighieri"
    assert strip_footnote_markers("No markers here.") == "No markers here."
    # Should handle multiple markers
    assert strip_footnote_markers("A[1] B[2] C[3]") == "A B C"

def test_split_sentences():
    """Test that paragraphs are broken into manageable sentences for the TTS engine."""
    text = "Hello world. How are you? I'm fine, thanks! Mr. Smith went to Washington."
    sentences = split_sentences(text)
    
    # We expect NLTK (or our regex fallback) to split them intelligently
    assert len(sentences) >= 3
    assert "Hello world." in sentences
    assert "How are you?" in sentences
    
    # Check that newlines break sentences
    text_with_newlines = "Line one.\nLine two.\n\nLine three."
    sentences2 = split_sentences(text_with_newlines)
    assert len(sentences2) == 3
    assert sentences2[0] == "Line one."
    assert sentences2[1] == "Line two."
    assert sentences2[2] == "Line three."

def test_split_sentences_handles_quotes():
    """Ensure dialogue isn't mangled."""
    text = '"Stop right there!" he yelled. "I won\'t," she replied quietly.'
    sentences = split_sentences(text)
    
    assert sentences[0].startswith('"Stop')
    assert len(sentences) == 2
