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

    # --- FUNGSI BARU UNTUK MANAJEMEN POSISI AKTIF ---

    def get_all_open_positions(self) -> List[Dict[str, Any]]:
        """Mengambil semua dokumen dari koleksi 'open_positions'."""
        if self.db is None: return []
        return list(self.db.open_positions.find({}))

    def get_open_position(self, coin_pair: str) -> Optional[Dict[str, Any]]:
        """Mengambil data posisi terbuka berdasarkan coin_pair."""
        if self.db is None: return None
        return self.db.open_positions.find_one({'_id': coin_pair})

    def save_open_position(self, position_data: Dict[str, Any]):
        """Menyimpan atau memperbarui data posisi terbuka menggunakan coin_pair sebagai _id."""
        if self.db is None or not position_data or 'coin_pair' not in position_data:
            print("Gagal menyimpan posisi: Data tidak valid atau koneksi DB tidak ada.")
            return

        collection = self.db.open_positions
        doc = position_data.copy()
        doc['_id'] = doc['coin_pair']
        
        result = collection.replace_one({'_id': doc['_id']}, doc, upsert=True)
        if result.upserted_id:
            print(f"Posisi baru untuk {doc['_id']} disimpan ke DB.")
        elif result.modified_count > 0:
            print(f"Data posisi untuk {doc['_id']} diperbarui di DB.")

    def delete_open_position(self, coin_pair: str) -> bool:
        """Menghapus data posisi terbuka dari DB setelah ditutup."""
        if self.db is None: return False
        
        result = self.db.open_positions.delete_one({'_id': coin_pair})
        if result.deleted_count > 0:
            print(f"Posisi {coin_pair} telah ditutup dan dihapus dari DB.")
            return True
        return False

    def close_connection(self):
        """Menutup koneksi ke database."""
        if self.client:
            self.client.close()
            print("Koneksi MongoDB ditutup.")