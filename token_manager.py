"""
Token Management Utility for Fyers API
Handles token validation and refresh automatically
"""

import datetime
import sys
import os
import logging

# Add the project root directory to Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def load_config(config_file='config.yaml'):
    """Load configuration from YAML file"""
    try:
        import yaml
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
    # Always return False to enforce daily 2FA authentication
    logging.info("Daily 2FA required: always perform fresh authentication.")
    return False

def ensure_valid_token(use_totp=False):
    """
    Check if token is valid, and if not, generate a new one.
    
    Args:
        use_totp (bool): Whether to use TOTP for authentication
        
    Returns:
        str: Valid access token or None if failed
    """
    # Always require fresh authentication (no reuse/refresh)
    try:
        logging.info("Daily 2FA required: generating new access token...")
        from authenticate import FyersAuthenticator
        authenticator = FyersAuthenticator()
        success = authenticator.authenticate(use_totp=use_totp)
        if success:
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
    # Always require daily 2FA authentication
    token = ensure_valid_token(use_totp)
    return token is not None

if __name__ == "__main__":
    # Test token validation
    logging.basicConfig(level=logging.INFO)
    
    print("🔐 Daily 2FA required. Starting fresh authentication...")
    token = ensure_valid_token()
    if token:
        print("✅ Authentication successful! Token is ready to use.")
    else:
        print("❌ Failed to authenticate. Please run authenticate.py manually.")