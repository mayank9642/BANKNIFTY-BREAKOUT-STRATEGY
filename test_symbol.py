from datetime import datetime, timedelta
import pytz

ist = pytz.timezone('Asia/Kolkata')
today = datetime.now(ist)
print(f'Today: {today}')

days_to_thursday = (3 - today.weekday()) % 7
print(f'Days to Thursday: {days_to_thursday}')

if days_to_thursday == 0:
    if today.hour > 15 or (today.hour == 15 and today.minute >= 30):
        days_to_thursday = 7

expiry = today + timedelta(days=days_to_thursday)
print(f'Expiry: {expiry}')
print(f'Format: {expiry.day}{expiry.strftime("%b").upper()}{expiry.strftime("%y")}')

# Test with BANKNIFTY
spot = 56500
strike = round(spot / 100) * 100
print(f'Strike: {strike}')
symbol = f"NSE:BANKNIFTY-{expiry.day}-{expiry.strftime('%b').upper()}-{strike}-CE"
print(f'Symbol: {symbol}')

from symbol_formatter import convert_option_symbol_format
converted = convert_option_symbol_format(symbol)
print(f'Converted: {converted}')