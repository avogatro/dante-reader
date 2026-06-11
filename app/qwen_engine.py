"""
Qwen-TTS Engine — Neural Text-to-Speech wrapper using Alibaba's Qwen3-TTS.
Uses sounddevice to stream live audio directly from the neural network.
"""

import logging
import threading
import queue
from typing import Optional, Iterator
import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject
from app.interfaces import BaseTTSEngine

from .tts_engine import split_sentences, strip_footnote_markers

try:
    import torch
    from faster_qwen3_tts import FasterQwen3TTS
    QWEN_AVAILABLE = True
except ImportError:
    QWEN_AVAILABLE = False


class QwenTTSEngine(BaseTTSEngine):
    """
    Qwen-3 TTS engine wrapper supporting real-time streaming audio via sounddevice.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[FasterQwen3TTS] = None
        self._thread: Optional[threading.Thread] = None
        
        self._stop_flag = threading.Event()
        self._paused = threading.Event()
        self._paused.set()  # Not paused initially
        
        self._skip_footnotes = True
        self._speaker = "aiden"
        self._model_id = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
        self._sample_rate = 24000 # Qwen natively synthesizes at 24kHz
        
        # Audio Streaming State
        self._audio_queue = queue.Queue()
        self._audio_buffer = np.zeros((0, 1), dtype='float32')
        
        # Continuous hardware stream to prevent hardware pops
        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback,
            blocksize=2048
        )
        self._stream.start()
        
        # Start model initialization and warmup in the background immediately
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
            # This prevents the hardware from buzzing or popping when waiting for the AI!
            have = len(self._audio_buffer)
            if have > 0:
                outdata[:have] = self._audio_buffer
            outdata[have:] = 0.0
            self._audio_buffer = np.zeros((0, 1), dtype='float32')

    def _init_model_bg(self) -> None:
        try:
            self._ensure_model()
        except Exception as e:
            logging.error(f"Failed to background init Qwen model: {e}")

    def _ensure_model(self) -> FasterQwen3TTS:
        if self._model is None:
            if not QWEN_AVAILABLE:
                raise ImportError("faster-qwen3-tts is not installed.")
                
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            
            logging.info("[QWEN TTS] Loading FasterQwen3TTS model...")
            self._model = FasterQwen3TTS.from_pretrained(
                self._model_id,
                device=device,
                dtype=dtype,
                attn_implementation="sdpa"
            )
            
            # Warm up the CUDA graphs to get instant TTFA later
            logging.info("[QWEN TTS] Warming up CUDA graphs (this takes ~10s)...")
            list(self._model.generate_custom_voice_streaming(
                text="warmup", 
                speaker="aiden", 
                language="English", 
                chunk_size=12
            ))
            logging.info("[QWEN TTS] Warmup complete! Engine ready.")
            
        return self._model

    def set_voice(self, voice_id: str) -> None:
        self._speaker = voice_id

    def set_skip_footnotes(self, skip: bool) -> None:
        self._skip_footnotes = skip
        
    def set_rate(self, rate: int) -> None:
        # Qwen-3 TTS doesn't currently support native playback rate adjustment.
        # This is a no-op to satisfy the BaseTTSEngine interface.
        pass

    def get_available_voices(self) -> list[dict]:
        return [
            {"id": "aiden", "name": "Aiden (Sunny American Male)"},
            {"id": "dylan", "name": "Dylan (Male)"},
            {"id": "eric", "name": "Eric (Male)"},
            {"id": "ono_anna", "name": "Ono Anna (Female)"},
            {"id": "ryan", "name": "Ryan (Dynamic Male)"},
            {"id": "serena", "name": "Serena (Female)"},
            {"id": "sohee", "name": "Sohee (Female)"},
            {"id": "uncle_fu", "name": "Uncle Fu (Male)"},
            {"id": "vivian", "name": "Vivian (Bright Young Female)"},
        ]

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
        self._thread = threading.Thread(
            target=self._worker, args=(sentences_map,), daemon=True
        )
        self._thread.start()

    def _worker(self, sentences_map: list[tuple[str, str]]) -> None:
        try:
            model = self._ensure_model()
            
            for i, (raw_sentence, clean_sentence) in enumerate(sentences_map):
                if self._stop_flag.is_set():
                    break

                self._paused.wait()
                if self._stop_flag.is_set():
                    break

                logging.info(f"[QWEN TTS] Generating sentence {i+1}/{len(sentences_map)}: {clean_sentence[:50]!r}...")
                self.sentence_started.emit(i, raw_sentence)
                
                try:
                    # True streaming generator yields chunks as they are predicted
                    gen = model.generate_custom_voice_streaming(
                        text=clean_sentence,
                        speaker=self._speaker,
                        language="English",
                        chunk_size=12
                    )
                    
                    # Accumulate audio to prevent micro-stutters
                    chunk_buffer = []
                    chunk_buffer_size = 0
                    MIN_BUFFER_SIZE = 12000 # 0.5s of audio at 24kHz
                    
                    for audio_chunk, sr, timing in gen:
                        if self._stop_flag.is_set():
                            # Flush the queue if we stopped
                            while not self._audio_queue.empty():
                                self._audio_queue.get_nowait()
                            break
                        
                        self._paused.wait()
                        
                        if len(audio_chunk) > 0:
                            wav_chunk = np.array(audio_chunk, dtype='float32')
                            if wav_chunk.ndim == 1:
                                wav_chunk = wav_chunk.reshape(-1, 1)
                            
                            chunk_buffer.append(wav_chunk)
                            chunk_buffer_size += len(wav_chunk)
                            
                            if chunk_buffer_size >= MIN_BUFFER_SIZE:
                                self._audio_queue.put(np.concatenate(chunk_buffer))
                                chunk_buffer.clear()
                                chunk_buffer_size = 0
                                
                    # Put any remaining audio in the queue
                    if chunk_buffer and not self._stop_flag.is_set():
                        self._audio_queue.put(np.concatenate(chunk_buffer))
                            
                finally:
                    pass
                
                # Wait for the audio queue to drain before marking the sentence as finished
                while not self._audio_queue.empty():
                    if self._stop_flag.is_set():
                        break
                    self._paused.wait()
                    sd.sleep(50)
                
                self.sentence_finished.emit(i)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(f"Qwen TTS Error: {str(e)}")
        finally:
            self.playback_finished.emit()

    def pause(self) -> None:
        self._paused.clear()

    def resume(self) -> None:
        self._paused.set()
        
    def is_paused(self) -> bool:
        return not self._paused.is_set()
        
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        self._stop_flag.set()
        self._paused.set()
        
        # Instantly clear the audio hardware queue to stop playback
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
                
        # Clear buffer to eliminate stop delay
        self._audio_buffer = np.zeros((0, 1), dtype='float32')
                
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
