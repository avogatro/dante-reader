# 🐍 Dante EPUB Reader: PyQt6 Desktop Architecture

Welcome to the engineering documentation for the **Python/PyQt6 Desktop** iteration of the Dante EPUB Reader. This document outlines the vision for the native desktop application and frankly assesses the architectural trade-offs and drawbacks of the current implementation.

---

## 🏛️ Vision & Architecture

The Python migration was initiated to transform the project from a browser-bound web app into a deeply integrated, powerful desktop application. The core vision includes:

1. **Uncompromising Rendering via Chromium**: By using `QWebEngineView`, we retain the ability to render modern HTML5, MathML, and complex CSS layouts perfectly, without having to rebuild a typesetting engine from scratch.
2. **Native OS Integration**: Python allows us to interface directly with the local file system (for reading standard `.epub` zip archives natively without manual extraction), local hardware (system TTS engines via `pyttsx3`), and native window managers.
3. **Dual-Core AI Companion**: Deep integration with both cloud AI (Google Gemini) and local, privacy-first AI (Ollama running `gemma4:31b-cloud`), allowing users to highlight text and instantly receive translations or historical context.
4. **Custom Protocol Serving**: Implementing a custom `epub://` scheme handler allows Python to dynamically serve resources (HTML, images, CSS) directly out of memory from the parsed EPUB archive, providing a seamless "local web server" experience without actually opening any ports.

---

## ⚠️ Drawbacks & Architectural Friction (Current State)

While powerful, blending Python, Qt C++, and a Chromium Web Engine creates significant friction. The following are the major drawbacks and technical hurdles of the current state:

### 1. The Python / C++ Boundary (Use-After-Free Crashes)
Because PyQt6 is a Python wrapper around a C++ framework, memory management can be violently unpredictable. 
* **The Issue**: When the Chromium engine emits a signal (e.g., `navigationRequested` when a link is clicked), the C++ event loop pauses to let Python handle it. If Python modifies the WebEngine's state (like calling `setHtml()` to load a new chapter) *during* that handler, the C++ engine deletes the page objects while they are still being evaluated, resulting in an instant, uncatchable **Segmentation Fault**.
* **The Band-Aid**: Every UI modification triggered by a web event must be decoupled from the C++ call stack using `QTimer.singleShot(0)`.

### 2. The Chromium / Python Bridge (DOM Isolation)
We are running two entirely separate runtimes: the Python application logic and the V8 JavaScript engine inside Chromium.
* **The Issue**: Python cannot directly query the DOM. If we want to know what text the user highlighted, or if we want to scroll to a specific `#anchor`, we must inject JavaScript strings via `runJavaScript()` and wait for asynchronous callbacks.
* **The Impact**: This makes features like **TTS Word Highlighting** incredibly difficult. In a pure web app, JS can easily highlight words as they are spoken. In PyQt, the Python TTS engine cannot synchronously force the Chromium DOM to highlight words in real-time without severe latency or complex WebSocket bridging.

### 3. Resource Overhead
Embedding `QWebEngineView` means shipping an entire Chromium browser inside the application.
* **The Issue**: The memory footprint is massive (often 100MB+ just to render text). It consumes significantly more battery and CPU than a native `QTextBrowser` or a pure C++ renderer.

### 4. Custom Scheme CORS & Encoding Nightmares
Serving EPUB files from memory via the `epub://` protocol triggered massive security and encoding issues.
* **The Issue**: Web engines enforce strict Same-Origin Policies (CORS). Our custom scheme had to be carefully registered to bypass these blocks. Furthermore, Windows consoles use the `charmap` codec by default. If a Japanese EPUB title or a Unicode arrow (`→`) was parsed from the web engine and printed to the terminal by Python, it caused a hard `UnicodeEncodeError` that bypassed standard Python exception handling and instantly killed the Qt application.

### 5. Complex State Management
In a standard web app, the DOM *is* the state. In this PyQt app, state is fragmented:
* Python knows which chapter file is loaded.
* The Chromium DOM knows what line is currently visible on the screen.
* Keeping these two in sync (e.g., resizing the window changes pagination in CSS, which means Python's concept of the "current reading progress" becomes instantly invalidated) requires fragile, constant polling between Python and JS.

---
*Documented: June 2026*
