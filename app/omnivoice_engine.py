"""
OmniVoice Engine — Neural Text-to-Speech wrapper using OmniVoice.
Uses sounddevice to stream live audio.
"""

import logging
import threading
import queue
import os
from typing import Optional
import numpy as np
import sounddevice as sd
from app.interfaces import BaseTTSEngine

from .tts_engine import split_sentences, strip_footnote_markers

try:
    import torch
    from omnivoice import OmniVoice
    OMNIVOICE_AVAILABLE = True
except ImportError:
    OMNIVOICE_AVAILABLE = False


class OmniVoiceTTSEngine(BaseTTSEngine):
    """
    OmniVoice TTS engine wrapper supporting audio playback via sounddevice queue.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[OmniVoice] = None
        self._thread: Optional[threading.Thread] = None
        self._player_thread: Optional[threading.Thread] = None
        
        self._stop_flag = threading.Event()
        self._paused = threading.Event()
        self._paused.set()  # Not paused initially
        
        self._skip_footnotes = True
        self._speaker = "jiang_voice"
        self._model_id = "k2-fsa/OmniVoice"
        self._sample_rate = 24000 # OmniVoice synthesizes at 24kHz
        
        # Audio Streaming State
        self._audio_queue = queue.Queue()
        self._audio_buffer = np.zeros((0, 1), dtype='float32')
        self._generation_queue = queue.Queue(maxsize=3)
        
        # Default reference info
        self._ref_audio = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'voice', 'jiang_voice.wav'))
        self._ref_text = "Because Russia and Ukraine export a lot of grain to these places. These places are not food independent. They rely on fertilizer. They rely on food imports."
        self.set_voice("jiang_voice")
        
        # Continuous hardware stream to prevent hardware pops
        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback,
            blocksize=2048
        )
        self._stream.start()
        
        # Start model initialization in the background immediately
        threading.Thread(target=self._init_model_bg, daemon=True).start()

    def _audio_callback(self, outdata, frames, time, status):
        """Called by sounddevice on a high-priority hardware thread to fetch audio frames."""
        needed = frames
        
        # Pull chunks from the queue until we have enough frames
        while len(self._audio_buffer) < needed:
            try:
                chunk = self._audio_queue.get_nowait()
                self._audio_buffer = np.concatenate([self._audio_buffer, chunk])
            except queue.Empty:
                break
                
        if len(self._audio_buffer) >= needed:
            # We have enough data! Feed the hardware.
            outdata[:] = self._audio_buffer[:needed]
            self._audio_buffer = self._audio_buffer[needed:]
        else:
            # Underflow (queue is empty). Play what we have, then fill the rest with absolute silence (zeros).
            have = len(self._audio_buffer)
            if have > 0:
                outdata[:have] = self._audio_buffer
            outdata[have:] = 0.0
            self._audio_buffer = np.zeros((0, 1), dtype='float32')

    def _init_model_bg(self) -> None:
        try:
            self._ensure_model()
        except Exception as e:
            logging.error(f"Failed to background init OmniVoice model: {e}")

    def _ensure_model(self) -> OmniVoice:
        if self._model is None:
            if not OMNIVOICE_AVAILABLE:
                raise ImportError("omnivoice is not installed.")
                
            if torch.cuda.is_available():
                device = "cuda:0"
                dtype = torch.bfloat16
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
                dtype = torch.float16
            else:
                device = "cpu"
                dtype = torch.float32
            
            logging.info("[OMNIVOICE TTS] Loading OmniVoice model...")
            self._model = OmniVoice.from_pretrained(
                self._model_id,
                device_map=device,
                dtype=dtype
            )
            
            # Warm up
            logging.info("[OMNIVOICE TTS] Warming up...")
            if os.path.exists(self._ref_audio):
                try:
                    self._model.generate(
                        text="warmup", 
                        ref_audio=self._ref_audio, 
                        ref_text=self._ref_text
                    )
                except Exception:
                    pass
            logging.info("[OMNIVOICE TTS] Warmup complete! Engine ready.")
            
        return self._model

    def set_voice(self, voice_id: str) -> None:
        self._speaker = voice_id
        voice_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'voice'))
        voice_path = os.path.join(voice_dir, f"{voice_id}.wav")
        text_path = os.path.join(voice_dir, f"{voice_id}.txt")
       
        if os.path.exists(voice_path):
            self._ref_audio = voice_path
            
            target_path = text_path if os.path.exists(text_path) else None
            if target_path:
                try:
                    with open(target_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip().strip('"\'')
                        if content:
                            self._ref_text = content
                except Exception as e:
                    logging.error(f"Failed to load ref text for {voice_id}: {e}")

    def set_skip_footnotes(self, skip: bool) -> None:
        self._skip_footnotes = skip
        
    def set_rate(self, rate: int) -> None:
        pass

    def get_available_voices(self) -> list[dict]:
        # Quick scan of voice directory
        voices = []
        voice_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'voice'))
        if os.path.exists(voice_dir):
            for file in os.listdir(voice_dir):
                if file.endswith('.wav'):
                    vid = file[:-4]
                    voices.append({"id": vid, "name": vid.replace('_', ' ').title()})
        if not voices:
            voices.append({"id": "jiang_voice", "name": "Jiang Voice"})
        return voices

    # ── Playback Controls ──

    def speak_text(self, text: str) -> None:
        self.stop()  # Stop any current playback

        raw_sentences = split_sentences(text)
        if not raw_sentences:
            self.playback_finished.emit()
            return
            
        # Tuple mapping as requested: (raw_text for UI, clean_text for TTS)
        sentences_map = []
        for raw in raw_sentences:
            clean = strip_footnote_markers(raw) if self._skip_footnotes else raw
            sentences_map.append((raw, clean))

        self._stop_flag.clear()
        self._paused.set()
        
        # Clear generation queue
        while not self._generation_queue.empty():
            try:
                self._generation_queue.get_nowait()
            except queue.Empty:
                break
                
        self._thread = threading.Thread(
            target=self._worker, args=(sentences_map,), daemon=True
        )
        self._thread.start()
        
        self._player_thread = threading.Thread(
            target=self._player, daemon=True
        )
        self._player_thread.start()

    def _worker(self, sentences_map: list[tuple[str, str]]) -> None:
        try:
            model = self._ensure_model()
            
            for i, (raw_sentence, clean_sentence) in enumerate(sentences_map):
                if self._stop_flag.is_set():
                    break

                self._paused.wait()
                if self._stop_flag.is_set():
                    break

                logging.info(f"[OMNIVOICE TTS] Generating sentence {i+1}/{len(sentences_map)}: {clean_sentence[:50]!r}...")
                
                try:
                    # OmniVoice generates the whole sentence at once
                    audio = model.generate(
                        text=clean_sentence,
                        ref_audio=self._ref_audio,
                        ref_text=self._ref_text,
                        speed=0.9,
                        denoise=True
                    )
                    
                    if isinstance(audio, list):
                        audio = np.concatenate(audio)
                        
                    if len(audio) > 0:
                        wav_chunk = np.array(audio, dtype='float32')
                        if wav_chunk.ndim == 1:
                            wav_chunk = wav_chunk.reshape(-1, 1)
                        
                        # Wait until there is room in the queue
                        while not self._stop_flag.is_set():
                            try:
                                self._generation_queue.put((i, raw_sentence, wav_chunk), timeout=0.1)
                                break
                            except queue.Full:
                                pass
                        
                except Exception as e:
                    logging.error(f"Error on sentence {i+1}: {e}")
                    
            # Signal end of generation
            while not self._stop_flag.is_set():
                try:
                    self._generation_queue.put(None, timeout=0.1)
                    break
                except queue.Full:
                    pass

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(f"OmniVoice TTS Error: {str(e)}")

    def _player(self) -> None:
        try:
            while not self._stop_flag.is_set():
                self._paused.wait()
                if self._stop_flag.is_set():
                    break
                
                try:
                    item = self._generation_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                    
                if item is None:
                    break # End of text
                    
                i, raw_sentence, wav_chunk = item
                
                self.sentence_started.emit(i, raw_sentence)
                self._audio_queue.put(wav_chunk)
                
                # Wait for audio to finish playing
                while (not self._audio_queue.empty() or len(self._audio_buffer) > 0) and not self._stop_flag.is_set():
                    self._paused.wait()
                    sd.sleep(50)
                
                if not self._stop_flag.is_set():
                    self.sentence_finished.emit(i)
                    
        finally:
            if not self._stop_flag.is_set():
                self.playback_finished.emit()

    def pause(self) -> None:
        self._paused.clear()

    def resume(self) -> None:
        self._paused.set()
        
    def is_paused(self) -> bool:
        return not self._paused.is_set()
        
    def is_playing(self) -> bool:
        return (self._thread is not None and self._thread.is_alive()) or (self._player_thread is not None and self._player_thread.is_alive())

    def stop(self) -> None:
        self._stop_flag.set()
        self._paused.set()
        
        # Clear generation queue
        if hasattr(self, '_generation_queue'):
            while not self._generation_queue.empty():
                try:
                    self._generation_queue.get_nowait()
                except queue.Empty:
                    break
        
        # Instantly clear the audio hardware queue to stop playback
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
                
        # CLEAR BUFFER TO FIX STOP DELAY
        self._audio_buffer = np.zeros((0, 1), dtype='float32')
                
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            
        if self._player_thread and self._player_thread.is_alive():
            self._player_thread.join(timeout=1.0)
