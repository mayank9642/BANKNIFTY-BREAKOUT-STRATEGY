from fyers_apiv3 import fyersModel
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
