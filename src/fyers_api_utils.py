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
    try:
        if not fyers_client:
            return None
            
        response = fyers_client.quotes(data={"symbols": symbol})
        if response.get('s') == 'ok' and response.get('d'):
            return response['d'][0]['v']['lp']
        else:
            logging.warning(f"Failed to get LTP for {symbol}: {response}")
            return None
    except Exception as e:
        logging.error(f"Error getting LTP for {symbol}: {e}")
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