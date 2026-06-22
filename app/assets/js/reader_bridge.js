// reader_bridge.js
// Javascript functions called from Python to control the reader view

window.readerBridge = {
    scrollToAnchor: function(anchor_id) {
        var el = document.getElementById(anchor_id);
        if (el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }
    },
    
    forceRepaint: function() {
        setTimeout(() => {
            window.scrollTo(0, 1); 
            window.scrollTo(0, 0);
            // Force a hardware compositor layer refresh
            if (document.body) {
                document.body.style.transform = 'translateZ(0)';
                setTimeout(() => document.body.style.transform = 'none', 50);
            }
        }, 50);
    },
    
    setPdfDarkMode: function(enabled) {
        document.body.classList.toggle('dark-mode', enabled);
    },
    
    resetPdfSettings: function() {
        localStorage.removeItem('pdfjs.preferences');
        localStorage.removeItem('pdfjs.history');
        try {
            PDFViewerApplicationOptions.set('defaultZoomValue', 'page-fit');
            PDFViewerApplicationOptions.set('spreadModeOnLoad', 0);
        } catch (e) {}
        // Prevent PDF.js from rewriting history during the unload event triggered by reload
        localStorage.setItem = function() {};
        location.reload();
    },
    
    getScrollPercent: function() {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        h = h > 0 ? h : 1;
        return window.scrollY / h;
    },
    
    scrollToPercent: function(pct) {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        h = h > 0 ? h : 1;
        window.scrollTo(0, pct * h);
    }
};
