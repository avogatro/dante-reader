# 📖 Dante Alighieri Interactive Reading Dashboard: Engineering Portfolio & Skill Sheet

Welcome to the engineering documentation and system architecture ledger of the **Dante Interactive eBook Reader & Companion**. This document outlines the core system vision, technical features, complex engineering problems solved, and specialized pair-programming skills developed throughout this project's lifecycle.

---

## 🏛️ System Vision & Core Philosophy

The goal of this project was to establish an **ultra-premium, fully offline-capable, single-page application (SPA)** for reading and analyzing Dante Alighieri’s *Divine Comedy*. The application represents a synthesis of classical typesetting aesthetics and modern interactive research tools:

1. **Aesthetics & Immersion**: Uses modern dynamic theming with automatic Light/Dark mode toggles and an auto-collapsible distraction-free reading UI.
2. **Neural Narration Continuity**: Features a highly optimized `faster-qwen3-tts` engine with real-time true token streaming, yielding a 0.5s Time To First Audio (TTFA) for fluid, selection-driven audiobook companionship.
3. **Interactive AI Research**: Includes a split-pane slide-out research panel providing offline translations, interactive historical footnotes, and local Gemini/Ollama AI verse explanations.
4. **Native Desktop Portability**: Engineered entirely using Python, PyQt6, and QtWebEngine to provide robust OS-level capabilities without relying on external browser dependencies.

---

## ⚡ Core Features Implemented

### 1. PyQt6 Native Desktop GUI & QtWebEngine
* **Native OS Integration**: Constructed a complete desktop UI with splitters, sidebars, and customizable theme settings using PyQt6.
* **QWebEngineView Injection**: Leveraged Qt's embedded Chromium engine to render standard EPUB XHTML files while injecting dynamic Dark Mode CSS and Python-to-JS bridge events on the fly via custom URL scheme handlers (`epub://`).
* **Typographical User Controls**: Engineered an adjustable reading column system, allowing users to dynamically switch between standard typography (~60-90 characters per line) and full-width rendering via settings.

### 2. High-Performance True Streaming TTS
* **Neural Architecture**: Implemented a fully localized text-to-speech companion using `faster-qwen3-tts` running on PyTorch CUDA.
* **Continuous Audio Streaming**: Engineered a custom zero-padded queue system for `sounddevice` to completely eliminate hardware pops and stutters. Yields audio in true real-time, completely bypassing the "sentence delay" typical in standard generative models.

### 3. Asynchronous AI Research & Footnote Extraction
* **Dynamic AI Backend Probing**: The AI Research Panel automatically probes local Ollama (`localhost:11434`) and remote Gemini API endpoints at launch in a background thread, decoupling UI rendering from blocking network calls.
* **Markdown Interpretation**: Upgraded the AI response engine to pipe outputs through the Python `markdown` library, correctly mapping rich markdown into HTML for the PyQt `QTextBrowser` widget.
* **Footnote Decoupling**: Automatically scrubs EPUB footnotes, intercepts click events natively, and maps them to a beautiful slide-out pane instead of forcing the user to navigate away from the chapter.

---

## 🛠️ Advanced Technical Problems Solved

### 🚨 Problem 1: SVG Cover Collapse & CSS Circular Dependency
* **Symptom**: Giant cover images inside e-books were displaying as only 150 pixels tall, cropping off 90% of the image. 
* **Solution**: Discovered a multi-layer WebKit SVG calculation bug. The HTML `<body>` lacked a defined height, causing the SVG's `height="100%"` to create a circular layout dependency. Applying `min-height: 100vh` to the body and switching the SVG to `width: 100%; height: auto` resolved the layout loop, anchoring the image to the window size.

### 🚨 Problem 2: Malformed EPUB Case-Sensitivity Crash
* **Symptom**: Even with the CSS fix applied, WebKit was still collapsing the SVG to exactly `150px`.
* **Solution**: Identified that older EPUB generators output `viewbox="..."` entirely in lowercase. Because SVG is parsed as XML, WebKit strictly demands CamelCase (`viewBox`). When it failed to parse the lowercase attribute, the SVG lost its aspect ratio, causing WebKit to aggressively fallback to a hardcoded `300x150` dimensionless minimum. Engineered a regex interceptor (`re.sub`) in the Python HTML injection pipeline to dynamically auto-correct malformed `viewbox` and `preserveaspectratio` attributes before they hit the rendering engine, instantly restoring perfect image scaling.

