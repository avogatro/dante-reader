// Extracts text from the current selection or cursor to the end of the chapter, optionally restricting to a target class.
window.extractChapterText = function(targetClass) {
    var sel = window.getSelection();
    if (targetClass && document.querySelectorAll(targetClass).length === 0) {
        targetClass = '';
    }
    
    // Function to extract text from a specific target across all rows
    function extractDanteText(fromNode) {
        var cells = Array.from(document.querySelectorAll(targetClass));
        var startIndex = 0;
        if (fromNode) {
            var closestCell = fromNode.nodeType === 3 ? fromNode.parentElement.closest('td, .track-original, .track-translation') : fromNode.closest('td, .track-original, .track-translation');
            if (closestCell) {
                var tr = closestCell.closest('tr, .translation-row');
                if (tr) {
                    var targetCell = tr.querySelector(targetClass);
                    startIndex = cells.indexOf(targetCell);
                }
                if (startIndex === -1) startIndex = 0;
            }
        }
        
        var textPieces = [];
        for (var i = startIndex; i < cells.length; i++) {
            var cell = cells[i];
            var clone = cell.cloneNode(true);
            
            // Remove multimedia buttons, images, and superscripts (like [183])
            var elementsToRemove = clone.querySelectorAll('button, div[data-audio-id], div[data-video-id], img, sup, .linenum, .pagenum');
            elementsToRemove.forEach(function(el) { el.remove(); });
            
            // Add newlines to block elements so textContent doesn't crush lines together
            var blocks = clone.querySelectorAll('p, div, h1, h2, h3, h4, h5, h6, li');
            blocks.forEach(function(el) { el.appendChild(document.createTextNode('\n')); });
            var brs = clone.querySelectorAll('br');
            brs.forEach(function(el) { el.replaceWith('\n'); });
            
            var text = clone.textContent;
            if (text && text.trim().length > 0) {
                textPieces.push(text.trim());
            }
        }
        return textPieces.join('\n\n');
    }
    
    if (targetClass && document.querySelectorAll(targetClass).length > 0) {
        return extractDanteText(sel.anchorNode);
    } else {
        if (sel.rangeCount > 0) {
            if (!sel.isCollapsed) {
                // Selection is highlighted text, just return that
                var div = document.createElement('div');
                div.appendChild(sel.getRangeAt(0).cloneContents());
                var unwanted = div.querySelectorAll('button, div[data-audio-id], div[data-video-id], img, sup, .linenum, .pagenum');
                unwanted.forEach(function(el) { el.remove(); });
                return div.textContent;
            } else if (sel.anchorNode && document.body.contains(sel.anchorNode)) {
                // Read from cursor to end
                var range = document.createRange();
                range.setStart(sel.anchorNode, sel.anchorOffset);
                range.setEndAfter(document.body.lastChild || document.body);
                var fragment = range.cloneContents();
                var div = document.createElement('div');
                div.appendChild(fragment);
                
                var unwanted = div.querySelectorAll('button, div[data-audio-id], div[data-video-id], img, sup, .linenum, .pagenum');
                unwanted.forEach(function(el) { el.remove(); });
                
                var blocks = div.querySelectorAll('p, div, h1, h2, h3, h4, h5, h6, li');
                blocks.forEach(function(el) { el.appendChild(document.createTextNode('\n')); });
                var brs = div.querySelectorAll('br');
                brs.forEach(function(el) { el.replaceWith('\n'); });
                
                return div.textContent;
            }
        }
        var clone = document.body.cloneNode(true);
        var elementsToRemove = clone.querySelectorAll('button, div[data-audio-id], div[data-video-id], img, sup, .linenum, .pagenum');
        elementsToRemove.forEach(function(el) { el.remove(); });
        
        var blocks = clone.querySelectorAll('p, div, h1, h2, h3, h4, h5, h6, li');
        blocks.forEach(function(el) { el.appendChild(document.createTextNode('\n')); });
        var brs = clone.querySelectorAll('br');
        brs.forEach(function(el) { el.replaceWith('\n'); });
        
        return clone.textContent;
    }
};
