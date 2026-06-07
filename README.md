# Dante Reader

An advanced EPUB and PDF reader built with PyQt6, featuring integrated AI Translation and Text-to-Speech (TTS).

## Features
- **EPUB and PDF Support**: Fast and reliable rendering powered by PyQt6-WebEngine and PDF.js.
- **Dante Mode**: Specialized side-by-side reading layout (Original, IPA Pronunciation, Translation) for language learning.
- **AI Translation**: Seamlessly translate text passages or full pages using Google Gemini AI.
- **Text-to-Speech (TTS)**: High-quality offline TTS using `faster-qwen3-tts` or standard `pyttsx3`.
- **Distraction-Free Reading**: Hide toolbars and focus on the text.
- **Customization**: True dark mode for both EPUBs and PDFs, adjustable fonts, spacing, and layouts.

## Installation

### Prerequisites
- Python 3.14+
- Windows (Powershell) or Linux/macOS

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dante-reader
   ```

2. **Install core dependencies**
   ```bash
   pip install -r app/requirements.txt
   ```

3. **(Optional) Install Advanced TTS engine**
   If you want to use the high-quality Qwen3 TTS engine, install it separately:
   ```bash
   pip install faster-qwen3-tts
   ```

### Configuration
To enable AI translation features, you need a Google Gemini API Key.
Create a `config.json` file in the root of the project:
```json
{
  "gemini_api_key": "YOUR_API_KEY_HERE"
}
```

## How to Use

### Starting the App
Run the included PowerShell script:
```powershell
.\start_reader.ps1
```
Or start it manually via Python:
```bash
python -m app.main
```

### UI Overview
- **Library (📚)**: Toggle the left sidebar to browse and open your EPUBs and PDFs. Add custom library directories as needed.
- **Chapter Navigation**: Use the dropdown or `Prev`/`Next` buttons at the top to navigate chapters.
- **Focus (📖)**: Toggle distraction-free mode (hides all sidebars).
- **AI Panel (✨)**: Open the right sidebar to access AI translations and explanations.

### Dante Mode (Language Learning)
When reading specialized "Dante" books, a unique toolbar will appear at the top:
- Checkboxes to toggle **Original**, **IPA Pronunciation**, and **Translation** columns side-by-side.
- **Translate Page**: Automatically invoke AI translation for the currently visible section of the page.
- **TTS Target**: Choose which column (Original, IPA, Translation) the Text-to-Speech engine reads aloud from the dropdown.

### Text-to-Speech
- **Play/Stop**: Select any text on the page, right-click, and choose **"🔊 Play from here"** to begin reading aloud.
- **Settings**: Open the AI sidebar (✨) and navigate to the **TTS** tab to adjust voices, speech speed, or toggle the advanced AI Engine.

### PDF Reading
- Open any PDF directly from the Library sidebar.
- Enable **Dark Mode** inside the `View` menu, which instantly applies a deep navy theme to the viewer and intelligently inverts the PDF canvas for late-night reading.

### Advanced Extraction Modes
Dante Reader includes powerful text-extraction modes powered by `PyMuPDF` and `pymupdf4llm` to convert complex documents into clean, linear text. You can toggle these from the **View** menu:
- **PDF Reading Mode (Extract Text)**: Instead of rendering the PDF exactly as printed (via PDF.js), this mode extracts the raw markdown/text from the PDF, preserving tables and headers, and reflows it as standard HTML. This allows you to apply custom fonts, spacing, and TTS to PDFs just like an EPUB!
- **EPUB Markdown Extraction Mode**: Forces an EPUB file to be parsed through the Markdown extraction engine. This strips away complex, messy publisher layouts and CSS, rewriting the book into a clean, linear, and standardized format.
