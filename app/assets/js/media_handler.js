// Handles interactive media (audio, video, footnotes) for Dante books by capturing clicks and dispatching to epub:// URLs.
(function() {
    // The global media object must be provided before this script runs (e.g., via window._dante_media).
    const media = window._dante_media || { audio: {}, video: {}, foot: {} };
    
    window.setAudioButtonState = function(id, isPlaying) {
        document.querySelectorAll('[data-audio-id]').forEach(el => {
            const btnId = el.getAttribute('data-audio-id');
            if (!media.audio[btnId]) return;
            
            if (btnId === id && isPlaying) {
                el.innerHTML = '<button class="media-btn">\u23F9 ' + media.audio[btnId].title + ' (Stop)</button>';
            } else {
                el.innerHTML = '<button class="media-btn">\u25B6 ' + media.audio[btnId].title + '</button>';
            }
        });
    };
    
    // Initial hydrate
    window.setAudioButtonState(null, false);
    
    document.querySelectorAll('[data-video-id]').forEach(el => {
        const id = el.getAttribute('data-video-id');
        if (media.video[id] && media.video[id].title) {
            el.innerHTML = '<button class="media-btn">\uD83C\uDFAC ' + media.video[id].title + '</button>';
        }
    });
    
    document.addEventListener('click', e => {
        const audioDiv = e.target.closest('[data-audio-id]');
        if (audioDiv) {
            window.location.href = 'epub://action/media?type=audio&id=' + audioDiv.getAttribute('data-audio-id');
            return;
        }
        
        const videoDiv = e.target.closest('[data-video-id]');
        if (videoDiv) {
            window.location.href = 'epub://action/media?type=video&id=' + videoDiv.getAttribute('data-video-id');
            return;
        }
        
        const footLink = e.target.closest('[data-foot-id]');
        if (footLink) {
            window.location.href = 'epub://action/media?type=foot&id=' + footLink.getAttribute('data-foot-id');
            return;
        }
    });
})();
