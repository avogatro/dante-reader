# How to Add a New Voice

To add a new AI voice profile for Dante Reader's OmniVoice engine, you need to provide a high-quality audio sample of the voice and an exact transcript of what is being spoken in the audio. The AI model will use this short clip to clone the voice and reading style.

## 1. Prepare the Voice Sample (The `.wav` file)
You need a clear, high-quality audio clip of the target voice. The sample should ideally be around **15 to 20 seconds** long.

1. Obtain a clean recording of the voice.
2. Open the audio file in **Audacity** (or a similar audio editor).
3. **Clean up the audio:**
   - Remove background noise, hum, or static using Noise Reduction.
   - Delete any long pauses, breaths, coughs, or non-speech sounds.
   - Make sure the speech volume is normalized and clearly audible without distortion.
4. Export the cleaned audio as a `.wav` file.
5. Name the file clearly with an underscore format (e.g., `voice_name_language_accent.wav`).
6. Place the `.wav` file directly in this `voice/` folder.

## 2. Prepare the Transcript (The `.txt` file)
The AI engine needs to know exactly what is being spoken in the reference audio to align the vocal traits properly.

1. Listen to your cleaned `.wav` file very carefully.
2. Type out **exactly** what is spoken in the audio clip, word for word. Include punctuation (commas, periods, question marks) to help the AI understand the pacing and tone.
3. Save this transcript as a plain text file (`.txt`).
4. **Crucial:** The `.txt` file MUST have the exact same base name as the `.wav` file. 
   - *Example:* If your audio is `my_new_voice.wav`, your text file must be named `my_new_voice.txt`.
5. Place the `.txt` file alongside the `.wav` file in this `voice/` folder.

## 3. Using the New Voice
Once both files (e.g., `my_new_voice.wav` and `my_new_voice.txt`) are present in the `voice/` folder, restart Dante Reader. 

The OmniVoice engine will automatically detect the new files, and the voice will appear as an option in the application's TTS settings or Ribbon Bar drop-down menu!
