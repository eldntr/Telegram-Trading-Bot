import json
from typing import List, Dict, Any
from datetime import datetime

class JsonWriter:
    """Handles writing data to a JSON file."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def write(self, data: List[Dict[str, Any]]):
        """Writes a list of dictionaries to the JSON file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Successfully wrote {len(data)} messages to {self.file_path}")
        except IOError as e:
            print(f"Error writing to file {self.file_path}: {e}")