### 🚨 Problem 3: Hardware Audio Pops During Neural TTS Generation
* **Symptom**: Between streaming AI audio chunks and at the end of sentences, the hardware audio would click and pop unpleasantly.
* **Solution**: Realized that opening and closing `sounddevice.OutputStream` repeatedly caused hardware voltage drops. Restructured the neural TTS wrapper to keep a continuous output stream open at all times. Developed a `queue.Queue` buffer that yields perfect zeroes to the soundcard when the AI is processing, maintaining constant stream pressure and eliminating all audio artifacts.

---

## 🎓 Key Engineering Skills Demonstrated
* **Advanced PyQt6 Architecture**: Native window framing, complex QSplitter layouts, signal/slot concurrency, and deeply customized Qt widgets.
* **WebEngine Bridge Integration**: Fusing Python backends with Chromium frontend DOM interception using `QWebChannel` and custom URL schemes.
* **High-Performance Audio Streaming**: Managing thread-safe queues, zero-padding algorithms, and raw hardware audio stream callbacks via `sounddevice`.
* **Asynchronous AI Engineering**: Integrating live CUDA-accelerated neural networks (`faster-qwen3-tts`), REST APIs (Gemini/Ollama), and chunk-based streaming in non-blocking background threads.

---

## 🚀 Advanced TTS & UI Integration (Phase 2)

### 🏆 Phase 2 Achievements

1. **Continuous Neural TTS Streaming**
   - Successfully integrated Alibaba's `Qwen3-TTS` neural network via `faster-qwen3-tts`.
   - Built a robust, multithreaded audio pipeline using `sounddevice.OutputStream` that constantly streams data to the hardware, using zero-padding to completely eliminate audio popping/clicking artifacts between sentences.
   - Exposed all 9 internal synthetic voices (Aiden, Ryan, Serena, Vivian, etc.) to the user interface.

2. **Advanced TTS Playback Controls**
   - Implemented intelligent "Cursor-to-EOF" text extraction using `window.getSelection()` bridging, allowing the user to start TTS from any arbitrary point in the chapter.
   - Added an "Auto-Continue Next Chapter" feature that seamlessly loads the next chapter and resumes reading, *only* if the user was reading a full chapter and hadn't manually hit stop.
   
3. **Live DOM Synchronization & Highlighting**
   - Bridged the Python TTS engine and the JavaScript DOM.
   - Using `document.execCommand('hiliteColor')` and `window.find()`, the app dynamically highlights the exact sentence currently being synthesized in real-time.
   - Engineered an elegant auto-scrolling algorithm that uses `range.getBoundingClientRect()` to only adjust the page if the active sentence leaves the visible viewport, anchoring it to the top.

4. **Premium UI/UX Polish**
   - Added a "Focus Mode" to cleanly toggle sidebars.
   - Removed arbitrary max-widths to allow full edge-to-edge reading.
   - Enhanced the library panel to support up to 3 lines for longer book titles.
   - Upgraded the default base font sizes for better readability.

### 🧠 Phase 2 Lessons Learned

> [!CAUTION]
> **Qt QSS Parser Limitations with SVGs**
> When trying to style the dropdown arrow of a `QComboBox`, we learned that Qt's QSS engine is notoriously buggy when parsing raw `utf8` SVG strings inline, often falling back to black or failing entirely. 
> **Lesson:** Always use **Base64 encoded** SVG strings inside QSS `url("data:image/svg+xml;base64,...")` to guarantee flawless cross-platform rendering of UI icons.

> [!TIP]
> **WebEngine Compositor Stalling on Local Protocols**
> We discovered that `QWebEngineView` has a bug where it occasionally stalls its compositor when navigating via custom schemes (`epub://`), resulting in stale or black pages (like the cover image bug).
> **Lesson:** A reliable workaround is injecting a zero-pixel CSS hardware transform (`document.body.style.transform = 'translateZ(0)'`) and removing it via a `QTimer` to force the compositor to repaint the screen.

