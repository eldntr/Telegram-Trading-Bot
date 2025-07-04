# Auto Trade Bot/binance/trader.py
import time
from typing import Dict, Any, Tuple
from .client import BinanceClient

class Trader:
    """
    Bertanggung jawab untuk mengeksekusi trade berdasarkan keputusan yang sudah dianalisis.
    """
    def __init__(self, client: BinanceClient, user_config: Dict[str, Any]):
        self.client = client
        self.user_config = user_config

    def get_risk_config(self, risk_level: str) -> Dict[str, Any]:
        """Mengembalikan konfigurasi yang sesuai berdasarkan level risiko."""
        risk_management = self.user_config.get("risk_management", {})
        if risk_level and risk_level.lower() == 'high':
            return risk_management.get("high_risk", {})
        return risk_management.get("normal_risk", {})

    def can_execute_trade(self, decision: Dict[str, Any], account_summary: Dict[str, Any], open_positions_by_risk: Dict[str, int]) -> Tuple[bool, str]:
        """
        Melakukan semua pemeriksaan pra-pembelian tanpa mengeksekusi order.
        """
        coin_pair = decision["coin_pair"]
        risk_level = decision.get("risk_level", "normal").lower()
        risk_config = self.get_risk_config(risk_level)
        usdt_per_trade = risk_config["usdt_amount_per_trade"]
        base_asset = coin_pair.replace("USDT", "")

        # Pengecekan 1: Posisi Maksimal Berdasarkan Risiko
        current_positions_for_risk = open_positions_by_risk.get(risk_level, 0)
        if current_positions_for_risk >= risk_config["max_positions"]:
            return (False, f"Batas posisi {risk_level.upper()} ({risk_config['max_positions']}) tercapai.")

        # Pengecekan 2: Order Aktif
        open_orders = self.client.get_open_orders(symbol=coin_pair)
        if open_orders:
            return (False, f"Ditemukan {len(open_orders)} order aktif untuk {coin_pair}.")

        # Pengecekan 3: Saldo USDT
        usdt_balance = next((asset['free_balance'] for asset in account_summary.get('held_assets', []) if asset['asset'] == 'USDT'), 0)
        if usdt_balance < usdt_per_trade:
            return (False, f"Saldo USDT tidak cukup. Tersedia: ${usdt_balance:.2f}, Dibutuhkan: ${usdt_per_trade:.2f}")

        # Pengecekan 4: Aset Sudah Dimiliki
        held_asset_value = next((asset['value_in_usdt'] for asset in account_summary.get('held_assets', []) if asset['asset'] == base_asset), 0)
        if held_asset_value >= (usdt_per_trade * 0.5):
             return (False, f"Aset {base_asset} sudah dimiliki dengan nilai signifikan (${held_asset_value:.2f}).")

        # Pengecekan 5: Aturan Trading (Minimum Notional)
        symbol_info = self.client.get_symbol_info(coin_pair)
        if not symbol_info:
            return (False, f"Tidak dapat menemukan aturan trading untuk {coin_pair}.")

        min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)
        if min_notional_filter and usdt_per_trade < float(min_notional_filter['minNotional']):
            reason = f"Jumlah trade (${usdt_per_trade}) di bawah minimum (${float(min_notional_filter['minNotional'])}) untuk {coin_pair}."
            return (False, reason)

        return (True, "Semua pengecekan lolos, siap untuk dieksekusi.")


    def execute_trade(self, decision: Dict[str, Any], account_summary: Dict[str, Any], open_positions_by_risk: Dict[str, int]) -> Dict[str, Any]:
        """
        Mengeksekusi satu trade, dengan memanggil can_execute_trade terlebih dahulu.
        """
        is_buyable, reason = self.can_execute_trade(decision, account_summary, open_positions_by_risk)
        if not is_buyable:
            return {"status": "SKIP", "reason": reason}

        coin_pair = decision["coin_pair"]
        risk_level = decision.get("risk_level", "normal").lower()
        risk_config = self.get_risk_config(risk_level)
        usdt_per_trade = risk_config["usdt_amount_per_trade"]
        base_asset = coin_pair.replace("USDT", "")

        print(f"Memulai proses pembelian untuk {coin_pair} ({risk_level.upper()} Risk)...")

        buy_order = self.client.place_market_buy_order(symbol=coin_pair, quote_order_qty=usdt_per_trade)
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
            # Mengambil level TP dan SL dari konfigurasi
            tp_level_idx = risk_config["tp_level"] - 1
            sl_level_idx = risk_config["sl_level"]

            if tp_level_idx < 0 or tp_level_idx >= len(decision['targets']):
                 return {"status": "CRITICAL_FAIL", "reason": f"Level TP {risk_config['tp_level']} tidak valid untuk sinyal ini.", "buy_order": buy_order}

            tp_price = decision['targets'][tp_level_idx]['price']

            # Logika untuk level SL
            if sl_level_idx == 0:
                # Level 0 berarti SL di harga beli rata-rata aktual
                sl0_percentage = self.user_config.get("position_management", {}).get("sl0_percentage_from_entry", 0.995)
                sl_price = avg_price * sl0_percentage
            elif sl_level_idx > 0 and (sl_level_idx - 1) < len(decision['stop_losses']):
                # Level 1 atau 2 menggunakan SL dari sinyal
                sl_price = decision['stop_losses'][sl_level_idx - 1]['price']
            else:
                 return {"status": "CRITICAL_FAIL", "reason": f"Level SL {risk_config['sl_level']} tidak valid untuk sinyal ini.", "buy_order": buy_order}
        
        except (IndexError, KeyError, TypeError) as e:
            return {"status": "CRITICAL_FAIL", "reason": f"Data TP/SL tidak ditemukan pada sinyal atau config. Error: {e}", "buy_order": buy_order}

        print(f"Menempatkan OCO Order: TP={tp_price} (Level {risk_config['tp_level']}), SL={sl_price} (Level {risk_config['sl_level']})")
        oco_order = self.client.place_oco_sell_order(
            symbol=coin_pair,
            quantity=actual_balance,
            take_profit_price=tp_price,
            stop_loss_price=sl_price
        )

        if not oco_order:
            return {"status": "CRITICAL_FAIL", "reason": "Aset berhasil dibeli tetapi GAGAL menempatkan OCO order.", "buy_order": buy_order, "details": "Cek error body dari Binance."}

        return {"status": "SUCCESS", "reason": "Pembelian dan penempatan OCO berhasil.", "buy_order": buy_order, "oco_order": oco_order}