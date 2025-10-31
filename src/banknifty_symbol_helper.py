import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fyers_apiv3 import fyersModel
from src.config import load_config
from src.token_helper import ensure_valid_token
import datetime

if __name__ == "__main__":
    today = datetime.datetime.now()
    next_expiry = get_next_banknifty_expiry(today)
    print("Next BANKNIFTY expiry:", next_expiry)

def get_next_banknifty_expiry(current_date):
    """
    Fetch the next available BANKNIFTY expiry date from Fyers option chain after current_date.
    Returns a datetime.date object for the next expiry.
    """
    config = load_config()
    client_id = config.get('fyers', {}).get('client_id', '')
    access_token = ensure_valid_token()
    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path="")
    data = {"symbol": "NSE:NIFTYBANK-INDEX", "strikecount": 50, "timestamp": ""}
    response = fyers.optionchain(data=data)
    if response.get('s') != 'ok':
        raise Exception(f"Failed to fetch BANKNIFTY option chain: {response}")
    expiry_list = response['data']['expiryData']
    # Find the next expiry after current_date
    for exp in expiry_list:
        exp_date = datetime.datetime.strptime(exp['date'], '%d-%m-%Y').date()
        if exp_date >= current_date.date():
            return datetime.datetime(exp_date.year, exp_date.month, exp_date.day, tzinfo=current_date.tzinfo)
    # If none found, fallback to first expiry
    first_exp = expiry_list[0]['date']
    exp_date = datetime.datetime.strptime(first_exp, '%d-%m-%Y').date()
    return datetime.datetime(exp_date.year, exp_date.month, exp_date.day, tzinfo=current_date.tzinfo)
from src.config import load_config
from src.token_helper import ensure_valid_token
import datetime

def get_banknifty_option_symbol(strike, option_type, expiry_date=None):
    """
    Fetch BANKNIFTY option chain and return the exact symbol for the given strike, option type, and expiry.
    If expiry_date is None, use the nearest expiry.
    """
    config = load_config()
    client_id = config.get('fyers', {}).get('client_id', '')
    access_token = ensure_valid_token()
    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path="")
    data = {"symbol": "NSE:NIFTYBANK-INDEX", "strikecount": 50, "timestamp": ""}
    response = fyers.optionchain(data=data)
    if response.get('s') != 'ok':
        raise Exception(f"Failed to fetch BANKNIFTY option chain: {response}")
    # Find expiry
    expiry_list = response['data']['expiryData']
    if expiry_date:
        expiry_str = expiry_date.strftime('%d-%m-%Y')
        expiry_epoch = None
        for exp in expiry_list:
            if exp['date'] == expiry_str:
                expiry_epoch = exp['expiry']
                break
        if not expiry_epoch:
            expiry_epoch = expiry_list[0]['expiry']
    else:
        expiry_epoch = expiry_list[0]['expiry']
    # Find matching option symbol
    for opt in response['data']['optionsChain']:
        if (opt['strike_price'] == strike and opt['option_type'] == option_type and str(opt.get('expiry', '')) == str(expiry_epoch)):
            return opt['symbol']
    # Fallback: match by strike and type only
    for opt in response['data']['optionsChain']:
        if (opt['strike_price'] == strike and opt['option_type'] == option_type):
            return opt['symbol']
    raise Exception(f"No matching BANKNIFTY option symbol found for strike={strike}, type={option_type}")
def get_next_banknifty_expiry(current_date):
    """
    Fetch the next available BANKNIFTY expiry date from Fyers option chain after current_date.
    Returns a datetime.date object for the next expiry.
    """
    config = load_config()
    client_id = config.get('fyers', {}).get('client_id', '')
    access_token = ensure_valid_token()
    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path="")
    data = {"symbol": "NSE:NIFTYBANK-INDEX", "strikecount": 50, "timestamp": ""}
    response = fyers.optionchain(data=data)
    if response.get('s') != 'ok':
        raise Exception(f"Failed to fetch BANKNIFTY option chain: {response}")
    expiry_list = response['data']['expiryData']
    # Find the next expiry after current_date
    for exp in expiry_list:
        exp_date = datetime.datetime.strptime(exp['date'], '%d-%m-%Y').date()
        if exp_date >= current_date.date():
            return datetime.datetime(exp_date.year, exp_date.month, exp_date.day, tzinfo=current_date.tzinfo)
    # If none found, fallback to first expiry
    first_exp = expiry_list[0]['date']
    exp_date = datetime.datetime.strptime(first_exp, '%d-%m-%Y').date()
    return datetime.datetime(exp_date.year, exp_date.month, exp_date.day, tzinfo=current_date.tzinfo)

if __name__ == "__main__":
    today = datetime.datetime.now()
    next_expiry = get_next_banknifty_expiry(today)
    print("Next BANKNIFTY expiry:", next_expiry)
