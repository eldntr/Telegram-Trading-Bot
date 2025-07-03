# Auto Trade Bot dari Sinyal Telegram 

Bot ini dirancang untuk mengotomatiskan proses trading di Binance berdasarkan sinyal yang dikirim ke channel atau grup Telegram. Versi ini telah ditingkatkan dengan fitur-fitur canggih untuk manajemen risiko, analisis pasar, dan manajemen posisi yang lebih cerdas. Bot akan mengambil pesan, mem-parsingnya, membuat keputusan berdasarkan strategi filter berlapis, mengeksekusi trade, dan mengelola posisi terbuka secara aktif.

## ✨ Fitur Unggulan Terbaru

  - **Parser Telegram Canggih**: Mampu membedakan berbagai jenis pesan seperti sinyal baru, pembaruan sinyal, rekap harian, dan peringatan pasar.
  - **Strategi Filter Berlapis (Multi-Layered Filter)**:
      - **Filter Tren Global (BTC)**: Menganalisis kondisi pasar Bitcoin (di atas/di bawah SMA) sebelum memutuskan untuk masuk ke market.
      - **Filter Tren Altcoin (Lokal)**: Jika pasar BTC netral, bot akan menganalisis tren koin sinyal itu sendiri sebagai konfirmasi kedua.
      - **Filter Prioritas Risiko**: Bot dapat dikonfigurasi untuk hanya mengeksekusi sinyal dengan tingkat risiko "Normal", mengabaikan sinyal berisiko tinggi.
      - **Filter Sinyal Kedaluwarsa**: Mengabaikan sinyal yang usianya sudah melebihi batas waktu validitas yang ditentukan.
  - **Manajemen Posisi Aktif**:
      - **Trailing Stop Loss Dinamis**: Secara otomatis menaikkan level Stop Loss ke titik breakeven atau level Take Profit sebelumnya ketika target harga tercapai untuk mengamankan keuntungan.
      - **Penanganan Posisi Macet (Stuck Trade)**: Menutup posisi secara otomatis jika tidak mencapai TP1 setelah durasi waktu tertentu untuk mencegah modal terjebak.
  - **Eksekusi Aman & Cerdas**:
      - **Pemeriksaan Pra-Pembelian**: Melakukan validasi lengkap (saldo cukup, tidak ada order duplikat, aturan `min_notional` terpenuhi) sebelum membeli.
      - **Eksekusi Order OCO**: Setelah membeli aset, bot langsung memasang order OCO (One-Cancels-the-Other) untuk *Take Profit* dan *Stop Loss*.
  - **Dashboard Streamlit Interaktif**: Visualisasikan status akun, keputusan trade, sinyal terbaru, dan data mentah dari file JSON secara *real-time*.
  - **Integrasi Database MongoDB**: Menyimpan sinyal yang ter-parse dan melacak posisi trading yang sedang aktif untuk manajemen yang persisten.
  - **Mode Operasi Fleksibel**:
      - **Autoloop**: Menjalankan bot secara terus-menerus dengan siklus fetch, decide, execute, dan manage.
      - **Kontrol CLI**: Menjalankan setiap rutinitas (fetch, decide, execute, status, manage) secara terpisah melalui argumen baris perintah.

## 📂 Struktur Proyek

```
Telegram-Trading-Bot/
├── core/
│   └── routines.py          # Logika utama untuk setiap alur kerja (fetch, decide, dll.)
├── binance/
│   ├── client.py            # Klien untuk interaksi dengan API Binance
│   ├── strategy.py          # Logika strategi trading dan filter keputusan
│   ├── trader.py            # Logika untuk eksekusi trade (buy, oco)
│   ├── account.py           # Logika untuk manajemen akun (cek saldo)
│   └── models.py            # Dataclass untuk struktur data trading
├── telegram/
│   ├── client.py            # Klien untuk koneksi dan mengambil pesan Telegram
│   ├── parser.py            # Logika untuk mem-parsing berbagai jenis pesan
│   ├── models.py            # Dataclass untuk berbagai tipe pesan Telegram
│   └── utils.py             # Utilitas, seperti penulis file JSON
├── db/
│   └── mongo_client.py      # Pengelola koneksi dan operasi MongoDB
├── data/                    # Direktori output untuk file .json (diabaikan oleh git)
├── main.py                  # File utama sebagai pusat kendali (entry point)
├── dashboard.py             # Aplikasi dashboard Streamlit
├── config.py                # Memuat konfigurasi dari file .env
├── requirements.txt         # Daftar library yang dibutuhkan
├── .env                     # File konfigurasi environment (tidak di-commit)
├── .env.sample              # Contoh file .env
├── docker-compose.yml       # Konfigurasi untuk menjalankan bot dan DB dengan Docker
└── README.MD                # File dokumentasi ini
```

