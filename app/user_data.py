import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

class UserDataManager:
    def __init__(self, book_path: str):
        self.book_path = book_path
        
        # Determine the userdata JSON path
        base_path, ext = os.path.splitext(book_path)
        self.data_file = f"{base_path}_userdata.json"
        
        # In-memory data store
        self.data = {
            "bookmarks": [],
            "notes": []
        }
        
        self.load()

    def load(self) -> None:
        """Load user data from the JSON file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    self.data["bookmarks"] = content.get("bookmarks", [])
                    self.data["notes"] = content.get("notes", [])
            except Exception as e:
                print(f"Failed to load user data from {self.data_file}: {e}")

    def save(self) -> None:
        """Save user data to the JSON file."""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save user data to {self.data_file}: {e}")

    # --- Bookmarks ---
    
    def add_bookmark(self, chapter: int, scroll_percent: float, label: str = "") -> Dict:
        bookmark = {
            "id": str(uuid.uuid4()),
            "chapter": chapter,
            "scroll_percent": scroll_percent,
            "label": label,
            "timestamp": datetime.now().isoformat()
        }
        self.data["bookmarks"].append(bookmark)
        self.save()
        return bookmark

    def remove_bookmark(self, bookmark_id: str) -> bool:
        initial_len = len(self.data["bookmarks"])
        self.data["bookmarks"] = [b for b in self.data["bookmarks"] if b["id"] != bookmark_id]
        if len(self.data["bookmarks"]) < initial_len:
            self.save()
            return True
        return False

    def update_bookmark(self, bookmark_id: str, new_label: str) -> bool:
        for b in self.data["bookmarks"]:
            if b["id"] == bookmark_id:
                b["label"] = new_label
                b["timestamp"] = datetime.now().isoformat()
                self.save()
                return True
        return False

    def get_bookmarks(self) -> List[Dict]:
        return sorted(self.data["bookmarks"], key=lambda x: (x.get("chapter", 0), x.get("scroll_percent", 0.0)))

    # --- Notes ---
    
    def add_note(self, chapter: int, scroll_percent: float, selected_text: str, note_content: str) -> Dict:
        note = {
            "id": str(uuid.uuid4()),
            "chapter": chapter,
            "scroll_percent": scroll_percent,
            "selected_text": selected_text,
            "note": note_content,
            "timestamp": datetime.now().isoformat()
        }
        self.data["notes"].append(note)
        self.save()
        return note

    def remove_note(self, note_id: str) -> bool:
        initial_len = len(self.data["notes"])
        self.data["notes"] = [n for n in self.data["notes"] if n["id"] != note_id]
        if len(self.data["notes"]) < initial_len:
            self.save()
            return True
        return False

    def update_note(self, note_id: str, new_content: str) -> bool:
        for n in self.data["notes"]:
            if n["id"] == note_id:
                n["note"] = new_content
                n["timestamp"] = datetime.now().isoformat()
                self.save()
                return True
        return False

    def get_notes(self) -> List[Dict]:
        return sorted(self.data["notes"], key=lambda x: (x.get("chapter", 0), x.get("scroll_percent", 0.0)))
