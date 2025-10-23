"""
Token helper for Fyers API authentication
"""
import datetime
import logging
from src.config import load_config

def is_token_valid():
    """Check if the access token is still valid"""
    try:
        config = load_config()
        token_expiry_str = config.get('fyers', {}).get('token_expiry', '')
        
        if not token_expiry_str:
            logging.warning("No token expiry found in config.")
            return False
        
        expiry_time = datetime.datetime.strptime(token_expiry_str, '%Y-%m-%d %H:%M:%S')
        current_time = datetime.datetime.now()
        
        # Add a buffer of 5 minutes
        buffer_time = datetime.timedelta(minutes=5)
        
        if current_time + buffer_time < expiry_time:
            return True
        else:
            logging.info("Token expired or about to expire.")
            return False
    
    except Exception as e:
        logging.error(f"Error checking token validity: {str(e)}")
        return False

def ensure_valid_token():
    """Ensure we have a valid token, refresh if needed"""
    try:
        if is_token_valid():
            config = load_config()
            return config.get('fyers', {}).get('access_token', '')
        else:
            logging.error("Token is invalid. Please re-authenticate using authenticate.py")
            return None
    except Exception as e:
        logging.error(f"Error ensuring valid token: {e}")
        return None