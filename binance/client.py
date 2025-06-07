# Auto Trade Bot/binance/client.py
import time
import hmac
import hashlib
import requests
import math
import json
from typing import Optional, Dict, Any, List

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
        self.exchange_info = None

    def _generate_signature(self, data: str) -> str:
        return hmac.new(self.api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()

    def _send_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Optional[Any]:
        if params is None:
            params = {}
        
        url = f"{self.BASE_API_URL}{endpoint}"
        
        if signed:
            if not self.api_key or not self.api_secret:
                print("Error: API Key dan Secret Key diperlukan.")
                return None
            
            params['timestamp'] = int(time.time() * 1000)
            params['recvWindow'] = 5000 
            
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            signature = self._generate_signature(query_string)
            query_string += f"&signature={signature}"
            
            try:
                # Perbaikan: Menggunakan method.upper() untuk konsistensi
                req_method = method.upper()
                if req_method == 'GET':
                    response = self.session.get(f"{url}?{query_string}")
                elif req_method == 'POST':
                    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                    response = self.session.post(url, data=query_string, headers=headers)
                elif req_method == 'DELETE':
                    response = self.session.delete(f"{url}?{query_string}")
                else:
                    print(f"Metode HTTP tidak didukung: {req_method}")
                    return None

                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error saat request ke {url}: {e}")
                if e.response is not None:
                    try:
                        error_data = e.response.json()
                        print(f"Error Body dari Binance: {error_data}")
                    except json.JSONDecodeError:
                        print(f"Error Body: {e.response.text}")
                return None
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return None

    def _get_exchange_info(self):
        if self.exchange_info is None:
            print("Mengambil exchange info (aturan trading)...")
            self.exchange_info = self._send_request("GET", "/exchangeInfo")
        return self.exchange_info

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        info = self._get_exchange_info()
        if info:
            for symbol_info in info['symbols']:
                if symbol_info['symbol'] == symbol:
                    return symbol_info
        return None

    def _format_value(self, value, step_size_str: str):
        step_size = float(step_size_str)
        if step_size == 1.0:
            return str(int(float(value)))
        
        precision = abs(int(round(math.log(step_size, 10), 0)))
        factor = 10 ** precision
        floored_value = math.floor(float(value) * factor) / factor
        return f"{floored_value:.{precision}f}"
        
    def place_market_buy_order(self, symbol: str, quote_order_qty: float) -> Optional[Dict[str, Any]]:
        params = {"symbol": symbol, "side": "BUY", "type": "MARKET", "quoteOrderQty": quote_order_qty}
        return self._send_request("POST", "/order", params, signed=True)
        
    def place_market_sell_order(self, symbol: str, quantity: float) -> Optional[Dict[str, Any]]:
        """Menempatkan order MARKET SELL untuk sejumlah kuantitas tertentu."""
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            print(f"Gagal menempatkan Market Sell: tidak ditemukan info untuk {symbol}")
            return None
        
        lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
        if not lot_size_filter:
            print(f"Filter LOT_SIZE tidak ditemukan untuk {symbol}")
            return None

        formatted_quantity = self._format_value(quantity, lot_size_filter['stepSize'])
        params = {"symbol": symbol, "side": "SELL", "type": "MARKET", "quantity": formatted_quantity}
        return self._send_request("POST", "/order", params, signed=True)

    def place_oco_sell_order(self, symbol: str, quantity: float, take_profit_price: float, stop_loss_price: float) -> Optional[Dict[str, Any]]:
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            print(f"Gagal menempatkan OCO: tidak ditemukan info untuk {symbol}")
            return None
            
        filters = {f['filterType']: f for f in symbol_info['filters']}
        
        formatted_quantity = self._format_value(float(quantity), filters['LOT_SIZE']['stepSize'])
        formatted_tp_price = self._format_value(take_profit_price, filters['PRICE_FILTER']['tickSize'])
        formatted_sl_price = self._format_value(stop_loss_price, filters['PRICE_FILTER']['tickSize'])
        stop_limit_price_val = stop_loss_price * 0.995 
        formatted_sl_limit_price = self._format_value(stop_limit_price_val, filters['PRICE_FILTER']['tickSize'])

        params = {"symbol": symbol, "side": "SELL", "quantity": formatted_quantity, "price": formatted_tp_price, "stopPrice": formatted_sl_price, "stopLimitPrice": formatted_sl_limit_price, "stopLimitTimeInForce": "GTC"}
        return self._send_request("POST", "/order/oco", params, signed=True)
    
    def cancel_oco_order(self, symbol: str, order_list_id: int) -> Optional[Dict[str, Any]]:
        print(f"Membatalkan OCO orderListId: {order_list_id} untuk {symbol}...")
        params = {"symbol": symbol, "orderListId": order_list_id}
        return self._send_request("DELETE", "/orderList", params, signed=True)

    # --- BARU: Fungsi untuk membatalkan SEMUA order untuk sebuah simbol ---
    def cancel_all_open_orders_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Membatalkan semua open order untuk simbol tertentu."""
        print(f"Membatalkan SEMUA order terbuka untuk {symbol}...")
        params = {"symbol": symbol}
        # Menggunakan endpoint DELETE /openOrders yang didesain untuk ini
        return self._send_request("DELETE", "/openOrders", params, signed=True)

    def get_current_price(self, symbol: str) -> Optional[float]:
        params = {"symbol": symbol}
        data = self._send_request("GET", "/ticker/price", params)
        return float(data['price']) if data and 'price' in data else None
        
    def get_all_tickers(self) -> Optional[List[Dict[str, Any]]]:
        return self._send_request("GET", "/ticker/price")

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        return self._send_request("GET", "/account", signed=True)

    def get_open_orders(self, symbol: str = None) -> Optional[list]:
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._send_request("GET", "/openOrders", params, signed=True)