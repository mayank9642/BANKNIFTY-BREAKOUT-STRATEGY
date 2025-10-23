#!/usr/bin/env python3
"""
Test script to check BANKNIFTY option symbol formats with Fyers API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import load_config
from src.token_helper import ensure_valid_token
from fyers_apiv3 import fyersModel
import datetime

def test_banknifty_symbols():
    """Test BANKNIFTY option symbols"""
    try:
        config = load_config()
        client_id = config.get('fyers', {}).get('client_id', '')
        access_token = ensure_valid_token()
        
        fyers = fyersModel.FyersModel(
            client_id=client_id,
            token=access_token,
            log_path=""
        )
        
        # Test BANKNIFTY option chain
        print("Testing BANKNIFTY option chain...")
        
        # Get option chain for BANKNIFTY
        data = {
            "symbol": "NSE:NIFTYBANK-INDEX",
            "strikecount": 5,
            "timestamp": ""
        }
        
        response = fyers.optionchain(data=data)
        if response.get('s') == 'ok':
            print("✅ BANKNIFTY option chain successful!")
            
            # Print some sample symbols
            options_chain = response.get('data', {}).get('optionsChain', [])
            print(f"\nFound {len(options_chain)} option contracts:")
            
            for i, option in enumerate(options_chain[:10]):  # First 10 symbols
                symbol = option.get('symbol', '')
                strike = option.get('strike_price', '')
                option_type = option.get('option_type', '')
                print(f"{i+1}. {symbol} (Strike: {strike}, Type: {option_type})")
                
        else:
            print(f"❌ Option chain failed: {response}")
            
        # Test individual symbols
        test_symbols = [
            "NSE:BANKNIFTY25O2856400CE",  # Our current format
            "NSE:BANKNIFTY25OCT56400CE",  # Alternative format
            "NSE:BANKNIFTY2425OCT56400CE", # Another format
            "NSE:NIFTYBANK25O2856400CE",   # Using NIFTYBANK instead
        ]
        
        print(f"\nTesting individual symbol formats:")
        for symbol in test_symbols:
            try:
                response = fyers.quotes(data={"symbols": symbol})
                if response.get('s') == 'ok':
                    ltp = response['d'][0]['v']['lp']
                    print(f"✅ {symbol} → LTP: {ltp}")
                else:
                    print(f"❌ {symbol} → {response.get('message', 'Failed')}")
            except Exception as e:
                print(f"❌ {symbol} → Error: {e}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_banknifty_symbols()