import json
import urllib.request
import urllib.error
from .interfaces import LLMBackend

# Try importing google.genai (new SDK)
try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

class OllamaBackend(LLMBackend):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self._available_models: list[str] = []

    @property
    def name(self) -> str:
        return "Ollama (Local)"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._available_models = [m["name"] for m in data.get("models", [])]
                return len(self._available_models) > 0
        except Exception:
            return False

    def get_models(self) -> list[str]:
        return self._available_models

    def generate(self, prompt: str, model: str) -> str:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "No response received.")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"🔌 Cannot connect to Ollama.\n\nMake sure Ollama is running:\n  ollama serve\n\nExpected at: {self.base_url}")


class GeminiBackend(LLMBackend):
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None
        self._available_models: list[str] = []

    @property
    def name(self) -> str:
        return "Gemini (Cloud)"

    def is_available(self) -> bool:
        if not HAS_GENAI or not self._api_key:
            return False
            
        try:
            self._client = genai.Client(api_key=self._api_key)
            # Only list models that support generateContent
            models = []
            for m in self._client.models.list():
                if "generateContent" in getattr(m, "supported_actions", []):
                    models.append(m.name)
            self._available_models = models
            return len(self._available_models) > 0
        except Exception as e:
            return False

    def get_models(self) -> list[str]:
        return self._available_models

    def generate(self, prompt: str, model: str) -> str:
        if not self._client:
            if not self._api_key:
                raise RuntimeError("Gemini API key is not configured. Please add it in settings.")
            self._client = genai.Client(api_key=self._api_key)
            
        try:
            response = self._client.models.generate_content(
                model=model, contents=prompt
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                raise RuntimeError(
                    "🚫 Gemini API quota exhausted.\n\n"
                    "Your free-tier API key has hit its daily request limit. "
                    "Switch to Ollama (local) for unlimited free usage, or wait ~24h for quota reset."
                )
            raise RuntimeError(error_str)

def get_all_backends() -> dict[str, LLMBackend]:
    """Factory function to load and return all available backend instances."""
    from app.config import load_prefs
    prefs = load_prefs()
    api_key = prefs.get("gemini_api_key", "")
    return {
        "Ollama (Local)": OllamaBackend(base_url="http://localhost:11434"),
        "Gemini (Cloud)": GeminiBackend(api_key=api_key)
    }
