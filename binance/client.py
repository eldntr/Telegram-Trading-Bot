# Auto Trade Bot/binance/client.py
import requests
from typing import Optional

class BinanceClient:
    """
    Klien untuk berinteraksi dengan API publik Binance.
    """
    BASE_API_URL = "https://api.binance.com/api/v3"

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Mengambil harga pasar saat ini untuk simbol koin tertentu.

        Args:
            symbol: Simbol pasangan trading (misalnya, 'BTCUSDT').

        Returns:
            Harga saat ini sebagai float, atau None jika terjadi kesalahan.
        """
        endpoint = f"{self.BASE_API_URL}/ticker/price"
        params = {"symbol": symbol}
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()  # Akan memunculkan error untuk status 4xx/5xx
            data = response.json()
            return float(data['price'])
        except requests.exceptions.RequestException as e:
            print(f"Error saat menghubungi Binance API untuk {symbol}: {e}")
            return None
        except (KeyError, ValueError) as e:
            print(f"Error saat mem-parsing respons dari Binance untuk {symbol}: {e}")
            return None