## 🚀 Pengaturan & Instalasi

1.  **Clone Proyek**

    ```bash
    git clone <url_repository_anda>
    cd Telegram-Trading-Bot-prioritize-normal-risk
    ```

2.  **Buat Virtual Environment** (Sangat disarankan)

    ```bash
    python -m venv venv
    source venv/bin/activate  # Di Windows: venv\Scripts\activate
    ```

3.  **Install Dependensi**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi Environment**
    Salin file `.env.sample` menjadi `.env` dan isi semua variabel yang diperlukan.

    ```bash
    cp .env.sample .env
    ```

    Buka file `.env` dan sesuaikan nilainya:

    ```env
    # Konfigurasi Telegram
    TELEGRAM_API_ID="YOUR_TELEGRAM_API_ID"
    TELEGRAM_API_HASH="YOUR_TELEGRAM_API_HASH"
    TELEGRAM_PHONE_NUMBER="YOUR_PHONE_NUMBER_WITH_COUNTRY_CODE"
    TELEGRAM_TARGET_CHAT_ID="TARGET_TELEGRAM_CHAT_ID"

    # Konfigurasi Binance
    BINANCE_API_KEY="YOUR_BINANCE_API_KEY"
    BINANCE_API_SECRET="YOUR_BINANCE_SECRET_KEY"

    # Konfigurasi Trading & Risiko
    USDT_AMOUNT_PER_TRADE="11"
    PRIORITIZE_NORMAL_RISK="True"
    FILTER_OLD_SIGNALS_ENABLED="True"
    SIGNAL_VALIDITY_MINUTES="45"

    # Konfigurasi Filter Pasar
    BTC_TREND_FILTER_ENABLED="True"
    BTC_FILTER_TIMEFRAME="1h"
    BTC_FILTER_SMA_PERIOD="50"
    ALTCOIN_TREND_FILTER_ENABLED="True"

    # Konfigurasi Manajemen Posisi
    TRAILING_ENABLED="True"
    STUCK_TRADE_ENABLED="True"
    STUCK_TRADE_DURATION_HOURS="6"

    # Konfigurasi Database (jika menggunakan Docker, sesuaikan dengan docker-compose.yml)
    MONGO_URI="mongodb://root:07092004@localhost:27017/"
    ```

## 🛠️ Cara Penggunaan

Semua perintah dijalankan melalui `main.py`.

  - **Mengambil Pesan & Menyimpan ke DB**

    ```bash
    python main.py fetch --limit 100
    ```

  - **Membuat Keputusan Trading dari Sinyal di DB**

    ```bash
    python main.py decide
    ```

  - **Mengeksekusi Trade yang Disetujui**

    ```bash
    python main.py execute
    ```

  - **Memeriksa Status Akun & Order Terbuka**

    ```bash
    python main.py status
    ```

  - **Menjalankan Rutinitas Manajemen Posisi (Trailing & Stuck)**

    ```bash
    python main.py manage
    ```

  - **Menjalankan Mode Otomatis (Autoloop)**
    (Berjalan selamanya, jeda 5 menit, fetch awal 100 pesan, siklus berikutnya 50 pesan)

    ```bash
    python main.py autoloop --delay 300 --initial-limit 100 --limit 50
    ```

  - **Menjalankan Dashboard Visual**

    ```bash
    streamlit run dashboard.py
    ```

## 🐳 Menjalankan dengan Docker

Proyek ini dilengkapi dengan `docker-compose.yml` untuk memudahkan deployment.

1.  Pastikan Docker dan Docker Compose terinstall.
2.  Pastikan file `.env` Anda sudah terisi dengan benar, terutama `MONGO_URI` yang harus menunjuk ke service `mongodb`.
3.  Jalankan perintah berikut dari root direktori proyek:
    ```bash
    docker-compose up --build
    ```
    Perintah ini akan membangun image untuk bot dan dashboard, serta menjalankan kontainer MongoDB. Bot akan mulai berjalan dalam mode `autoloop` dan dashboard akan dapat diakses di `http://localhost:8501`.

## 🌊 Diagram Alur Kerja Bot (Autoloop)

```mermaid
graph TD
    subgraph "Siklus Bot Autoloop"
        A[Mulai Siklus] --> B{1. Fetch Pesan & Simpan ke DB};
        B --> C{2. Decide: Ambil Sinyal dari DB & Terapkan Filter};
        C --> |Ada Sinyal 'BUY'| D{3. Execute Trade};
        C --> |SKIP/FAIL| E[Lanjut ke Manajemen];
        D --> E;
        E --> F{4. Manage Positions};
        F --> |Cek Posisi di DB| G{Update Trailing SL / Tutup Posisi Macet};
        G --> H[Tunggu Jeda Waktu];
    end
    H --> A;
```