"""
Strategy Startup Script
Handles authentication, token validation, and strategy launch
"""

import sys
import os
import logging
import datetime
from pathlib import Path

def setup_logging():
    """Setup basic logging for startup script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_dependencies():
    """Check if all required packages are installed"""
    required_packages = [
        'pandas', 'numpy', 'matplotlib', 'seaborn', 'yfinance',
        'fyers_apiv3', 'pytz', 'pyyaml', 'websocket-client'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print(f"📦 Install with: pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_config():
    """Check if configuration is properly set up"""
    try:
        import yaml
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        client_id = config.get('fyers', {}).get('client_id', '')
        secret_key = config.get('fyers', {}).get('secret_key', '')
        
        if client_id == "YOUR_FYERS_CLIENT_ID" or not client_id:
            print("❌ Please update your Fyers Client ID in config.yaml")
            return False
        
        if secret_key == "YOUR_FYERS_SECRET_KEY" or not secret_key:
            print("❌ Please update your Fyers Secret Key in config.yaml")
            return False
        
        print("✅ Configuration looks good")
        return True
        
    except Exception as e:
        print(f"❌ Error checking config: {e}")
        return False

def check_authentication():
    """Check if we have a valid access token"""
    try:
        from token_manager import is_token_valid, ensure_valid_token
        
        if is_token_valid():
            print("✅ Access token is valid")
            return True
        else:
            print("🔄 Access token is expired or missing")
            print("🔐 Attempting to refresh token...")
            
            token = ensure_valid_token()
            if token:
                print("✅ Token refreshed successfully")
                return True
            else:
                print("❌ Failed to refresh token")
                return False
                
    except Exception as e:
        print(f"❌ Error checking authentication: {e}")
        return False

def run_strategy():
    """Launch the main strategy"""
    try:
        print("🚀 Starting Enhanced 5-Minute Breakout Strategy...")
        print("📊 Strategy will begin monitoring at market open (9:15 AM IST)")
        print("🛑 Press Ctrl+C to stop the strategy")
        print("-" * 60)
        
        from breakout_strategy import Enhanced5MinBreakoutStrategy
        
        strategy = Enhanced5MinBreakoutStrategy()
        strategy.run_strategy()
        
    except KeyboardInterrupt:
        print("\n🛑 Strategy stopped by user")
    except Exception as e:
        print(f"❌ Strategy error: {e}")
        logging.error(f"Strategy execution failed: {e}")

def run_dashboard():
    """Launch the monitoring dashboard"""
    try:
        print("📊 Starting monitoring dashboard...")
        print("🌐 Dashboard will be available at: http://localhost:8080")
        print("🛑 Press Ctrl+C to stop the dashboard")
        
        from dashboard import start_dashboard
        start_dashboard()
        
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Dashboard error: {e}")

def show_menu():
    """Show main menu"""
    print("=" * 60)
    print("🎯 ENHANCED 5-MINUTE BREAKOUT STRATEGY")
    print("=" * 60)
    print()
    print("Please choose an option:")
    print()
    print("1. 🔐 Authenticate with Fyers API")
    print("2. 🚀 Run Strategy (Live Trading)")
    print("3. 🧪 Run Strategy (Simulation Mode)")
    print("4. 📊 Launch Monitoring Dashboard")
    print("5. 📈 Analyze Performance")
    print("6. ⚙️  Check System Status")
    print("7. 🚪 Exit")
    print()

def main():
    """Main startup function"""
    setup_logging()
    
    while True:
        show_menu()
        choice = input("Enter your choice (1-7): ").strip()
        
        if choice == '1':
            print("\n🔐 FYERS API AUTHENTICATION")
            print("-" * 30)
            
            if not check_config():
                print("Please update config.yaml with your API credentials first.")
                continue
            
            from authenticate import FyersAuthenticator
            authenticator = FyersAuthenticator()
            
            use_totp = input("Do you want to use TOTP authentication? (y/n): ").lower() == 'y'
            success = authenticator.authenticate(use_totp=use_totp)
            
            if success:
                print("✅ Authentication successful!")
            else:
                print("❌ Authentication failed!")
                
        elif choice == '2':
            print("\n🚀 STARTING LIVE TRADING STRATEGY")
            print("-" * 40)
            
            # Pre-flight checks
            if not check_dependencies():
                continue
            if not check_config():
                continue
            if not check_authentication():
                continue
            
            # Confirm live trading
            confirm = input("⚠️  This will start LIVE trading. Are you sure? (yes/no): ").lower()
            if confirm != 'yes':
                print("Live trading cancelled.")
                continue
            
            # Set live mode in config
            import yaml
            with open('config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            config['simulation']['enabled'] = False
            with open('config.yaml', 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
            
            run_strategy()
            
        elif choice == '3':
            print("\n🧪 STARTING SIMULATION MODE")
            print("-" * 30)
            
            # Pre-flight checks
            if not check_dependencies():
                continue
            if not check_config():
                continue
            if not check_authentication():
                continue
            
            # Set simulation mode in config
            import yaml
            with open('config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            config['simulation']['enabled'] = True
            with open('config.yaml', 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
            
            print("📝 Running in SIMULATION mode - no real trades will be executed")
            run_strategy()
            
        elif choice == '4':
            print("\n📊 LAUNCHING MONITORING DASHBOARD")
            print("-" * 40)
            run_dashboard()
            
        elif choice == '5':
            print("\n📈 PERFORMANCE ANALYSIS")
            print("-" * 25)
            
            try:
                from strategy_analysis import main as analyze_main
                analyze_main()
            except Exception as e:
                print(f"❌ Analysis error: {e}")
                
        elif choice == '6':
            print("\n⚙️  SYSTEM STATUS CHECK")
            print("-" * 25)
            
            print("📦 Checking dependencies...")
            deps_ok = check_dependencies()
            
            print("📋 Checking configuration...")
            config_ok = check_config()
            
            print("🔐 Checking authentication...")
            auth_ok = check_authentication()
            
            if deps_ok and config_ok and auth_ok:
                print("\n✅ System is ready for trading!")
            else:
                print("\n❌ System needs attention before trading.")
                
        elif choice == '7':
            print("\n👋 Goodbye!")
            break
            
        else:
            print("\n❌ Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()