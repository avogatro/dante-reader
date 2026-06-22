// Constrains selection to a single column in table/grid mode, and identifies the translation track.
window.getConstrainedSelection = function() {
    var output = { text: '', track: '' };
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return JSON.stringify(output);
    
    var anchor = sel.anchorNode;
    if (!anchor) {
        output.text = window.getSelection().toString();
        return JSON.stringify(output);
    }
    
    var cell = anchor.nodeType === 3 ? anchor.parentElement.closest('[class*="track-"]') : anchor.closest('[class*="track-"]');
    if (!cell) {
        output.text = window.getSelection().toString();
        return JSON.stringify(output);
    }
    
    var className = Array.from(cell.classList).find(c => c.startsWith('track-'));
    if (!className) {
        output.text = window.getSelection().toString();
        return JSON.stringify(output);
    }
    
    output.track = className.replace('track-', '');
    
    var range = sel.getRangeAt(0);
    var fragment = range.cloneContents();
    
    var tempDiv = document.createElement('div');
    tempDiv.appendChild(fragment);
    
    var badCells = tempDiv.querySelectorAll('[class*="track-"]');
    badCells.forEach(node => {
        if (!node.classList.contains(className)) {
            node.remove();
        }
    });
    
    output.text = tempDiv.innerText.trim();
    return JSON.stringify(output);
};
