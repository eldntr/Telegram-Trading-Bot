# Auto Trade Bot/dashboard.py (Versi Perbaikan)
import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- Konfigurasi Halaman Streamlit ---
st.set_page_config(
    layout="wide",
    page_title="Auto Trade Bot Dashboard",
    page_icon="🤖",
    initial_sidebar_state="expanded"
)

# --- Fungsi Helper untuk Memuat Data ---
def load_json_data(file_path: Path):
    """Memuat data dari file JSON dengan penanganan error."""
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content:
                    return None
                return json.loads(content)
        except json.JSONDecodeError:
            return {"error": f"Gagal mem-parsing JSON dari {file_path.name}."}
        except Exception as e:
            return {"error": f"Terjadi kesalahan saat membaca {file_path.name}: {e}"}
    return {"error": f"File tidak ditemukan: {file_path.name}."}

# --- Path ke File Data (DIperbarui) ---
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"  # Menentukan subfolder 'data'

ACCOUNT_STATUS_FILE = DATA_DIR / "account_status.json"
TRADE_DECISIONS_FILE = DATA_DIR / "trade_decisions.json"
NEW_SIGNALS_FILE = DATA_DIR / "new_signals.json"
SIGNAL_UPDATES_FILE = DATA_DIR / "signal_updates.json"
MARKET_ALERTS_FILE = DATA_DIR / "market_alerts.json"
PARSED_MESSAGES_FILE = DATA_DIR / "parsed_messages.json"

ALL_JSON_FILES = {
    "Status Akun": ACCOUNT_STATUS_FILE,
    "Keputusan Trade": TRADE_DECISIONS_FILE,
    "Sinyal Baru": NEW_SIGNALS_FILE,
    "Pembaruan Sinyal": SIGNAL_UPDATES_FILE,
    "Peringatan Pasar": MARKET_ALERTS_FILE,
    "Semua Pesan Ter-parse": PARSED_MESSAGES_FILE,
}

# --- Sidebar dan Auto-Refresh ---
with st.sidebar:
    st.title("Auto Trade Bot")
    st.markdown("---")
    refresh_interval = st_autorefresh(
        interval=st.select_slider(
            "Pilih Interval Refresh Otomatis (detik)",
            options=[0, 5, 10, 30, 60],
            value=10,
            help="Pilih 0 untuk menonaktifkan refresh otomatis."
        ) * 1000,
        key="data_refresher"
    )
    st.info(f"Dashboard akan refresh setiap {refresh_interval / 1000} detik.")

# --- Judul Utama dan Tombol Refresh ---
st.title("🤖 Auto Trade Bot Dashboard")
st.markdown(f"**Data terakhir diperbarui pada:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")

# --- Memuat Semua Data ---
account_status = load_json_data(ACCOUNT_STATUS_FILE)
trade_decisions = load_json_data(TRADE_DECISIONS_FILE)
new_signals = load_json_data(NEW_SIGNALS_FILE)
signal_updates = load_json_data(SIGNAL_UPDATES_FILE)
market_alerts = load_json_data(MARKET_ALERTS_FILE)

# ==============================================================================
# TAMPILAN UTAMA
# ==============================================================================

# --- Ringkasan Status Akun Binance ---
st.header("📈 Ringkasan Akun Binance")

