# Auto Trade Bot/binance/trader.py
import time
from typing import Dict, Any, Tuple
from .client import BinanceClient

class Trader:
    """
    Bertanggung jawab untuk mengeksekusi trade berdasarkan keputusan yang sudah dianalisis.
    """
    def __init__(self, client: BinanceClient, usdt_per_trade: float):
        self.client = client
        self.usdt_per_trade = usdt_per_trade

    def can_execute_trade(self, decision: Dict[str, Any], account_summary: Dict[str, Any]) -> Tuple[bool, str]:
        """
        --- FUNGSI BARU ---
        Melakukan semua pemeriksaan pra-pembelian tanpa mengeksekusi order.
        Mengembalikan (True, "Alasan") jika bisa dieksekusi, atau (False, "Alasan") jika tidak.
        """
        coin_pair = decision["coin_pair"]
        base_asset = coin_pair.replace("USDT", "")

        # Pengecekan 1: Order Aktif
        open_orders = self.client.get_open_orders(symbol=coin_pair)
        if open_orders:
            return (False, f"Ditemukan {len(open_orders)} order aktif untuk {coin_pair}.")

        # Pengecekan 2: Saldo USDT
        usdt_balance = next((asset['free_balance'] for asset in account_summary.get('held_assets', []) if asset['asset'] == 'USDT'), 0)
        if usdt_balance < self.usdt_per_trade:
            return (False, f"Saldo USDT tidak cukup. Tersedia: ${usdt_balance:.2f}, Dibutuhkan: ${self.usdt_per_trade:.2f}")

        # Pengecekan 3: Aset Sudah Dimiliki
        held_asset_value = next((asset['value_in_usdt'] for asset in account_summary.get('held_assets', []) if asset['asset'] == base_asset), 0)
        if held_asset_value >= (self.usdt_per_trade * 0.5):
             return (False, f"Aset {base_asset} sudah dimiliki dengan nilai signifikan (${held_asset_value:.2f}).")

        # Pengecekan 4: Aturan Trading (Minimum Notional)
        symbol_info = self.client.get_symbol_info(coin_pair)
        if not symbol_info:
            return (False, f"Tidak dapat menemukan aturan trading untuk {coin_pair}.")
        
        min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
        if min_notional_filter and self.usdt_per_trade < float(min_notional_filter['minNotional']):
            reason = f"Jumlah trade (${self.usdt_per_trade}) di bawah minimum (${float(min_notional_filter['minNotional'])}) untuk {coin_pair}."
            return (False, reason)

        return (True, "Semua pengecekan lolos, siap untuk dieksekusi.")


    def execute_trade(self, decision: Dict[str, Any], account_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mengeksekusi satu trade, dengan memanggil can_execute_trade terlebih dahulu.
        """
        # --- PERUBAHAN: Panggil fungsi pengecekan terlebih dahulu ---
        is_buyable, reason = self.can_execute_trade(decision, account_summary)
        if not is_buyable:
            return {"status": "SKIP", "reason": reason}

        coin_pair = decision["coin_pair"]
        base_asset = coin_pair.replace("USDT", "")
        
        print(f"Memulai proses pembelian untuk {coin_pair}...")
        
        buy_order = self.client.place_market_buy_order(symbol=coin_pair, quote_order_qty=self.usdt_per_trade)
        if not buy_order or buy_order.get('status') != 'FILLED':
            return {"status": "FAIL", "reason": "Market buy order gagal dieksekusi atau tidak terisi penuh.", "details": buy_order}

        initial_filled_qty = float(buy_order['executedQty'])
        avg_price = float(buy_order['cummulativeQuoteQty']) / initial_filled_qty
        print(f"Berhasil membeli {initial_filled_qty:.6f} {base_asset} @ ~${avg_price:.4f}")
        
        print("Menunggu & mengambil saldo aktual untuk menempatkan OCO...")
        time.sleep(2) 
        updated_account_info = self.client.get_account_info()
        if not updated_account_info:
             return {"status": "CRITICAL_FAIL", "reason": "Aset dibeli tetapi GAGAL mengambil saldo terbaru untuk OCO.", "buy_order": buy_order}

        actual_balance = 0.0
        for balance in updated_account_info.get('balances', []):
            if balance['asset'] == base_asset:
                actual_balance = float(balance['free'])
                break
        
        if actual_balance <= 0:
            return {"status": "CRITICAL_FAIL", "reason": f"Aset dibeli tetapi saldo {base_asset} tidak ditemukan atau nol.", "buy_order": buy_order}
        
        print(f"Saldo aktual terdeteksi: {actual_balance} {base_asset}. Menggunakan jumlah ini untuk OCO.")

        try:
            tp_price = decision['targets'][3]['price']
            sl_price = decision['stop_losses'][0]['price']
        except (IndexError, KeyError):
            return {"status": "CRITICAL_FAIL", "reason": "Data TP4 atau SL1 tidak ditemukan pada sinyal.", "buy_order": buy_order}
            
        print(f"Menempatkan OCO Order: TP=${tp_price}, SL=${sl_price}")
        oco_order = self.client.place_oco_sell_order(
            symbol=coin_pair,
            quantity=actual_balance,
            take_profit_price=tp_price,
            stop_loss_price=sl_price
        )

        if not oco_order:
            return {"status": "CRITICAL_FAIL", "reason": "Aset berhasil dibeli tetapi GAGAL menempatkan OCO order.", "buy_order": buy_order, "details": "Cek error body dari Binance."}
        
        return {"status": "SUCCESS", "reason": "Pembelian dan penempatan OCO berhasil.", "buy_order": buy_order, "oco_order": oco_order}