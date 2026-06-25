"""
Fyers API utilities for market data and trading
"""
import logging
import threading
import time
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
from src.config import load_config
from src.token_helper import ensure_valid_token

def get_fyers_client():
    """Get authenticated Fyers client"""
    try:
        config = load_config()
        client_id = config.get('fyers', {}).get('client_id', '')
        access_token = ensure_valid_token()
        
        if not access_token:
            logging.error("No valid access token available")
            return None
        
        fyers = fyersModel.FyersModel(
            client_id=client_id,
            token=access_token,
            log_path=""
        )
        
        # Test the connection
        profile = fyers.get_profile()
        if profile.get('s') == 'ok':
            logging.info(f"Fyers client authenticated successfully")
            return fyers
        else:
            logging.error(f"Fyers authentication failed: {profile}")
            return None
            
    except Exception as e:
        logging.error(f"Error creating Fyers client: {e}")
        return None

def get_ltp(fyers_client, symbol):
    """Get Last Traded Price for a symbol"""
    # Improved LTP fetch with retries, exponential backoff and 429 handling
    if not fyers_client:
        return None

    max_retries = 4
    backoff = 0.5
    for attempt in range(1, max_retries + 1):
        try:
            response = fyers_client.quotes(data={"symbols": symbol})

            # If the API returns a structured error, inspect and handle 429 specifically
            if isinstance(response, dict) and response.get('s') == 'error':
                code = response.get('code')
                # Rate limited or bad request - backoff longer
                logging.warning(f"Failed to get LTP for {symbol} (API error) attempt {attempt}/{max_retries}: {response}")
                if code == 429:
                    # Respectful backoff on rate limit
                    time.sleep(backoff * 4)
                else:
                    time.sleep(backoff)
                backoff *= 2
                continue

            if response and response.get('s') == 'ok' and response.get('d'):
                # Some responses use 'lp' or 'ltp'
                val = response['d'][0].get('v', {})
                if isinstance(val, dict):
                    ltp = val.get('lp') or val.get('ltp') or val.get('lt')
                else:
                    ltp = None

                if ltp is not None:
                    try:
                        return float(ltp)
                    except Exception:
                        return None

            # Unexpected response - retry a few times
            logging.debug(f"Unexpected LTP response for {symbol} (attempt {attempt}/{max_retries}): {response}")
            time.sleep(backoff)
            backoff *= 2
        except ValueError as e:
            # JSON decode or parsing issue from underlying library
            logging.error(f"JSON parsing error getting LTP for {symbol} (attempt {attempt}/{max_retries}): {e}")
            time.sleep(backoff)
            backoff *= 2
        except Exception as e:
            # Network errors, timeouts etc.
            logging.error(f"Error getting LTP for {symbol} (attempt {attempt}/{max_retries}): {e}")
            time.sleep(backoff)
            backoff *= 2

    # All retries exhausted
    logging.warning(f"Exhausted LTP fetch retries for {symbol}. Returning None")
    return None

class WebSocketManager:
    """Manage WebSocket connections for real-time data"""
    
    def __init__(self):
        self.ws = None
        self.callback_handler = None
        self.connected = False
        
    def connect(self, symbols, callback_handler):
        """Connect to WebSocket with symbols"""
        try:
            config = load_config()
            client_id = config.get('fyers', {}).get('client_id', '')
            access_token = ensure_valid_token()
            
            if not access_token:
                logging.error("No valid access token for WebSocket")
                return False
            
            self.callback_handler = callback_handler
            
            def onmessage(message):
                """Handle incoming WebSocket messages"""
                try:
                    if self.callback_handler and message:
                        # Parse message and call handler
                        if isinstance(message, dict):
                            symbol = message.get('symbol', '')
                            ltp = message.get('ltp')
                            if symbol and ltp:
                                self.callback_handler(symbol, 'ltp', ltp, message)
                except Exception as e:
                    logging.error(f"WebSocket message handler error: {e}")
            
            def onerror(message):
                """Handle WebSocket errors"""
                logging.error(f"WebSocket error: {message}")
            
            def onclose(message):
                """Handle WebSocket close"""
                logging.info(f"WebSocket closed: {message}")
                self.connected = False
            
            def onopen():
                """Handle WebSocket open"""
                logging.info("WebSocket connected successfully")
                self.connected = True
            
            # Create WebSocket connection with correct parameters
            try:
                self.ws = data_ws.FyersDataSocket(
                    access_token=access_token,
                    log_path="",
                    litemode=False,
                    write_to_file=False,
                    reconnect=True,
                    on_connect=onopen,
                    on_close=onclose,
                    on_error=onerror,
                    on_message=onmessage
                )
                
            except Exception as e:
                logging.error(f"Failed to create WebSocket connection: {e}")
                self.ws = None
                return
            
            # Subscribe to symbols
            self.ws.subscribe(symbols=symbols, data_type="SymbolUpdate")
            
            # Start WebSocket in a separate thread
            ws_thread = threading.Thread(target=self.ws.keep_running, daemon=True)
            ws_thread.start()
            
            # Wait a bit for connection
            time.sleep(2)
            
            return self.connected
            
        except Exception as e:
            logging.error(f"WebSocket connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect WebSocket"""
        try:
            if self.ws:
                self.ws.close_connection()
                self.connected = False
        except Exception as e:
            logging.error(f"WebSocket disconnect error: {e}")

# Global WebSocket manager instance
_ws_manager = None

def start_market_data_websocket(symbols, callback_handler):
    """Start WebSocket for market data"""
    global _ws_manager
    
    try:
        if _ws_manager:
            _ws_manager.disconnect()
        
        _ws_manager = WebSocketManager()
        success = _ws_manager.connect(symbols, callback_handler)
        
        if success:
            return _ws_manager
        else:
            return None
            
    except Exception as e:
        logging.error(f"Error starting WebSocket: {e}")
        return None

def stop_market_data_websocket():
    """Stop WebSocket connection"""
    global _ws_manager
    
    if _ws_manager:
        _ws_manager.disconnect()
        _ws_manager = None