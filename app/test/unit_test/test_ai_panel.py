import pytest
from PyQt6.QtWidgets import QApplication
from app.ai_panel import AiPanel

def test_ai_panel_format_response(qtbot):
    """Test that Markdown responses are properly converted and LaTeX arrows are handled."""
    panel = AiPanel()
    qtbot.addWidget(panel)
    
    # Test bold markdown
    html = panel._format_response("Hello **World**!")
    assert "<strong>World</strong>" in html
    assert "Hello" in html
    
    # Test LaTeX arrows replacement
    html_arrows = panel._format_response("A $\\rightarrow$ B $\\leftarrow$ C $\\Rightarrow$ D")
    assert "A → B ← C ⇒ D" in html_arrows
    assert "$\\rightarrow$" not in html_arrows

def test_ai_panel_display_error(qtbot):
    """Test that errors are formatted into the QTextBrowser securely."""
    panel = AiPanel()
    qtbot.addWidget(panel)
    
    panel._display_error("Network <Error> & failed")
    
    html = panel._response.toHtml()
    
    # The status label should update
    assert "failed" in panel._status_label.text().lower()
    
    # The text browser should contain escaped HTML
    assert "Network &lt;Error&gt; &amp; failed" in html
    # Buttons should be re-enabled
    assert panel._btn_explain.isEnabled() is True
