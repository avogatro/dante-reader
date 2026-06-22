// Provides helper functions for AI translation: finding visible paragraphs to translate and injecting translated HTML into the DOM.
window.translationHelper = {
    // Finds and returns an array of translation IDs for paragraphs currently visible in the viewport.
    getVisibleTransIds: function() {
        var rows = document.querySelectorAll('[data-trans-id]');
        var visibleIds = [];
        
        // Get viewport height with a 50% buffer above and below
        var buffer = window.innerHeight * 0.5;
        var topBound = -buffer;
        var bottomBound = window.innerHeight + buffer;
        
        for (var i = 0; i < rows.length; i++) {
            var rect = rows[i].getBoundingClientRect();
            // Check if row is within our buffered viewport
            if (rect.bottom > topBound && rect.top < bottomBound) {
                var id = rows[i].getAttribute('data-trans-id');
                if (id) {
                    visibleIds.push(id);
                }
            }
        }
        return visibleIds;
    },

    // Injects translated text into the DOM. Handles both Dante (table layout) and standard EPUB modes.
    injectTranslations: function(trans, isDante) {
        var parser = new DOMParser();
        
        for (var id in trans) {
            if (isDante) {
                var p = document.querySelector('p[data-trans-id="' + id + '"]');
                if (p) {
                    var td = p.closest('td');
                    if (td && td.classList.contains('track-text')) {
                        var tr = p.closest('tr');
                        if (tr) {
                            var ai_td = tr.querySelector('td.track-translation');
                            if (!ai_td) {
                                ai_td = document.createElement('td');
                                ai_td.className = 'track-translation';
                                tr.appendChild(ai_td);
                            }
                            var ai_p = ai_td.querySelector('p[data-trans-id="' + id + '_ai"]');
                            if (!ai_p) {
                                ai_p = document.createElement('p');
                                ai_p.className = 'line';
                                ai_p.setAttribute('data-trans-id', id + '_ai');
                                ai_td.appendChild(ai_p);
                            }
                            ai_p.innerHTML = trans[id];
                        }
                    }
                }
            } else {
                var el = document.querySelector('[data-trans-id="' + id + '"] .track-translation');
                if (el) {
                    try {
                        el.innerHTML = trans[id];
                    } catch (e) {
                        var doc = parser.parseFromString(trans[id], 'text/html');
                        el.innerHTML = '';
                        Array.from(doc.body.childNodes).forEach(node => {
                            el.appendChild(node.cloneNode(true));
                        });
                    }
                }
            }
        }
    }
};
