
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import datetime
from fyers_apiv3 import fyersModel
from src.config import load_config
from src.token_helper import ensure_valid_token

def fetch_option_chain(index_symbol):
    config = load_config()
    client_id = config.get('fyers', {}).get('client_id', '')
    access_token = ensure_valid_token()
    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path="")
    data = {
        "symbol": index_symbol,
        "strikecount": 20,
        "timestamp": ""
    }
    response = fyers.optionchain(data=data)
    if response.get('s') == 'ok':
        print(f"Option chain for {index_symbol}:")
        expiry_list = response['data']['expiryData']
        print("Expiries:")
        for exp in expiry_list:
            print(f"  {exp['date']} ({exp['expiry']})")
        print("\nSample option symbols:")
        for opt in response['data']['optionsChain'][:10]:
            print(f"  {opt['symbol']} | Strike: {opt['strike_price']} | Type: {opt['option_type']}")
    else:
        print(f"Failed to fetch option chain: {response}")

if __name__ == "__main__":
    # Test for BANKNIFTY and NIFTY
    fetch_option_chain("NSE:BANKNIFTY")
    fetch_option_chain("NSE:NIFTY50-INDEX")