> [!IMPORTANT]
> **Extracting DOM Text with Native Spacing**
> Standard `range.toString()` strips out critical paragraph newlines, breaking sentence tokenization for the TTS.
> **Lesson:** To get properly newline-formatted text from a specific cursor position to the end of a document, clone the DOM range into a hidden `<div>` and read its `.innerText`.

> [!TIP]
> **Smart Auto-Scrolling**
> Forcing a `scrollIntoView({block: 'center'})` on every sentence causes a jarring, seasick reading experience.
> **Lesson:** Always use `range.getBoundingClientRect()` to calculate visibility relative to the viewport. Only issue a `window.scrollBy` if `rect.top < 0` or `rect.bottom > window.innerHeight`.

---

## 📚 PDF Integration & Chromium Storage Nuances (Phase 3)

### 🏆 Phase 3 Achievements

1. **Native PDF.js Bundling**
   - Successfully integrated a complete offline build of Mozilla's PDF.js to avoid the restrictive security sandbox of Qt's default Chrome PDF viewer.
   - Preserved full text-selection capabilities, ensuring that both the neural TTS engine and the AI Research Panel function flawlessly on PDFs exactly as they do on EPUBs.
2. **Dynamic UI/CSS Injection**
   - Injected global dark mode scrollbars and deep navy-gray (`#0d1117`) backgrounds into the PDF.js renderer natively.
   - Built a custom "PDF Dark Mode" filter toggle (`invert(1) hue-rotate(180deg)`) for the document canvas.
3. **Advanced State Fingerprinting**
   - Restructured the global application state to save `book_progress` on a per-document basis.
   - Automatically mapped PDF.js's native fingerprinting system to persist exact zoom preferences, scroll positions, and page numbers across restarts.

### 🧠 Phase 3 Lessons Learned

> [!WARNING]
> **The PyQt6 Default Profile "Incognito" Bug**
> **Symptom:** `QWebEngineProfile.defaultProfile()` silently ignored commands to set a persistent storage path, completely failing to save `localStorage` data across restarts.
> **Diagnosis:** In PyQt6, `defaultProfile()` natively initializes as an `OffTheRecord` (Incognito) profile. Any commands sent to it to establish a persistent SQLite database are quietly ignored.
> **Lesson:** To establish true persistence and prevent Chromium from wiping its memory on close, developers *must* instantiate a named profile (e.g., `QWebEngineProfile("MyProfileName")`), which inherently forces Chromium to spin up a physical LevelDB database in the user's `AppData` folder.

> [!CAUTION]
> **The PDF.js `unload` Race Condition**
> **Symptom:** When programmatically wiping PDF.js `localStorage` and calling `location.reload()`, the settings would instantly revert back to their old state.
> **Diagnosis:** Calling a reload fires a DOM `pagehide` and `unload` event. PDF.js listens for these events and aggressively tries to write its *current* in-memory state back to `localStorage` just milliseconds before the page actually refreshes, perfectly undoing any `localStorage.removeItem()` calls made right before it.
> **Lesson:** When wiping a Chromium backend state programmatically, you must temporarily gag the saving mechanisms (e.g., overriding `localStorage.setItem = function() {};`) before issuing a reload to prevent phantom writes.

> [!TIP]
> **PDF.js Global vs Fallback Preferences**
> **Symptom:** Injecting `spreadModeOnLoad: 0` into `pdfjs.preferences` via `localStorage` forced all PDFs to open in Single Page mode, permanently disabling the user's ability to save an "Even Spreads" preference.
> **Diagnosis:** In PDF.js, injecting preferences directly into `pdfjs.preferences` creates a hard global override for certain properties, overriding `pdfjs.history`.
> **Lesson:** To gracefully establish a fallback (like "Page Fit") without steamrolling user history, use `PDFViewerApplicationOptions.set('defaultZoomValue', 'page-fit');` within the `webviewerloaded` listener. It acts as a memory-only baseline that happily yields to any saved document history.

