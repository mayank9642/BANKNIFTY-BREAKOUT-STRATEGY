"""
Balance Reset Utility
Reset capital balance to ₹100,000 and clear all trading statistics
"""

import os
import sys

def reset_balance():
    """Reset balance to initial amount"""
    try:
        balance_file = 'logs/capital_balance.txt'
        initial_balance = 100000
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Write reset values
        with open(balance_file, 'w') as f:
            f.write(f"{initial_balance}\n")  # current_balance
            f.write(f"0\n")                  # total_trades
            f.write(f"0\n")                  # winning_trades
            f.write(f"0\n")                  # losing_trades
            f.write(f"0.0\n")                # total_profit_loss
            f.write(f"Balance reset on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        print("✅ Balance successfully reset!")
        print(f"💰 Current Balance: ₹{initial_balance:,.2f}")
        print("📊 Trading Statistics: 0 trades (0W/0L)")
        print("📈 Net P&L: ₹0.00")
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting balance: {e}")
        return False

if __name__ == "__main__":
    print("🔄 BALANCE RESET UTILITY")
    print("=" * 40)
    print("This will reset your trading capital to ₹100,000")
    print("and clear all trading statistics.")
    print()
    
    confirm = input("Are you sure you want to reset? (yes/no): ").lower().strip()
    
    if confirm in ['yes', 'y']:
        if reset_balance():
            print("\n🎉 Balance reset completed!")
        else:
            print("\n❌ Balance reset failed!")
            sys.exit(1)
    else:
        print("\n🚫 Balance reset cancelled.")
        sys.exit(0)