if account_status and "error" not in account_status:
    total_balance = account_status.get('total_balance_usdt', 0)
    held_assets_count = len(account_status.get('held_assets', []))

    col1, col2 = st.columns(2)
    col1.metric("Total Estimasi Nilai (USDT)", f"${total_balance:,.2f}")
    col2.metric("Jumlah Aset yang Dipegang", held_assets_count)

    with st.expander("Lihat Detail Aset yang Dipegang"):
        if held_assets_count > 0:
            df_assets = pd.DataFrame(account_status['held_assets'])
            st.dataframe(
                df_assets,
                column_config={
                    "asset": st.column_config.TextColumn("Aset"),
                    "total_balance": st.column_config.NumberColumn("Total Saldo", format="%.8f"),
                    "value_in_usdt": st.column_config.NumberColumn("Nilai (USDT)", format="$ %.2f"),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Tidak ada aset yang sedang dipegang.")
else:
    error_message = account_status.get("error", "Data status akun tidak tersedia.") if isinstance(account_status, dict) else "Data tidak valid."
    st.error(f"Gagal memuat status akun: **{error_message}**")

st.markdown("---")

# --- Analisis Keputusan Trading ---
st.header("🧠 Analisis & Keputusan Trading")

if trade_decisions and "error" not in trade_decisions and isinstance(trade_decisions, list):
    buy_count = sum(1 for d in trade_decisions if d.get('decision') == 'BUY')
    skip_count = sum(1 for d in trade_decisions if d.get('decision') == 'SKIP')
    fail_count = sum(1 for d in trade_decisions if d.get('decision') == 'FAIL')

    col1, col2, col3 = st.columns(3)
    col1.metric("Keputusan Beli (BUY)", buy_count, "Sinyal akan dieksekusi")
    col2.metric("Keputusan Lewati (SKIP)", skip_count, "Harga tidak sesuai", delta_color="off")
    col3.metric("Keputusan Gagal (FAIL)", fail_count, "Error saat evaluasi", delta_color="inverse")

    with st.expander("Lihat Detail Setiap Keputusan"):
        for decision in trade_decisions:
            emoji = "✅" if decision['decision'] == 'BUY' else ("⏭️" if decision['decision'] == 'SKIP' else "❌")
            with st.container(border=True):
                 st.subheader(f"{emoji} {decision['decision']}: {decision['coin_pair']}")
                 st.markdown(f"> **Alasan:** `{decision['reason']}`")
                 if decision.get('current_price') is not None:
                    st.text(f"Harga Saat Ini: {decision['current_price']} | Harga Masuk Sinyal: {decision['entry_price']}")
                 if decision['decision'] == 'BUY':
                    st.json(decision)
else:
    error_message = trade_decisions.get("error", "Data keputusan trading tidak tersedia.") if isinstance(trade_decisions, dict) else "Data tidak valid."
    st.error(f"Gagal memuat keputusan trading: **{error_message}**")

st.markdown("---")

# --- Sinyal Terbaru dari Telegram ---
st.header("🔔 Sinyal & Peringatan Terbaru dari Telegram")

tab1, tab2, tab3 = st.tabs([
    f"Sinyal Baru ({len(new_signals or []) if isinstance(new_signals, list) else 0})",
    f"Pembaruan Sinyal ({len(signal_updates or []) if isinstance(signal_updates, list) else 0})",
    f"Peringatan Pasar ({len(market_alerts or []) if isinstance(market_alerts, list) else 0})"
])

with tab1:
    if new_signals and "error" not in new_signals and isinstance(new_signals, list):
        st.subheader(f"Ditemukan {len(new_signals)} sinyal baru.")
        for signal in new_signals[:5]:
            with st.container(border=True):
                st.markdown(f"**Pair:** `{signal.get('coin_pair')}` | **Risiko:** `{signal.get('risk_level')}`")
                st.markdown(f"**Harga Masuk:** `{signal.get('entry_price')}`")
                with st.expander("Lihat data JSON lengkap"):
                    st.json(signal)
    else:
        st.warning("Tidak ada data sinyal baru atau file tidak dapat dibaca.")

with tab2:
    if signal_updates and "error" not in signal_updates and isinstance(signal_updates, list):
        st.subheader(f"Ditemukan {len(signal_updates)} pembaruan sinyal.")
        for update in signal_updates[:5]:
             with st.container(border=True):
                color = "green" if update.get('update_type') == 'TARGET_HIT' else "red"
                st.markdown(f"**Pair:** `{update.get('coin_pair')}` | <span style='color:{color};'>{update.get('update_type')}</span>", unsafe_allow_html=True)
                with st.expander("Lihat data JSON lengkap"):
                    st.json(update)
    else:
         st.warning("Tidak ada data pembaruan sinyal atau file tidak dapat dibaca.")

with tab3:
    if market_alerts and "error" not in market_alerts and isinstance(market_alerts, list):
        st.subheader(f"Ditemukan {len(market_alerts)} peringatan pasar.")
        for alert in market_alerts[:5]:
             with st.container(border=True):
                st.markdown(f"**Koin:** `{alert.get('coin')}` | **Perubahan:** `{alert.get('price_change_percentage')}%` dalam `{alert.get('timeframe_minutes')}` menit")
                with st.expander("Lihat data JSON lengkap"):
                    st.json(alert)
    else:
         st.warning("Tidak ada data peringatan pasar atau file tidak dapat dibaca.")

st.markdown("---")

# --- Penampil File JSON Mentah ---
st.header("📄 Penampil File JSON Mentah")
selected_file_name = st.selectbox("Pilih file JSON untuk ditampilkan:", options=list(ALL_JSON_FILES.keys()))

if selected_file_name:
    file_path = ALL_JSON_FILES[selected_file_name]
    raw_data = load_json_data(file_path)
    if raw_data is None:
        st.info(f"File {file_path.name} kosong.")
    elif "error" in raw_data:
        st.error(raw_data['error'])
    else:
        st.json(raw_data)