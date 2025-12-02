"""
Test Fyers API with different symbol formats to find which one works
"""
import logging
from datetime import datetime
from fyers_apiv3 import fyersModel
from config import load_config
from token_manager import ensure_valid_token
from src.symbol_formatter import generate_option_symbol

logging.basicConfig(level=logging.INFO)

def test_fyers_symbols():
    """Test different symbol formats with Fyers API"""
    
    # Initialize Fyers client
    config = load_config()
    client_id = config['fyers']['client_id']
    access_token = ensure_valid_token()
    
    if not access_token:
        print("❌ No valid access token")
        return
    
    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path="")
    
    print("=" * 80)
    print("TESTING FYERS API SYMBOL FORMATS")
    print("=" * 80)
    
    # Get current BANKNIFTY spot price for ATM strike
    spot_response = fyers.quotes(data={"symbols": "NSE:NIFTYBANK-INDEX"})
    if spot_response.get('s') == 'ok':
        spot_price = spot_response['d'][0]['v']['lp']
        print(f"\n📊 BANKNIFTY Spot: {spot_price:.2f}")
        atm_strike = round(spot_price / 100) * 100  # Round to nearest 100
        print(f"📍 ATM Strike: {atm_strike}")
    else:
        print("❌ Failed to get spot price")
        atm_strike = 59600  # Fallback
    
    print("\n" + "=" * 80)
    print("TEST 1: Weekly Expiry (Dec 3, 2025)")
    print("=" * 80)
    
    # Test weekly expiry symbols
    weekly_expiry = datetime(2025, 12, 3).date()
    weekly_ce = generate_option_symbol('BANKNIFTY', weekly_expiry, atm_strike, 'CE')
    weekly_pe = generate_option_symbol('BANKNIFTY', weekly_expiry, atm_strike, 'PE')
    
    print(f"\n🔹 Testing CE: {weekly_ce}")
    response = fyers.quotes(data={"symbols": weekly_ce})
    if response.get('s') == 'ok' and 'd' in response:
        data = response['d'][0]
        if 'v' in data and isinstance(data['v'], dict):
            if 'lp' in data['v']:
                print(f"   ✅ SUCCESS! LTP: {data['v']['lp']}")
            elif data['v'].get('s') == 'error':
                print(f"   ❌ ERROR: {data['v'].get('errmsg', 'Unknown error')}")
            else:
                print(f"   ⚠️  Response: {data['v']}")
        else:
            print(f"   ⚠️  Unexpected structure: {data}")
    else:
        print(f"   ❌ FAILED: {response}")
    
    print(f"\n🔹 Testing PE: {weekly_pe}")
    response = fyers.quotes(data={"symbols": weekly_pe})
    if response.get('s') == 'ok' and 'd' in response:
        data = response['d'][0]
        if 'v' in data and isinstance(data['v'], dict):
            if 'lp' in data['v']:
                print(f"   ✅ SUCCESS! LTP: {data['v']['lp']}")
            elif data['v'].get('s') == 'error':
                print(f"   ❌ ERROR: {data['v'].get('errmsg', 'Unknown error')}")
            else:
                print(f"   ⚠️  Response: {data['v']}")
        else:
            print(f"   ⚠️  Unexpected structure: {data}")
    else:
        print(f"   ❌ FAILED: {response}")
    
    print("\n" + "=" * 80)
    print("TEST 2: Monthly Expiry (Dec 30, 2025)")
    print("=" * 80)
    
    # Test monthly expiry symbols
    monthly_expiry = datetime(2025, 12, 30).date()
    monthly_ce = generate_option_symbol('BANKNIFTY', monthly_expiry, atm_strike, 'CE')
    monthly_pe = generate_option_symbol('BANKNIFTY', monthly_expiry, atm_strike, 'PE')
    
    print(f"\n🔹 Testing CE: {monthly_ce}")
    response = fyers.quotes(data={"symbols": monthly_ce})
    if response.get('s') == 'ok' and 'd' in response:
        data = response['d'][0]
        if 'v' in data and isinstance(data['v'], dict):
            if 'lp' in data['v']:
                print(f"   ✅ SUCCESS! LTP: {data['v']['lp']}")
            elif data['v'].get('s') == 'error':
                print(f"   ❌ ERROR: {data['v'].get('errmsg', 'Unknown error')}")
            else:
                print(f"   ⚠️  Response: {data['v']}")
        else:
            print(f"   ⚠️  Unexpected structure: {data}")
    else:
        print(f"   ❌ FAILED: {response}")
    
    print(f"\n🔹 Testing PE: {monthly_pe}")
    response = fyers.quotes(data={"symbols": monthly_pe})
    if response.get('s') == 'ok' and 'd' in response:
        data = response['d'][0]
        if 'v' in data and isinstance(data['v'], dict):
            if 'lp' in data['v']:
                print(f"   ✅ SUCCESS! LTP: {data['v']['lp']}")
            elif data['v'].get('s') == 'error':
                print(f"   ❌ ERROR: {data['v'].get('errmsg', 'Unknown error')}")
            else:
                print(f"   ⚠️  Response: {data['v']}")
        else:
            print(f"   ⚠️  Unexpected structure: {data}")
    else:
        print(f"   ❌ FAILED: {response}")
    
    print("\n" + "=" * 80)
    print("TEST 3: Query Optionchain API for Available Expiries")
    print("=" * 80)
    
    response = fyers.optionchain({"symbol": "NSE:NIFTYBANK-INDEX"})
    print(f"\n📋 Optionchain API Response:")
    if response and response.get('s') == 'ok':
        if 'd' in response:
            expiry_dates = response['d'].get('expiryDates', [])
            print(f"   ✅ Available expiries: {expiry_dates[:5]}")  # Show first 5
            if expiry_dates:
                print(f"\n   🎯 Next expiry from API: {expiry_dates[0]}")
        else:
            print(f"   ⚠️  No data in response: {response}")
    else:
        print(f"   ❌ API failed: {response}")
    
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("Check which symbol format worked above (showed ✅ SUCCESS)")
    print("=" * 80)

if __name__ == "__main__":
    test_fyers_symbols()
