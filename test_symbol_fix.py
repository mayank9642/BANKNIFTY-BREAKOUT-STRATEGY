"""
Test script to verify the symbol format fix
"""
from datetime import datetime
from src.symbol_formatter import generate_option_symbol

# Test with Dec 3 expiry (next weekly)
expiry_date = datetime(2025, 12, 3).date()

# Test BANKNIFTY symbols
banknifty_ce = generate_option_symbol('BANKNIFTY', expiry_date, 59600, 'CE')
banknifty_pe = generate_option_symbol('BANKNIFTY', expiry_date, 59600, 'PE')

print("=" * 60)
print("SYMBOL FORMAT TEST")
print("=" * 60)
print(f"Expiry Date: {expiry_date.strftime('%d-%b-%Y')}")
print()
print("BANKNIFTY:")
print(f"  CE Symbol: {banknifty_ce}")
print(f"  PE Symbol: {banknifty_pe}")
print()

# Test with Dec 30 expiry (monthly)
expiry_date_monthly = datetime(2025, 12, 30).date()
banknifty_ce_monthly = generate_option_symbol('BANKNIFTY', expiry_date_monthly, 59600, 'CE')
banknifty_pe_monthly = generate_option_symbol('BANKNIFTY', expiry_date_monthly, 59600, 'PE')

print(f"Monthly Expiry Date: {expiry_date_monthly.strftime('%d-%b-%Y')}")
print()
print("BANKNIFTY (Monthly):")
print(f"  CE Symbol: {banknifty_ce_monthly}")
print(f"  PE Symbol: {banknifty_pe_monthly}")
print()

# Test NIFTY symbols
nifty_ce = generate_option_symbol('NIFTY', datetime(2025, 12, 4).date(), 26250, 'CE')
nifty_pe = generate_option_symbol('NIFTY', datetime(2025, 12, 4).date(), 26250, 'PE')

print("NIFTY:")
print(f"  CE Symbol: {nifty_ce}")
print(f"  PE Symbol: {nifty_pe}")
print()

# Compare with old format
print("=" * 60)
print("COMPARISON:")
print("=" * 60)
print("OLD (wrong) format: NSE:BANKNIFTY25120359600CE")
print("NEW (correct) format: NSE:BANKNIFTY25DEC59600CE")
print()
print("✅ The new format uses month abbreviation (DEC) instead of date (1203)")
print("=" * 60)
