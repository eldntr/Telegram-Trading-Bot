# Auto Trade Bot/db/mongo_client.py (VERSI PERBAIKAN)

import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timezone

class MongoManager:
    """
    Manajer untuk semua interaksi dengan database MongoDB.
    Menangani penyimpanan sinyal, posisi, dan pengambilan data.
    """
    def __init__(self, uri, db_name):
        self.client = None
        self.db = None
        try:
            self.client = pymongo.MongoClient(uri)
            # Ping server untuk memastikan koneksi berhasil
            self.client.admin.command('ping')
            self.db = self.client[db_name]
            print("Berhasil terhubung ke MongoDB.")
            self._create_indexes()
        except ConnectionFailure as e:
            print(f"Gagal terhubung ke MongoDB: {e}")
            raise
        except Exception as e:
            print(f"Terjadi kesalahan saat inisialisasi MongoManager: {e}")
            raise

    def _create_indexes(self):
        """Membuat index untuk optimasi query, jika belum ada."""
        try:
            # Index untuk memastikan sinyal tidak duplikat berdasarkan ID pesan
            self.db.signals.create_index("message_id", unique=True)
            # Index untuk mengambil sinyal yang belum diproses dengan cepat
            self.db.signals.create_index("status")
            # Index untuk mengambil posisi terbuka berdasarkan coin_pair
            self.db.open_positions.create_index("coin_pair", unique=True)
            print("Index MongoDB telah diverifikasi/dibuat.")
        except OperationFailure as e:
            print(f"Gagal membuat index: {e}")


    def save_new_signals(self, signals_data: list):
        """
        Menyimpan sinyal baru ke database.
        Hanya menyimpan sinyal yang belum ada berdasarkan message_id.
        Setiap sinyal baru diberi status 'unprocessed'.
        """
        if not signals_data:
            return

        new_signals_count = 0
        for signal in signals_data:
            # Tambahkan status dan timestamp
            signal['status'] = 'unprocessed'
            signal['timestamp_received'] = datetime.now(timezone.utc)
            
            # Coba insert, jika message_id sudah ada, akan gagal (mencegah duplikat)
            try:
                self.db.signals.insert_one(signal)
                new_signals_count += 1
            except pymongo.errors.DuplicateKeyError:
                # Sinyal ini sudah ada, abaikan
                pass
        
        if new_signals_count > 0:
            print(f"Disimpan {new_signals_count} sinyal baru ke database.")

    # ======================================================================
    # === FUNGSI YANG HILANG DITAMBAHKAN DI SINI ===
    # ======================================================================
    def get_all_unprocessed_signals(self):
        """
        Mengambil semua sinyal dengan status 'unprocessed'.
        Setelah diambil, statusnya diubah menjadi 'processing' untuk mencegah
        diambil lagi oleh proses lain.
        """
        unprocessed_signals = list(self.db.signals.find({"status": "unprocessed"}))
        
        if not unprocessed_signals:
            return []

        print(f"Ditemukan {len(unprocessed_signals)} sinyal yang belum diproses.")
        
        # Dapatkan ID dari sinyal yang akan diproses
        signal_ids = [s['_id'] for s in unprocessed_signals]
        
        # Ubah status mereka menjadi 'processing'
        self.db.signals.update_many(
            {"_id": {"$in": signal_ids}},
            {"$set": {"status": "processing"}}
        )
        
        return unprocessed_signals
    
    def update_signal_status(self, message_id: int, new_status: str):
        """Mengubah status sinyal tertentu, misalnya menjadi 'executed'."""
        self.db.signals.update_one(
            {"message_id": message_id},
            {"$set": {"status": new_status}}
        )

    def save_open_position(self, position_data: dict):
        """Menyimpan atau memperbarui data posisi yang sedang terbuka."""
        # 'upsert=True' akan membuat dokumen baru jika belum ada, atau update jika sudah ada
        self.db.open_positions.update_one(
            {"coin_pair": position_data["coin_pair"]},
            {"$set": position_data},
            upsert=True
        )

    def get_all_open_positions(self) -> list:
        """Mengambil semua dokumen dari koleksi posisi terbuka."""
        return list(self.db.open_positions.find({}))

    def delete_open_position(self, coin_pair: str):
        """Menghapus dokumen posisi setelah ditutup."""
        self.db.open_positions.delete_one({"coin_pair": coin_pair})

    def close_connection(self):
        """Menutup koneksi ke database."""
        if self.client:
            self.client.close()