"""
OmniVoice Engine — Neural Text-to-Speech wrapper using OmniVoice.
Uses sounddevice to stream live audio.
"""

import logging
import threading
import queue
import time
import os
from typing import Optional
import numpy as np
import sounddevice as sd
from app.interfaces import BaseTTSEngine

from .tts_engine import split_sentences, strip_footnote_markers

import socket
import subprocess
import sys
import atexit
import requests
import json


class OmniVoiceTTSEngine(BaseTTSEngine):
    """
    OmniVoice TTS engine wrapper supporting audio playback via sounddevice queue.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = None
        self._thread: Optional[threading.Thread] = None
        self._player_thread: Optional[threading.Thread] = None
        self._server_process: Optional[subprocess.Popen] = None
        self._port = 8123
        
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
        
        # Kill any orphaned TTS server processes from previous runs
        self._kill_stale_servers()
        
        # Launch the TTS Microservice as a completely independent subprocess
        self._port = self._get_free_port()
        self._server_ready = False
        
        # In debug mode (DANTE_DEBUG=1), pipe stderr to a log file for diagnostics
        self._server_log = None
        if os.environ.get("DANTE_DEBUG"):
            log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tts_server.log'))
            self._server_log = open(log_path, 'w')
            server_stderr = self._server_log
            logging.info(f"[OMNIVOICE] Debug mode: server stderr → {log_path}")
        else:
            server_stderr = subprocess.DEVNULL
        
        self._server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.tts_server.server:app", "--port", str(self._port)],
            stdout=subprocess.DEVNULL,
            stderr=server_stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Register cleanup for normal exits
        atexit.register(self.cleanup)
        logging.info(f"[OMNIVOICE] TTS server launched on port {self._port} (PID {self._server_process.pid})")

    def _get_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
            
    def _cleanup_server(self):
        """Terminate the TTS server subprocess and close log file."""
        if self._server_process:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=5)
            except Exception:
                try:
                    self._server_process.kill()
                except Exception:
                    pass
            self._server_process = None
        if self._server_log:
            try:
                self._server_log.close()
            except Exception:
                pass
            self._server_log = None

    def cleanup(self):
        """Public cleanup: stop playback, kill server, close audio stream."""
        self.stop()
        self._cleanup_server()
        if hasattr(self, '_stream') and self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass

    @staticmethod
    def _kill_stale_servers():
        """Kill any orphaned TTS server processes from previous app runs."""
        if os.name == 'nt':
            try:
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     "Get-CimInstance Win32_Process -Filter "
                     "\"Name='python.exe' AND CommandLine LIKE '%uvicorn app.tts_server.server%'\" | "
                     "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                    capture_output=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    logging.info("[OMNIVOICE] Cleaned up stale TTS server processes")
            except Exception as e:
                logging.warning(f"[OMNIVOICE] Could not clean stale servers: {e}")
        else:
            try:
                subprocess.run(
                    ['pkill', '-f', 'uvicorn app.tts_server.server'],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass

    def _wait_for_server(self) -> bool:
        """Poll the server's /status endpoint until it reports ready."""
        if self._server_ready:
            return True

        max_wait = 300  # 5 minutes max for model loading
        poll_interval = 2.0
        elapsed = 0.0

        logging.info("[OMNIVOICE] Waiting for TTS server to become ready...")

        while elapsed < max_wait and not self._stop_flag.is_set():
            # Check if subprocess crashed
            if self._server_process and self._server_process.poll() is not None:
                logging.error(f"[OMNIVOICE] Server process exited with code {self._server_process.returncode}")
                self.error.emit("TTS server crashed during startup. Run with DANTE_DEBUG=1 for details.")
                return False

            try:
                resp = requests.get(f"http://127.0.0.1:{self._port}/status", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "ready":
                        logging.info(f"[OMNIVOICE] Server ready after {elapsed:.0f}s")
                        self._server_ready = True
                        return True
                    else:
                        logging.info(f"[OMNIVOICE] Server status: {data.get('status')} ({elapsed:.0f}s elapsed)")
            except requests.ConnectionError:
                pass  # Server not yet listening
            except Exception as e:
                logging.debug(f"[OMNIVOICE] Status poll error: {e}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        if self._stop_flag.is_set():
            return False

        logging.error(f"[OMNIVOICE] Server did not become ready within {max_wait}s")
        self.error.emit(f"TTS server did not become ready within {max_wait}s")
        return False

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

    # Removed old background init and model loading

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
            # Wait for server to finish loading the model before first request
            if not self._wait_for_server():
                return

            for i, (raw_sentence, clean_sentence) in enumerate(sentences_map):
                if self._stop_flag.is_set():
                    break

                self._paused.wait()
                if self._stop_flag.is_set():
                    break

                logging.info(f"[OMNIVOICE TTS] Requesting sentence {i+1}/{len(sentences_map)}: {clean_sentence[:50]!r}...")
                
                try:
                    payload = {
                        "text": clean_sentence,
                        "ref_audio": self._ref_audio,
                        "ref_text": self._ref_text
                    }
                    response = requests.post(
                        f"http://127.0.0.1:{self._port}/generate", 
                        json=payload,
                        timeout=180.0
                    )
                    
                    if response.status_code != 200:
                        logging.error(f"[OMNIVOICE TTS] Server error: {response.text}")
                        continue
                        
                    audio_bytes = response.content
                    wav_chunk = np.frombuffer(audio_bytes, dtype=np.float32)
                    
                    if len(wav_chunk) > 0:
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
