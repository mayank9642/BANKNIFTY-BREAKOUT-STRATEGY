"""
nifty_symbol_helper.py
Fetches valid NIFTY option symbols from Fyers option chain, similar to banknifty_symbol_helper.py.
"""
import logging
from src.fyers_api_utils import get_fyers_client

FYERS_NIFTY_INDEX_SYMBOL = "NSE:NIFTY50-INDEX"

# Fetch option chain for NIFTY

def fetch_nifty_option_chain():
    fyers = get_fyers_client()
    response = fyers.option_chain(symbol=FYERS_NIFTY_INDEX_SYMBOL)
    if response.get("s") != "ok":
        logging.error(f"Failed to fetch NIFTY option chain: {response}")
        return None
    return response["data"].get("optionsChain", [])

# Select ATM option symbol for NIFTY

def get_nifty_atm_option_symbol(spot_price, expiry_date, option_type):
    """
    Returns the closest ATM option symbol for NIFTY from the option chain.
    :param spot_price: Current NIFTY spot price
    :param expiry_date: Expiry date string (e.g., '14-10-2025')
    :param option_type: 'CE' or 'PE'
    """
    options_chain = fetch_nifty_option_chain()
    if not options_chain:
        return None
    # Find closest strike
    closest = None
    min_diff = float('inf')
    for opt in options_chain:
        if opt.get('option_type') != option_type:
            continue
        if opt.get('expiry') != expiry_date:
            continue
        strike = opt.get('strike_price')
        if strike is None:
            continue
        diff = abs(strike - spot_price)
        if diff < min_diff:
            min_diff = diff
            closest = opt
    if closest:
        return closest.get('symbol')
    return None
