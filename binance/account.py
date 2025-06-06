# Auto Trade Bot/binance/account.py
from typing import Dict, Any, Optional
from .client import BinanceClient

class AccountManager:
    """
    Mengelola fungsionalitas terkait akun Binance.
    """
    STABLECOINS = {'USDT', 'BUSD', 'USDC', 'DAI', 'TUSD'}

    def __init__(self, client: BinanceClient):
        self.client = client

    def get_account_summary(self) -> Optional[Dict[str, Any]]:
        """
        Menghasilkan ringkasan akun, termasuk aset yang dipegang dan total nilai dalam USDT.
        """
        print("Mengambil informasi akun dari Binance...")
        account_info = self.client.get_account_info()
        if not account_info or 'balances' not in account_info:
            print("Gagal mendapatkan informasi akun atau 'balances' tidak ditemukan.")
            return None
            
        print("Mengambil semua harga ticker untuk kalkulasi nilai...")
        all_tickers = self.client.get_all_tickers()
        if not all_tickers:
            print("Gagal mengambil harga ticker. Tidak dapat menghitung total nilai.")
            return {"held_assets": [], "total_balance_usdt": 0.0, "error": "Gagal mengambil harga ticker."}

        held_assets = []
        total_balance_usdt = 0.0

        print("Menghitung nilai aset yang dipegang...")
        for asset in account_info['balances']:
            asset_name = asset['asset']
            total_balance = float(asset['free']) + float(asset['locked'])

            if total_balance > 0:
                asset_value_usdt = 0.0
                if asset_name in self.STABLECOINS:
                    asset_value_usdt = total_balance
                else:
                    ticker_usdt = f"{asset_name}USDT"
                    if ticker_usdt in all_tickers:
                        price_usdt = all_tickers[ticker_usdt]
                        asset_value_usdt = total_balance * price_usdt
                
                # Hanya tambahkan ke ringkasan jika nilainya signifikan (di atas $0.01)
                if asset_value_usdt > 0.01:
                    held_assets.append({
                        "asset": asset_name,
                        "total_balance": total_balance,
                        "free_balance": float(asset['free']),
                        "locked_balance": float(asset['locked']),
                        "value_in_usdt": round(asset_value_usdt, 2)
                    })
                    total_balance_usdt += asset_value_usdt
        
        # Urutkan aset berdasarkan nilai dari yang terbesar
        held_assets.sort(key=lambda x: x['value_in_usdt'], reverse=True)

        return {
            "total_balance_usdt": round(total_balance_usdt, 2),
            "held_assets": held_assets
        }