// Handles double-clicking text to automatically highlight the word for dictionary lookup.
document.addEventListener('dblclick', function(e) {
    var targetClass = e.target.closest('.track-text, .track-original');
    if (!targetClass) return;
    
    var selection = window.getSelection();
    if (!selection.rangeCount) return;
    
    var word = selection.toString().trim();
    if (word.length > 0) {
        window.location.href = "epub://action/dict?word=" + encodeURIComponent(word);
    }
});