---

## 🏛️ Multi-Track Synchronous Formats & Dynamic UI (Phase 4)

### 🏆 Phase 4 Achievements

1. **The `.dante` Multi-Track Format**
   - Engineered a bespoke e-book container format (`.dante`) specifically optimized for comparative reading.
   - Merged separated JSON translations (Original Italian, Longfellow English, IPA pronunciation) into a unified block-level data structure.
   - Built a dynamic `DanteBook` loader that parses `.dante` zip files and synthesizes rich HTML on-the-fly for any combination of translation tracks, bypassing static EPUB spine requirements.
2. **Dynamic Tri-Panel Reading UI**
   - Expanded the core `reader_panel.py` from a dual-pane setup to a robust, dynamically sizing 3-pane `QSplitter` layout.
   - Implemented a unified Dante Control Bar with instantaneous checkboxes to toggle the visibility of Italian, English, and IPA panels without triggering expensive HTML re-renders or breaking the user's scroll state.
3. **Omni-Channel Scroll Synchronization**
   - Generalized the `SyncBridge` mechanism to broadcast scroll events across all three WebEngine instances synchronously.
4. **Decoupled TTS Engine Targets**
   - Implemented an independent "TTS Target" dropdown, enabling the `faster-qwen3-tts` engine to extract text and synthesize audio for a specific track (e.g., IPA or English) *even if that track's panel is currently hidden* by the user.

### 🧠 Phase 4 Lessons Learned

> [!TIP]
> **Headless DOM Text Extraction**
> **Symptom:** If a user disabled the IPA visual panel but selected IPA for TTS generation, the application failed to extract the text because standard extraction relied on querying the visible active `QWebEnginePage`.
> **Solution:** `QWebEngineView.setVisible(False)` does not destroy the underlying DOM; it only hides the compositor layer. By eagerly loading the synthesized HTML into all 3 web engines regardless of their checkbox visibility, we achieved true "headless" text extraction. The TTS engine can safely execute its JavaScript text-grabbing routines against the invisible panes flawlessly.


### 🏆 Phase 5 Achievements

1. **In-place EPUB Translation with Gemini**
   - Implemented dynamic DOM translation injection for any standard EPUB file without requiring the .dante format.
   - Built a background TranslationManager that streams translated blocks into a JSON cache, ensuring the UI remains responsive and API costs are minimized through caching.
2. **Translation API Robustness & Error Handling**
   - Corrected multiple complex Python binding issues, such as rogue inline rom PyQt6.QtCore import QTimer imports that caused standard EPUB link navigation handlers to fail with UnboundLocalError.
   - Engineered state locks (_translating_chapters = set()) inside the asynchronous translation workers to prevent race conditions and duplicate API requests if users rapid-fire the translation button.
   - Implemented deep visual UI indicators (e.g. ⏳ Translating... button states) and bubbled backend threading exceptions up to strict Qt WebEngine visual popups for immediate feedback when API connections fail.
3. **SVG Rendering Quirks & Aspect Ratio Preservation**
   - Fixed catastrophic EPUB cover image distortions inside QtWebEngine caused by standard EPUB generators lowercasing strict XML attributes (iewbox and preserveaspectratio).
   - Built a Regex pre-processor within the HTML injection pipeline to repair tag capitalization safely **after** BeautifulSoup has completely finished parsing and formatting the translation blocks.

### 💡 Phase 5 Lessons Learned

> [!TIP]
> **BeautifulSoup Attribute Casing Quirks**
> **Symptom:** Regex replacements converting iewbox to iewBox inside EPUB HTML appeared to randomly fail and revert back to lowercase when rendered in the Chromium engine.
> **Solution:** BeautifulSoup, when initialized with the standard html.parser, forcefully lowercases all element attributes by design. If raw string regex manipulation (like fixing camelCase XML attributes) occurs *before* a BeautifulSoup pass (e.g., to inject translation IDs), BeautifulSoup will completely overwrite the case-sensitive fixes. Always run raw string HTML patches **after** all DOM-tree parsing libraries have finished executing.

