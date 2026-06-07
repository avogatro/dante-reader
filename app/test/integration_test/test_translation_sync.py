import sys
import json
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtCore import QCoreApplication, QTimer
from app.translation_manager import TranslationManager
from app.interfaces import LLMBackend

class FailingBackend(LLMBackend):
    @property
    def name(self) -> str:
        return "Failing"
    def is_available(self) -> bool:
        return True
    def get_models(self) -> list[str]:
        return ["fail_model"]
    def generate(self, prompt: str, model: str) -> str:
        raise RuntimeError("Simulated connection failure (e.g. Gemini key missing)")

class SucceedingBackend(LLMBackend):
    @property
    def name(self) -> str:
        return "Succeeding"
    def is_available(self) -> bool:
        return True
    def get_models(self) -> list[str]:
        return ["good_model"]
    def generate(self, prompt: str, model: str) -> str:
        # Return a valid JSON array string mimicking an LLM response
        return json.dumps(["Test successful!"])

def run_test():
    app = QCoreApplication(sys.argv)
    
    fail_backend = FailingBackend()
    good_backend = SucceedingBackend()
    
    # 1. Instantiate the TranslationManager with the failing backend
    manager = TranslationManager("dummy_test_book.epub", "Modern English", fail_backend, "fail_model")
    
    blocks = [{"id": "trans_test_0", "html": "Hello world"}]
    
    step = 0
    
    def on_error(index, err):
        nonlocal step
        print(f"✅ [TEST STEP 1] Received error as expected: {err}")
        if step == 0:
            step = 1
            print("🔄 [TEST STEP 2] Swapping to succeeding backend and model...")
            manager.backend = good_backend
            manager.model_name = "good_model"
            
            print("🚀 [TEST STEP 3] Triggering translation again...")
            manager.translate_blocks(1, blocks)
            
    # Monkeypatch to catch the error
    manager._on_translation_error = on_error
    
    def on_done(index):
        trans = manager.get_chapter(index)
        print(f"✅ [TEST STEP 4] Translation successful! Result: {trans}")
        
        if trans.get("trans_test_0") == "Test successful!":
            print("🎉 ALL INTEGRATION TESTS PASSED!")
        else:
            print(f"❌ TEST FAILED: Unexpected translation output: {trans}")
            
        app.quit()
        
    manager.chapter_translated.connect(on_done)
    
    print("🚀 [TEST STEP 0] Triggering first translation (should fail)...")
    manager.translate_blocks(1, blocks)
    
    # Safety timeout
    QTimer.singleShot(5000, lambda: (print("❌ [TEST] Timeout!"), app.quit()))
    
    app.exec()

if __name__ == "__main__":
    run_test()
