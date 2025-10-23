"""
Enhanced Fyers API Authentication Helper
Integrates your existing authentication logic with optional TOTP support
"""

from fyers_apiv3 import fyersModel
import webbrowser
import urllib.parse
import json
import os
import sys
import yaml
import logging
import time
import datetime

class FyersAuthenticator:
    """Enhanced helper class for Fyers API authentication"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize with configuration"""
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            raise Exception(f"Failed to load config: {e}")
    
    def _save_config(self):
        """Save configuration back to YAML file"""
        try:
            with open(self.config_path, 'w') as file:
                yaml.dump(self.config, file, default_flow_style=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save config: {e}")

    def generate_auth_code(self, use_totp=False):
        """
        Generate authentication code URL and open in browser
        
        Args:
            use_totp (bool): If True, use TOTP authentication instead of redirect URL
        """
        client_id = self.config['fyers']['client_id']
        redirect_uri = self.config['fyers']['redirect_uri']
        
        session = fyersModel.SessionModel(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type="code",
            state="state"
        )
        
        auth_url = session.generate_authcode()
        print(f"Opening URL: {auth_url}")
        print("Please login and authorize the application...")
        webbrowser.open(auth_url, new=1)
        
        if use_totp and self.config.get('fyers', {}).get('totp_key'):
            try:
                import pyotp
                totp_key = self.config['fyers']['totp_key']
                totp = pyotp.TOTP(totp_key).now()
                print(f"Generated TOTP: {totp}")
                print("Using TOTP for authentication.")
                # When using TOTP, the flow is different and requires additional API calls
                # This is just a placeholder - implement according to Fyers TOTP flow
            except ImportError:
                print("pyotp package not installed. Please install it with: pip install pyotp")
                print("Falling back to URL redirect method.")
        
        # Get the auth code from the URL
        print("\nAfter authentication, you'll be redirected to a page.")
        print("Please copy the FULL URL from your browser's address bar and paste it below.")
        redirect_url = input("Enter the redirect URL: ")
        
        # Parse the auth code from the URL
        try:
            if "auth_code=" in redirect_url:
                auth_code = redirect_url[redirect_url.index('auth_code=')+10:redirect_url.index('&state')]
            else:
                print("Could not find auth_code in the URL. Please enter it manually.")
                auth_code = input("Enter the auth code: ")
            
            return auth_code
        except Exception as e:
            print(f"Error parsing auth code: {str(e)}")
            auth_code = input("Enter the auth code manually: ")
            return auth_code

    def generate_access_token(self, use_totp=False):
        """
        Generate access token using the authorization code
        
        Args:
            use_totp (bool): If True, use TOTP authentication
            
        Returns:
            str: Access token if successful, None otherwise
        """
        try:
            client_id = self.config['fyers']['client_id']
            secret_key = self.config['fyers']['secret_key']
            redirect_uri = self.config['fyers']['redirect_uri']
            
            # Get authentication code
            auth_code = self.generate_auth_code(use_totp)
            
            # Create session model for token generation
            session = fyersModel.SessionModel(
                client_id=client_id,
                secret_key=secret_key,
                redirect_uri=redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            
            # Set the auth code and generate token
            session.set_token(auth_code)
            response = session.generate_token()
            
            if response.get('access_token'):
                # Save the access token to config
                self.config['fyers']['access_token'] = response['access_token']
                
                # Save token expiry time (default is usually 1 day)
                expiry_time = datetime.datetime.now() + datetime.timedelta(days=1)
                self.config['fyers']['token_expiry'] = expiry_time.strftime('%Y-%m-%d %H:%M:%S')
                
                # Write updated config to file
                self._save_config()
                    
                print(f"Access token generated and saved successfully.")
                print(f"Token valid until: {self.config['fyers']['token_expiry']}")
                
                # Also save token to access.txt for compatibility
                with open('access.txt', 'w') as f:
                    f.write(response['access_token'])
                    
                return response['access_token']
            else:
                print(f"Failed to generate access token: {response}")
                return None
                
        except Exception as e:
            print(f"Error generating access token: {str(e)}")
            logging.error(f"Failed to generate access token: {str(e)}")
            return None
    
    def authenticate(self, use_totp=False, force_refresh=False):
        """Complete authentication process with enhanced options"""
        print("=== Enhanced Fyers API Authentication ===\n")
        
        # Check if we already have credentials
        if not self.config['fyers']['client_id'] or self.config['fyers']['client_id'] == "YOUR_FYERS_CLIENT_ID":
            print("Please update your Fyers API credentials in config.yaml:")
            print("1. client_id: Your Fyers Client ID")
            print("2. secret_key: Your Fyers Secret Key")
            print("3. Optional: totp_key for TOTP authentication")
            print("\nYou can find these in your Fyers API dashboard.")
            return False
        
        # Check if token already exists and is valid
        if not force_refresh and self.config['fyers'].get('access_token') and self.config['fyers'].get('token_expiry'):
            try:
                expiry_time = datetime.datetime.strptime(self.config['fyers']['token_expiry'], '%Y-%m-%d %H:%M:%S')
                if datetime.datetime.now() < expiry_time:
                    print("✅ Valid access token already exists!")
                    # Test the existing token
                    fyers = fyersModel.FyersModel(
                        client_id=self.config['fyers']['client_id'],
                        token=self.config['fyers']['access_token'],
                        log_path=""
                    )
                    profile = fyers.get_profile()
                    if profile['s'] == 'ok':
                        print(f"✅ Token verified successfully!")
                        print(f"User: {profile['data']['name']}")
                        print(f"Valid until: {self.config['fyers']['token_expiry']}")
                        return True
                    else:
                        print("❌ Existing token is invalid. Generating new token...")
                else:
                    print("⚠️ Existing token has expired. Generating new token...")
            except Exception as e:
                print(f"⚠️ Error checking existing token: {e}. Generating new token...")
        
        try:
            # Generate new access token
            access_token = self.generate_access_token(use_totp)
            
            if access_token:
                # Test the new token
                fyers = fyersModel.FyersModel(
                    client_id=self.config['fyers']['client_id'],
                    token=access_token,
                    log_path=""
                )
                
                profile = fyers.get_profile()
                if profile['s'] == 'ok':
                    print(f"\n✅ Authentication successful!")
                    print(f"User: {profile['data'].get('name', 'N/A')}")
                    email = profile['data'].get('email', None)
                    if email:
                        print(f"Email: {email}")
                    else:
                        print("Email: (not provided by Fyers API)")
                    print(f"Token: {access_token[:20]}...")
                    return True
                else:
                    print(f"❌ Token verification failed: {profile}")
                    return False
            else:
                print("❌ Failed to generate access token.")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False

def main():
    """Main authentication function with enhanced options"""
    try:
        import argparse
        parser = argparse.ArgumentParser(description="Fyers API Authentication Helper")
        parser.add_argument('--force', action='store_true', help='Force refresh of access token')
        args = parser.parse_args()

        print("🔐 Fyers API Authentication Options:")
        print("1. Standard authentication (redirect URL)")
        print("2. TOTP authentication (if configured)")

        choice = input("\nChoose authentication method (1 or 2): ").strip()
        use_totp = choice == "2"

        if use_totp:
            print("\n📱 TOTP authentication selected.")
            print("Make sure you have configured 'totp_key' in your config.yaml")
            print("Install pyotp if not already installed: pip install pyotp")

        force_refresh = args.force
        if not force_refresh:
            force_prompt = input("Force token refresh even if valid? (y/n): ").strip().lower()
            force_refresh = force_prompt == 'y'
        authenticator = FyersAuthenticator()
        success = authenticator.authenticate(use_totp=use_totp, force_refresh=force_refresh)
        if success:
            print("\n🎉 Authentication completed successfully!")
            print("📊 You're ready to run the strategy!")
            print("\n🚀 Next steps:")
            print("   1. Test in simulation mode: Set simulation.enabled: true in config.yaml")
            print("   2. Run strategy: python breakout_strategy.py")
            print("   3. Monitor dashboard: python dashboard.py")
        else:
            print("\n❌ Authentication failed. Please try again.")
            print("\n🔧 Troubleshooting:")
            print("   1. Check your API credentials in config.yaml")
            print("   2. Ensure your Fyers account has API access enabled")
            print("   3. Verify redirect URI matches your Fyers app settings")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
"""
Enhanced Fyers API Authentication Helper
Integrates your existing authentication logic with optional TOTP support
"""

from fyers_apiv3 import fyersModel
import webbrowser
import urllib.parse
import json
import os
import sys
import yaml
import logging
import time
import datetime

class FyersAuthenticator:
    """Enhanced helper class for Fyers API authentication"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize with configuration"""
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            raise Exception(f"Failed to load config: {e}")
    
    def _save_config(self):
        """Save configuration back to YAML file"""
        try:
            with open(self.config_path, 'w') as file:
                yaml.dump(self.config, file, default_flow_style=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save config: {e}")

    def generate_auth_code(self, use_totp=False):
        """
        Generate authentication code URL and open in browser
        
        Args:
            use_totp (bool): If True, use TOTP authentication instead of redirect URL
        """

        """
        Simple Fyers API Authentication Script
        Generates and saves Fyers access token to config.yaml
        """
        import yaml
        import logging
        from fyers_apiv3 import fyersModel

        class SimpleAuthenticator:
            def __init__(self, config_path='config.yaml'):
                self.config_path = config_path
                self.config = self._load_config()

            def _load_config(self):
                try:
                    with open(self.config_path, 'r') as f:
                        return yaml.safe_load(f)
                except Exception as e:
                    logging.error(f'Failed to load config: {e}')
                    return {}

            def _save_config(self):
                try:
                    with open(self.config_path, 'w') as f:
                        yaml.safe_dump(self.config, f, default_flow_style=False, indent=2)
                except Exception as e:
                    logging.error(f'Failed to save config: {e}')

            def authenticate(self):
                print('=== Fyers API Authentication Script Started ===')
                fyers_cfg = self.config.get('fyers', {})
                client_id = fyers_cfg.get('client_id')
                secret_key = fyers_cfg.get('secret_key')
                redirect_uri = fyers_cfg.get('redirect_uri')
                if not all([client_id, secret_key, redirect_uri]):
                    logging.error('Missing Fyers credentials in config.yaml')
                    print('\n❌ ERROR: Missing Fyers credentials in config.yaml')
                    print('Please update config.yaml with your Fyers API credentials:')
                    print('  client_id: Your Fyers Client ID')
                    print('  secret_key: Your Fyers Secret Key')
                    print('  redirect_uri: Your Fyers Redirect URI')
                    print('Script exiting. No authentication performed.')
                    return False
                session = fyersModel.SessionModel(
                    client_id=client_id,
                    secret_key=secret_key,
                    redirect_uri=redirect_uri,
                    response_type='code',
                    grant_type='authorization_code'
                )
                print('\nGo to the following URL and log in to Fyers:')
                print(session.generate_authcode())
                auth_code = input('\nPaste the response code here: ').strip()
                session.set_token(auth_code)
                try:
                    token_response = session.generate_token()
                    access_token = token_response['access_token']
                    fyers_cfg['access_token'] = access_token
                    self.config['fyers'] = fyers_cfg
                    self._save_config()
                    logging.info('Access token saved to config.yaml')
                    print('✅ Access token saved to config.yaml')
                    print('=== Fyers API Authentication Script Finished ===')
                    return True
                except Exception as e:
                    logging.error(f'Error generating access token: {e}')
                    print(f'❌ Error generating access token: {e}')
                    print('Script exiting. No authentication performed.')
                    return False

        def main():
            logging.basicConfig(level=logging.INFO)
            authenticator = SimpleAuthenticator()
            authenticator.authenticate()

        if __name__ == '__main__':
            main()