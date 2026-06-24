import os
import json
import pytest
from PyQt6.QtWebEngineWidgets import QWebEngineView

# Sample HTML from the user's bug report
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body class="dark-mode">
<div class="translation-row" data-trans-id="trans_0" style="display: flex; flex-direction: row; width: 100%; align-items: stretch; margin-bottom: 0.5em;"><div class="track-original" style="flex: 1; min-width: 0;"><p>unanswered too. "Where are we sailing? Tell me that." Jaime had made mention of the Free Cities, but had never said which one. "Is it Braavos? Tyrosh? Myr?" Tyrion would sooner have gone to Dorne. <em>Myrcella is older than Tommen, by Dornish law the Iron Throne is hers. I will help her claim her rights, as Prince Oberyn suggested</em> . </p></div><div class="track-translation" style="flex: 1; min-width: 0;"></div></div>
<div class="translation-row" data-trans-id="trans_1" style="display: flex; flex-direction: row; width: 100%; align-items: stretch; margin-bottom: 0.5em;"><div class="track-original" style="flex: 1; min-width: 0;"><p>Oberyn was dead, though, his head smashed to bloody ruin by the armored fist of Ser Gregor Clegane. And without the Red Viper to urge him on, would Doran Martell even consider such a chancy scheme? <em>He might clap me in chains instead and hand me back to my sweet sister</em> . The Wall might be safer. Old Bear Mormont said the Night's Watch had need of men like Tyrion. <em>Mormont might be dead, though. By now Slynt may be the lord commander</em> . That butcher's son was not like to have forgotten who sent him to the Wall. <em>Do I really want to spend the rest of my life eating salt beef and porridge with murderers and thieves?</em> Not that the rest of his life would last very long. Janos Slynt would see to that. </p></div><div class="track-translation" style="flex: 1; min-width: 0;"></div></div>
</body>
</html>
"""

def test_tts_extraction(qtbot):
    """
    Test that the chapter_text_extractor.js correctly extracts text
    from the QWebEngineView when called via python.
    """
    view = QWebEngineView()
    qtbot.addWidget(view)
    
    # 1. Load the JS file
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    js_path = os.path.join(app_dir, "assets", "js", "chapter_text_extractor.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    # 2. Inject the JS script into the HTML
    script_tag = f"<script id='chapter_text_extractor.js'>\n//<![CDATA[\n{js_code}\n//]]>\n</script>\n"
    html_with_js = SAMPLE_HTML.replace("</head>", f"{script_tag}</head>")
    
    # Wait for the page to finish loading
    with qtbot.waitSignal(view.loadFinished, timeout=5000):
        view.setHtml(html_with_js)

    # 3. Execute the extraction call (simulating reader_panel.py)
    extracted_text = None
    
    def callback(text):
        nonlocal extracted_text
        extracted_text = text

    target_selector = ".track-original"
    safe_target = json.dumps(target_selector)
    js_run = f"if (typeof window.extractChapterText === 'function') {{ window.extractChapterText({safe_target}); }} else {{ 'ERROR_NOT_DEFINED'; }}"
    
    view.page().runJavaScript(js_run, callback)
    
    # Wait until callback is fired
    qtbot.waitUntil(lambda: extracted_text is not None, timeout=2000)
    
    # Verify the results
    assert extracted_text != "ERROR_NOT_DEFINED", "The function was not defined!"
    assert extracted_text != "", "Extraction returned empty string!"
    assert "unanswered too." in extracted_text
    assert "Oberyn was dead, though" in extracted_text
    
    # Check that newlines were correctly preserved between block elements
    assert "suggested .\n\nOberyn was dead" in extracted_text

def test_tts_extraction_with_selection(qtbot):
    """
    Test what happens when a specific sentence is selected by the user.
    """
    view = QWebEngineView()
    qtbot.addWidget(view)
    
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    js_path = os.path.join(app_dir, "assets", "js", "chapter_text_extractor.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    script_tag = f"<script id='chapter_text_extractor.js'>\n//<![CDATA[\n{js_code}\n//]]>\n</script>\n"
    html_with_js = SAMPLE_HTML.replace("</head>", f"{script_tag}</head>")
    
    with qtbot.waitSignal(view.loadFinished, timeout=5000):
        view.setHtml(html_with_js)

    extracted_text = None
    def callback(text):
        nonlocal extracted_text
        extracted_text = text

    # Select the exact string "Myrcella is older than Tommen"
    js_select = """
    var ems = document.querySelectorAll('em');
    var targetNode = null;
    ems.forEach(em => {
        if (em.textContent.includes('Myrcella is older than Tommen')) {
            targetNode = em.firstChild;
        }
    });
    // Simulate a click (collapsed selection) at the start of "Myrcella is older than Tommen"
    var range = document.createRange();
    range.setStart(targetNode, 0);
    range.setEnd(targetNode, 0); // Collapsed range simulates a cursor click!
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    
    // Now run extraction
    var target_selector = ".track-original";
    if (typeof window.extractChapterText === 'function') { 
        window.extractChapterText(target_selector); 
    } else { 
        'ERROR_NOT_DEFINED'; 
    }
    """
    
    view.page().runJavaScript(js_select, callback)
    qtbot.waitUntil(lambda: extracted_text is not None, timeout=2000)
    
    # Verify that it correctly skipped the text before the cursor
    assert "unanswered too" not in extracted_text
    assert "Where are we sailing?" not in extracted_text
    
    # Verify it started exactly at the cursor
    assert extracted_text.startswith("Myrcella is older than Tommen")
    
    # Verify it continued to read the rest of the cell and the next cell
    assert "suggested .\n\nOberyn was dead" in extracted_text
    assert "Janos Slynt would see to that." in extracted_text

def test_tts_extraction_single_word_highlight(qtbot):
    """
    Test what happens when a single word is actively highlighted (selected).
    """
    view = QWebEngineView()
    qtbot.addWidget(view)
    
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    js_path = os.path.join(app_dir, "assets", "js", "chapter_text_extractor.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    script_tag = f"<script id='chapter_text_extractor.js'>\n//<![CDATA[\n{js_code}\n//]]>\n</script>\n"
    html_with_js = SAMPLE_HTML.replace("</head>", f"{script_tag}</head>")
    
    with qtbot.waitSignal(view.loadFinished, timeout=5000):
        view.setHtml(html_with_js)

    extracted_text = None
    def callback(text):
        nonlocal extracted_text
        extracted_text = text

    # Select the exact word "Braavos"
    js_select = """
    var ps = document.querySelectorAll('p');
    var targetNode = null;
    ps.forEach(p => {
        // Find the text node containing Braavos
        Array.from(p.childNodes).forEach(node => {
            if (node.nodeType === 3 && node.textContent.includes('Braavos')) {
                targetNode = node;
            }
        });
    });
    
    var range = document.createRange();
    var idx = targetNode.textContent.indexOf('Braavos');
    range.setStart(targetNode, idx);
    range.setEnd(targetNode, idx + 7); // Length of "Braavos"
    
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    
    // Now run extraction
    var target_selector = ".track-original";
    if (typeof window.extractChapterText === 'function') { 
        window.extractChapterText(target_selector); 
    } else { 
        'ERROR_NOT_DEFINED'; 
    }
    """
    
    view.page().runJavaScript(js_select, callback)
    qtbot.waitUntil(lambda: extracted_text is not None, timeout=2000)
    
    # We changed the logic so it ALWAYS reads continuously to the end of the chapter
    # even if you explicitly highlighted a specific word!
    assert extracted_text.startswith('Braavos? Tyrosh? Myr?" Tyrion would sooner have gone to Dorne.')
    assert "Myrcella is older than Tommen, by Dornish law the Iron Throne is hers." in extracted_text
    assert "suggested .\n\nOberyn was dead" in extracted_text
