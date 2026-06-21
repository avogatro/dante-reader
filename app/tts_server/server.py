import logging
import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import numpy as np

# Global model state
_model = None
_model_lock = threading.Lock()

class GenerateRequest(BaseModel):
    text: str
    ref_audio: str
    ref_text: str

def _init_model():
    global _model
    with _model_lock:
        if _model is not None:
            return
            
        logging.info("[TTS SERVER] Loading OmniVoice model...")
        import torch
        from omnivoice import OmniVoice
        
        if torch.cuda.is_available():
            device = "cuda:0"
            dtype = torch.bfloat16
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            dtype = torch.float16
        else:
            device = "cpu"
            dtype = torch.float32
            
        _model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=device,
            dtype=dtype
        )
        logging.info("[TTS SERVER] OmniVoice model loaded.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize model in the background so the server binds to the port instantly
    threading.Thread(target=_init_model, daemon=True).start()
    yield
    # Clean up on shutdown if needed
    global _model
    _model = None

app = FastAPI(title="OmniVoice TTS Server", lifespan=lifespan)

@app.get("/status")
def status():
    return {"status": "ready" if _model is not None else "loading"}

@app.post("/generate")
def generate(req: GenerateRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model is still loading")
        
    try:
        # Generate raw audio
        audio = _model.generate(
            text=req.text, 
            ref_audio=req.ref_audio, 
            ref_text=req.ref_text
        )
        
        # Convert output to numpy float32 array
        if hasattr(audio, 'detach'):
            audio_np = audio.detach().cpu().numpy()
        elif isinstance(audio, tuple) and hasattr(audio[0], 'detach'):
            audio_np = audio[0].detach().cpu().numpy()
        else:
            audio_np = np.array(audio)
            
        if len(audio_np.shape) == 1:
            audio_np = np.expand_dims(audio_np, axis=-1)
            
        audio_np = audio_np.astype(np.float32)
        
        # Return as raw bytes
        return Response(content=audio_np.tobytes(), media_type="application/octet-stream")
        
    except Exception as e:
        logging.error(f"[TTS SERVER] Error generating audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))
