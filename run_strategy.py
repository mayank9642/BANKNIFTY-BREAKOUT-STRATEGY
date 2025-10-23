"""
Strategy Runner - Uses your existing Breakout5MinStrategy
"""
import sys
import os
import argparse
import logging

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main runner function"""
    parser = argparse.ArgumentParser(description='Enhanced 5-Minute Breakout Strategy')
    parser.add_argument('--simulate', action='store_true', help='Run in simulation mode (dummy data)')
    parser.add_argument('--paper', action='store_true', help='Run in paper trading mode (real data, no real trades)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set up logging to overwrite log file each run
    logging.basicConfig(filename="logs/strategy.log", level=logging.INFO, filemode="w")
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Import your strategy class
        from breakout_strategy_main import Breakout5MinStrategy
        
        print("🚀 Starting Enhanced 5-Minute Breakout Strategy")
        print("=" * 50)
        
        if args.simulate:
            print("📝 Running in SIMULATION mode (dummy data)")
        elif args.paper:
            print("📊 Running in PAPER TRADING mode (real data, no real trades)")
        else:
            print("⚠️  Running in LIVE trading mode")
            confirm = input("Are you sure? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Cancelled.")
                return
        
        print("-" * 50)
        
        # Create and run strategy
        strategy = Breakout5MinStrategy(simulation=args.simulate, paper_trading=args.paper)
        strategy.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Strategy stopped by user")
    except Exception as e:
        print(f"❌ Error running strategy: {e}")
        logging.error(f"Strategy execution failed: {e}", exc_info=True)

if __name__ == '__main__':
    main()