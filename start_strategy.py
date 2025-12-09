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
        'fyers_apiv3', 'pytz', 'yaml', 'websocket'
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
        # Simple check - just verify the config file exists and has basic content
        import os
        if not os.path.exists('config.yaml'):
            print("❌ config.yaml file not found")
            return False
        
        with open('config.yaml', 'r') as f:
            content = f.read()
        
        # Basic checks for required sections
        if 'client_id:' not in content or 'secret_key:' not in content:
            print("❌ Please update your Fyers credentials in config.yaml")
            return False
            
        if 'YOUR_FYERS_CLIENT_ID' in content or 'YOUR_FYERS_SECRET_KEY' in content:
            print("❌ Please update placeholder values in config.yaml")
            return False
        
        print("✅ Configuration looks good")
        return True
        
    except Exception as e:
        print(f"❌ Error checking config: {e}")
        return False

def check_authentication():
    """Check if we have a valid access token"""
    try:
        # Simple direct config check to avoid import issues
        import datetime
        
        # Load config directly to avoid import conflicts
        try:
            import yaml
            with open('config.yaml', 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"⚠️ Could not load config: {e}")
            print("🔐 Please run authentication first (option 1)")
            return False
        
        # Check if access token exists
        access_token = config.get('fyers', {}).get('access_token', '')
        token_expiry_str = config.get('fyers', {}).get('token_expiry', '')
        
        if not access_token:
            print("🔄 No access token found")
            print("🔐 Please run authentication first (option 1)")
            return False
        
        if not token_expiry_str:
            print("⚠️ Token expiry not found, assuming token is valid")
            print("✅ Access token exists")
            return True
        
        # Check if token is expired
        try:
            expiry_time = datetime.datetime.strptime(token_expiry_str, '%Y-%m-%d %H:%M:%S')
            current_time = datetime.datetime.now()
            
            if current_time < expiry_time:
                print("✅ Access token is valid")
                return True
            else:
                print("🔄 Access token has expired")
                print("🔐 Please run authentication first (option 1)")
                return False
        except Exception as e:
            print(f"⚠️ Could not parse token expiry: {e}")
            print("✅ Access token exists (assuming valid)")
            return True
                
    except Exception as e:
        print(f"❌ Error checking authentication: {e}")
        print("🔐 Please run authentication first (option 1)")
        return False

def run_strategy():
    """Launch the main strategy"""
    try:
        print("🚀 Starting Enhanced 5-Minute Breakout Strategy...")
        print("📊 Strategy will begin monitoring at market open (9:15 AM IST)")
        print("🛑 Press Ctrl+C to stop the strategy")
        print("-" * 60)
        
        # Check config for simulation mode - use the config loader from src
        try:
            from src.config import load_config
            config = load_config()
            simulation_enabled = config.get('simulation', {}).get('enabled', False)
        except Exception as e:
            print(f"⚠️ Could not load config, defaulting to simulation mode: {e}")
            simulation_enabled = True
        
        from breakout_strategy_main import Breakout5MinStrategy
        
        if simulation_enabled:
            print("📝 Running in SIMULATION mode - no real trades will be executed")
            strategy = Breakout5MinStrategy(simulation=False, paper_trading=True)
        else:
            print("⚠️ Running in LIVE trading mode")
            strategy = Breakout5MinStrategy(simulation=False, paper_trading=False)
        
        strategy.run()
        
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

def show_balance_info():
    """Show current balance information"""
    try:
        balance_file = 'logs/capital_balance.txt'
        if os.path.exists(balance_file):
            with open(balance_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 5:
                    current_balance = float(lines[0].strip())
                    total_trades = int(lines[1].strip())
                    winning_trades = int(lines[2].strip())
                    losing_trades = int(lines[3].strip())
                    total_pnl = float(lines[4].strip())
                    
                    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                    
                    print("💰 CAPITAL STATUS")
                    print("-" * 20)
                    print(f"Current Balance: ₹{current_balance:,.2f}")
                    print(f"Total Trades: {total_trades} ({winning_trades}W/{losing_trades}L)")
                    if total_trades > 0:
                        print(f"Win Rate: {win_rate:.1f}%")
                        print(f"Net P&L: ₹{total_pnl:+,.2f}")
                    print()
                else:
                    print("💰 Capital: ₹100,000 (Initial)\n")
        else:
            print("💰 Capital: ₹100,000 (Initial)\n")
    except Exception:
        print("💰 Capital: ₹100,000 (Initial)\n")

def show_menu():
    """Show main menu"""
    print("=" * 60)
    print("🎯 ENHANCED 5-MINUTE BREAKOUT STRATEGY")
    print("=" * 60)
    print()
    show_balance_info()
    print("Please choose an option:")
    print()
    print("1. 🔐 Authenticate with Fyers API")
    print("2. 🚀 Run Strategy (Live Trading)")
    print("3. 🧪 Run Strategy (Simulation Mode)")
    print("4. 📊 Launch Monitoring Dashboard")
    print("5. 📈 Analyze Performance")
    print("6. ⚙️  Check System Status")
    print("7. � Reset Capital Balance")
    print("8. �🚪 Exit")
    print()

def main():
    """Main startup function"""
    setup_logging()
    
    while True:
        show_menu()
        choice = input("Enter your choice (1-8): ").strip()
        
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
            try:
                import re
                with open('config.yaml', 'r') as f:
                    content = f.read()
                # Simple regex replacement for simulation enabled flag
                content = re.sub(r'enabled:\s*true', 'enabled: false', content)
                with open('config.yaml', 'w') as f:
                    f.write(content)
            except Exception as e:
                print(f"⚠️ Could not update config for live mode: {e}")
            
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
            try:
                import re
                with open('config.yaml', 'r') as f:
                    content = f.read()
                # Simple regex replacement for simulation enabled flag
                content = re.sub(r'enabled:\s*false', 'enabled: true', content)
                with open('config.yaml', 'w') as f:
                    f.write(content)
            except Exception as e:
                print(f"⚠️ Could not update config for simulation mode: {e}")
            
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
            print("\n� RESET CAPITAL BALANCE")
            print("-" * 25)
            
            try:
                show_balance_info()
                confirm = input("⚠️  This will reset your balance to ₹100,000 and clear all stats. Continue? (yes/no): ").lower().strip()
                
                if confirm in ['yes', 'y']:
                    # Reset balance
                    balance_file = 'logs/capital_balance.txt'
                    initial_balance = 100000
                    
                    os.makedirs('logs', exist_ok=True)
                    with open(balance_file, 'w') as f:
                        f.write(f"{initial_balance}\n")  # current_balance
                        f.write(f"0\n")                  # total_trades
                        f.write(f"0\n")                  # winning_trades
                        f.write(f"0\n")                  # losing_trades
                        f.write(f"0.0\n")                # total_profit_loss
                        f.write(f"Reset on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    
                    print("\n✅ Balance successfully reset!")
                    print(f"💰 New Balance: ₹{initial_balance:,.2f}")
                    print("📊 Statistics cleared")
                else:
                    print("\n🚫 Balance reset cancelled.")
                    
            except Exception as e:
                print(f"❌ Error resetting balance: {e}")
                
        elif choice == '8':
            print("\n�👋 Goodbye!")
            break
            
        else:
            print("\n❌ Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()