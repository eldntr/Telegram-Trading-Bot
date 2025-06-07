# Auto Trade Bot/db/mongo_client.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from typing import List, Dict, Any, Optional

class MongoManager:
    """Mengelola koneksi dan operasi ke database MongoDB."""

    def __init__(self, uri: str, db_name: str):
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=10000)
            self.client.admin.command('ping')
            self.db = self.client[db_name]
            print("Berhasil terhubung ke MongoDB.")
        except ConnectionFailure as e:
            print(f"Gagal terhubung ke MongoDB: {e}")
            self.client = None
            self.db = None
    
    # --- BARU: Fungsi untuk mengambil satu sinyal ---
    def get_signal_by_pair(self, coin_pair: str) -> Optional[Dict[str, Any]]:
        """Mengambil data sinyal berdasarkan coin_pair dari koleksi 'new_signals'."""
        if self.db is None:
            return None
        
        return self.db.new_signals.find_one({'_id': coin_pair})

    def save_new_signals(self, signals: List[Dict[str, Any]]):
        """
        Menyimpan atau memperbarui sinyal baru ke koleksi 'new_signals'.
        Menggunakan 'coin_pair' sebagai _id untuk operasi upsert.
        """
        if self.db is None or not signals:
            if not signals:
                print("Tidak ada sinyal baru untuk disimpan ke MongoDB.")
            elif self.db is None:
                print("Tidak dapat menyimpan sinyal karena koneksi DB tidak ada.")
            return

        collection = self.db.new_signals
        
        upserted_count = 0
        modified_count = 0

        for signal in signals:
            coin_pair = signal.get("coin_pair")
            if not coin_pair:
                continue

            signal['_id'] = coin_pair
            filter_query = {'_id': coin_pair}
            result = collection.replace_one(filter_query, signal, upsert=True)
            
            if result.upserted_id:
                upserted_count += 1
            elif result.modified_count > 0:
                modified_count += 1
        
        print(f"Proses penyimpanan MongoDB selesai. Sinyal Baru: {upserted_count}, Sinyal Diperbarui: {modified_count}.")


    def close_connection(self):
        """Menutup koneksi ke database."""
        if self.client:
            self.client.close()
            print("Koneksi MongoDB ditutup.")