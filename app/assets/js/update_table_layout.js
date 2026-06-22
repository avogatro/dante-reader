// Updates the column visibility in table mode while maintaining the scroll position relative to a visible anchor element.
window.updateTableLayoutCss = function(cssStr) {
    // 1. Find an anchor element that is currently visible
    var anchor = null;
    var anchorOffset = 0;
    
    var elements = document.querySelectorAll('tr, p, h1, h2, h3, h4, h5, h6');
    for (var i = 0; i < elements.length; i++) {
        var el = elements[i];
        var rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        
        // Prefer elements that are genuinely in view
        if ((rect.top >= 0 && rect.top <= window.innerHeight / 2) || (rect.top < 0 && rect.bottom > window.innerHeight / 3)) {
            anchor = el;
            anchorOffset = rect.top;
            break;
        }
    }
    
    // 2. Update the style
    var styleId = 'table-column-toggles';
    var styleEl = document.getElementById(styleId);
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = styleId;
        var head = document.head || document.getElementsByTagName('head')[0] || document.documentElement;
        if (head) {
            head.appendChild(styleEl);
        }
    }
    styleEl.textContent = cssStr;
    
    // 3. Restore the relative scroll position
    if (anchor) {
        var restoreScroll = function() {
            var newRect = anchor.getBoundingClientRect();
            var diff = newRect.top - anchorOffset;
            if (diff !== 0 && Math.abs(diff) > 1) {
                window.scrollBy(0, diff);
            }
        };
        // Try multiple times as browser layout engines might defer the paint
        restoreScroll();
        requestAnimationFrame(function() {
            restoreScroll();
            setTimeout(restoreScroll, 50);
        });
    }
};
