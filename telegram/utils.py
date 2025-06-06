# Auto Trade Bot/telegram/utils.py
import json
import os
from typing import List, Dict, Any

class JsonWriter:
    """Menangani penulisan data ke file JSON di dalam direktori tertentu."""

    def __init__(self, file_name: str, directory: str = "data"):
        """
        Inisialisasi JsonWriter.

        Args:
            file_name: Nama file JSON yang akan ditulis.
            directory: Nama direktori untuk menyimpan file. Default 'data'.
        """
        self.directory = directory
        self.file_path = os.path.join(self.directory, file_name)
        
        # Memastikan direktori tujuan ada, jika tidak maka akan dibuat
        try:
            os.makedirs(self.directory, exist_ok=True)
        except OSError as e:
            print(f"Error saat membuat direktori {self.directory}: {e}")

    def write(self, data: any):
        """Menulis data (list atau dict) ke file JSON."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            item_count = len(data) if isinstance(data, list) else 1
            print(f"Berhasil menulis {item_count} item ke {self.file_path}")
        except IOError as e:
            print(f"Error saat menulis ke file {self.file_path}: {e}")