# Auto Trade Bot/binance/client.py
import time
import hmac
import hashlib
import requests
from typing import Optional, Dict, Any

class BinanceClient:
    """
    Klien untuk berinteraksi dengan API Binance, mendukung endpoint publik dan privat.
    """
    BASE_API_URL = "https://api.binance.com/api/v3"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'AutoTradeBot/1.0'
        })
        if self.api_key:
            self.session.headers.update({'X-MBX-APIKEY': self.api_key})

    def _generate_signature(self, data: str) -> str:
        """Menghasilkan signature HMAC-SHA256."""
        return hmac.new(self.api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()

    def _send_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Optional[Any]:
        """Fungsi inti untuk mengirim permintaan ke API Binance."""
        if params is None:
            params = {}
        url = f"{self.BASE_API_URL}{endpoint}"
        
        if signed:
            if not self.api_key or not self.api_secret:
                print("Error: API Key dan Secret Key diperlukan untuk request yang di-sign.")
                return None
            params['timestamp'] = int(time.time() * 1000)
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            params['signature'] = self._generate_signature(query_string)

        try:
            response = self.session.request(method, url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error saat request ke {url}: {e}")
            if e.response:
                print(f"Error Code: {e.response.json().get('code')}, Message: {e.response.json().get('msg')}")
            return None
        except ValueError:
            print("Gagal mem-parsing JSON dari response.")
            return None

    # --- Metode Publik ---
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Mengambil harga pasar saat ini untuk satu simbol."""
        data = self._send_request("GET", "/ticker/price", {"symbol": symbol})
        return float(data['price']) if data and 'price' in data else None
        
    def get_all_tickers(self) -> Optional[Dict[str, float]]:
        """Mengambil harga semua ticker untuk kalkulasi yang efisien."""
        data = self._send_request("GET", "/ticker/price")
        if not data:
            return None
        return {item['symbol']: float(item['price']) for item in data}

    # --- Metode Privat (Terotentikasi) ---
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Mengambil informasi akun, termasuk daftar saldo semua aset."""
        return self._send_request("GET", "/account", signed=True)