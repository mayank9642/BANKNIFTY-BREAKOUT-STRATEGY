"""
Token Management Utility for Fyers API
Handles token validation and refresh automatically
"""

import datetime
import sys
import os
import logging
import yaml

# Add the project root directory to Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def load_config(config_file='config.yaml'):
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return {}

def is_token_valid():
    """
    Check if the access token is still valid or needs to be refreshed.
    
    Returns:
        bool: True if token is valid, False otherwise
    """
    try:
        config = load_config()
        token_expiry_str = config.get('fyers', {}).get('token_expiry', '')
        
        if not token_expiry_str:
            logging.warning("No token expiry found in config.")
            return False
        
        expiry_time = datetime.datetime.strptime(token_expiry_str, '%Y-%m-%d %H:%M:%S')
        current_time = datetime.datetime.now()
        
        # Add a buffer of 5 minutes to ensure we don't use a token that's about to expire
        buffer_time = datetime.timedelta(minutes=5)
        
        if current_time + buffer_time < expiry_time:
            logging.info("Token is still valid.")
            return True
        else:
            logging.info("Token expired or about to expire.")
            return False
    
    except Exception as e:
        logging.error(f"Error checking token validity: {str(e)}")
        return False

def ensure_valid_token(use_totp=False):
    """
    Check if token is valid, and if not, generate a new one.
    
    Args:
        use_totp (bool): Whether to use TOTP for authentication
        
    Returns:
        str: Valid access token or None if failed
    """
    try:
        if is_token_valid():
            config = load_config()
            access_token = config.get('fyers', {}).get('access_token', '')
            if access_token:
                logging.info("Using existing valid token.")
                return access_token
        
        # Token is invalid or missing, generate new one
        logging.info("Generating new access token...")
        
        # Import the authentication function
        from authenticate import FyersAuthenticator
        
        authenticator = FyersAuthenticator()
        success = authenticator.authenticate(use_totp=use_totp)
        
        if success:
            # Reload config to get the new token
            config = load_config()
            return config.get('fyers', {}).get('access_token', '')
        else:
            logging.error("Failed to generate new access token.")
            return None
            
    except Exception as e:
        logging.error(f"Error ensuring valid token: {str(e)}")
        return None

def refresh_token_if_needed(use_totp=False):
    """
    Convenience function to refresh token if needed before strategy execution
    
    Args:
        use_totp (bool): Whether to use TOTP for authentication
        
    Returns:
        bool: True if token is valid/refreshed successfully, False otherwise
    """
    token = ensure_valid_token(use_totp)
    return token is not None

if __name__ == "__main__":
    # Test token validation
    logging.basicConfig(level=logging.INFO)
    
    print("🔐 Checking token validity...")
    
    if is_token_valid():
        print("✅ Token is valid and ready to use!")
    else:
        print("❌ Token is invalid or expired.")
        print("🔄 Attempting to refresh token...")
        
        token = ensure_valid_token()
        if token:
            print("✅ Token refreshed successfully!")
        else:
            print("❌ Failed to refresh token. Please run authenticate.py manually.")