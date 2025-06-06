# telegram/utils.py
import json
from typing import List, Dict, Any

class JsonWriter:
    """Menangani penulisan data ke file JSON."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def write(self, data: List[Dict[str, Any]]):
        """Menulis daftar dictionary ke file JSON."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Berhasil menulis {len(data)} pesan ke {self.file_path}")
        except IOError as e:
            print(f"Error saat menulis ke file {self.file_path}: {e}")