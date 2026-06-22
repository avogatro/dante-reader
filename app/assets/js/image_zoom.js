(function() {
    // Implements image click-to-zoom functionality with a centered fullscreen overlay.
document.addEventListener('click', function(e) {
        if (e.target.tagName.toLowerCase() === 'img') {
            // Check if already zoomed
            if (e.target.dataset.zoomed === 'true') {
                e.target.dataset.zoomed = 'false';
                e.target.style.position = '';
                e.target.style.top = '';
                e.target.style.left = '';
                e.target.style.width = '';
                e.target.style.height = '';
                e.target.style.maxWidth = '';
                e.target.style.maxHeight = '';
                e.target.style.zIndex = '';
                e.target.style.cursor = 'zoom-in';
                e.target.style.backgroundColor = '';
                e.target.style.objectFit = '';
            } else {
                // Zoom in
                e.target.dataset.zoomed = 'true';
                e.target.style.position = 'fixed';
                e.target.style.top = '0';
                e.target.style.left = '0';
                e.target.style.width = '100vw';
                e.target.style.height = '100vh';
                e.target.style.maxWidth = '100vw';
                e.target.style.maxHeight = '100vh';
                e.target.style.zIndex = '9999';
                e.target.style.cursor = 'zoom-out';
                e.target.style.backgroundColor = 'rgba(0,0,0,0.85)';
                e.target.style.objectFit = 'contain';
            }
        }
    });
})();
