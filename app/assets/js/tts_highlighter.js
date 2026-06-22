// Encapsulates logic for finding and highlighting text passages during Text-to-Speech playback.
window.highlightTTS = function(text, targetClass) {
    // Clear previous hiliteColor spans and any leftover transparent spans
    var spans = document.querySelectorAll('span[style*="background-color: rgba(201, 169, 110, 0.4)"], span[style*="background-color: transparent"]');
    spans.forEach(el => {
        var parent = el.parentNode;
        while (el.firstChild) {
            parent.insertBefore(el.firstChild, el);
        }
        parent.removeChild(el);
    });
    
    if (text === '') return;
    
    var lines = text.split(/[\r\n]+/).map(s => s.trim()).filter(s => s.length > 0);
    if (lines.length === 0) return;
    
    var sel = window.getSelection();
    sel.removeAllRanges();
    
    var foundAny = false;
    document.designMode = 'on';
    
    for (var j = 0; j < lines.length; j++) {
        var searchStr = lines[j];
        var textsToTry = [searchStr, searchStr.replace(/\s+/g, ' ').trim()];
        var foundLine = false;
        
        var savedRange = null;
        if (sel.rangeCount > 0) {
            savedRange = sel.getRangeAt(0).cloneRange();
        }
        
        for (var i = 0; i < textsToTry.length; i++) {
            var tryStr = textsToTry[i];
            if (!tryStr) continue;
            
            if (i > 0) {
                sel.removeAllRanges();
                if (savedRange) {
                    sel.addRange(savedRange);
                }
            }
            
            var iterations = 0;
            while (iterations < 50) {
                var matched = window.find(tryStr, false, false, false, false, false, false);
                if (!matched) break; 
                
                if (targetClass) {
                    var node = window.getSelection().anchorNode;
                    var container = node ? (node.nodeType === 3 ? node.parentElement : node) : null;
                    if (container && container.closest(targetClass)) {
                        foundLine = true;
                        break;
                    }
                } else {
                    foundLine = true;
                    break;
                }
                iterations++;
            }
            
            if (foundLine) break;
        }
        
        if (foundLine) {
            foundAny = true;
            document.execCommand('hiliteColor', false, 'rgba(201, 169, 110, 0.4)');
            // Collapse to end so next line searches forward from here
            if (sel.rangeCount > 0) {
                sel.collapseToEnd();
            }
        }
    }
    
    document.designMode = 'off';
    
    if (foundAny) {
        // Scroll into view only if out of bounds, placing it near the top
        var currentSel = window.getSelection();
        if (currentSel.rangeCount > 0) {
            var range = currentSel.getRangeAt(0);
            var rect = range.getBoundingClientRect();
            var viewHeight = window.innerHeight || document.documentElement.clientHeight;
            
            var isVisible = rect.top >= 0 && (rect.bottom <= viewHeight || rect.height > viewHeight);
            if (!isVisible) {
                window.scrollBy({top: rect.top - 20, behavior: 'smooth'});
            }
        }
    }
};
