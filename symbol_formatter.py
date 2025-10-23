"""
Symbol formatter for Fyers API compatibility
"""
import re
import datetime
import logging
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def convert_option_symbol_format(symbol):
    """
    Convert option symbols to Fyers API compatible format.
    
    Examples:
    - NSE:NIFTY-17-OCT-25200-CE -> NSE:NIFTY17OCT2525200CE
    - NIFTY-17-OCT-25200-CE -> NIFTY17OCT2525200CE
    """
    if not symbol:
        return symbol
        
    try:
        original_symbol = symbol
        logger.debug(f"Converting symbol: {symbol}")
        
        # If already in correct format, return as is
        if re.match(r'^(NSE:)?(NIFTY|BANKNIFTY)\d{1,2}[A-Z]{3}\d{2}\d{4,5}(CE|PE)$', symbol):
            return symbol
        
        # Preserve the prefix (NSE:, MCX:, etc.)
        prefix = ""
        if ":" in symbol:
            prefix, symbol = symbol.split(":", 1)
            prefix = prefix + ":"
        
        # Use regex to extract components
        # Pattern for symbols like: NIFTY-17-OCT-25200-CE or NIFTY_17_OCT_25200_CE
        pattern = r'(NIFTY|BANKNIFTY)[-_\s]*(\d{1,2})[-_\s]*([A-Z]{3})[-_\s]*(\d{2,4})[-_\s]*(\d{4,5})[-_\s]*(CE|PE)'
        match = re.search(pattern, symbol, re.IGNORECASE)
        
        if match:
            underlying, day, month, year, strike, option_type = match.groups()
            
            # Convert to 2-digit year if needed
            if len(year) == 4:
                year = year[-2:]
            
            # Ensure day is properly formatted
            day = day.zfill(2)
            
            # Build the final symbol
            new_symbol = f"{prefix}{underlying}{day}{month.upper()}{year}{strike}{option_type.upper()}"
            
            logger.debug(f"Converted: {original_symbol} → {new_symbol}")
            return new_symbol
        
        # If no match with the pattern, try to parse more flexibly
        # Extract underlying
        underlying_match = re.search(r'(NIFTY|BANKNIFTY)', symbol, re.IGNORECASE)
        if not underlying_match:
            # Silently return original if we can't parse - it may still work
            return original_symbol
        underlying = underlying_match.group(1).upper()
        
        # Extract option type
        option_type_match = re.search(r'(CE|PE)', symbol, re.IGNORECASE)
        if not option_type_match:
            # Silently return original if we can't parse - it may still work
            return original_symbol
        option_type = option_type_match.group(1).upper()
        
        # Extract strike price (4-5 digits) - look for longest sequence
        strike_matches = re.findall(r'\d{4,5}', symbol)
        if not strike_matches:
            # Silently return original if we can't parse - it may still work
            return original_symbol
        # Take the longest match (most likely the strike price)
        strike = max(strike_matches, key=len)
        
        # Extract date components
        date_match = re.search(r'(\d{1,2})[-_\s]*([A-Z]{3})[-_\s]*(\d{2,4})', symbol, re.IGNORECASE)
        if date_match:
            day, month, year = date_match.groups()
            if len(year) == 4:
                year = year[-2:]
            day = day.zfill(2)
            month = month.upper()
        else:
            # Use current month's expiry if date not found
            today = datetime.datetime.now()
            day = "24"  # Common monthly expiry date
            month = today.strftime('%b').upper()
            year = today.strftime('%y')
            logger.debug(f"Date not found in {symbol}, using default: {day}{month}{year}")
        
        # Build the final symbol
        new_symbol = f"{prefix}{underlying}{day}{month}{year}{strike}{option_type}"
        
        logger.debug(f"Converted: {original_symbol} → {new_symbol}")
        return new_symbol
    
    except Exception as e:
        logger.error(f"Error converting option symbol {symbol}: {e}")
        return original_symbol  # Return original symbol if conversion fails

def extract_option_details(symbol):
    """
    Extract option details from a symbol.
    
    Returns:
        dict: Contains underlying, strike, option_type, expiry_date
    """
    try:
        # Remove prefix if present
        clean_symbol = symbol.split(":")[-1] if ":" in symbol else symbol
        
        # Try to match the pattern
        pattern = r'(NIFTY|BANKNIFTY)(\d{1,2})([A-Z]{3})(\d{2})(\d{4,5})(CE|PE)'
        match = re.search(pattern, clean_symbol, re.IGNORECASE)
        
        if match:
            underlying, day, month, year, strike, option_type = match.groups()
            
            # Convert month abbreviation to number
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            month_num = month_map.get(month.upper())
            
            # Create expiry date (assuming 20xx year format)
            full_year = 2000 + int(year) if int(year) > 50 else 2000 + int(year)
            if int(year) < 25:  # Assuming years < 25 are 20xx
                full_year = 2000 + int(year)
            else:
                full_year = 1900 + int(year)
                
            expiry_date = datetime.date(full_year, month_num, int(day))
            
            return {
                'underlying': underlying.upper(),
                'strike': int(strike),
                'option_type': option_type.upper(),
                'expiry_date': expiry_date
            }
    except Exception as e:
        logger.error(f"Error extracting option details from {symbol}: {e}")
    
    return None

def apply_symbol_formatting(func):
    """
    Decorator to automatically format option symbols in function arguments.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Convert symbol arguments
        new_args = []
        for arg in args:
            if isinstance(arg, str) and ('NIFTY' in arg.upper() or 'BANKNIFTY' in arg.upper()) and ('CE' in arg.upper() or 'PE' in arg.upper()):
                new_args.append(convert_option_symbol_format(arg))
            else:
                new_args.append(arg)
        
        new_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str) and ('NIFTY' in value.upper() or 'BANKNIFTY' in value.upper()) and ('CE' in value.upper() or 'PE' in value.upper()):
                new_kwargs[key] = convert_option_symbol_format(value)
            else:
                new_kwargs[key] = value
        
        return func(*new_args, **new_kwargs)
    return wrapper

# Test the formatter
if __name__ == "__main__":
    test_symbols = [
        "NSE:NIFTY25OCT1625300CE",  # Already correct format
        "NSE:BANKNIFTY25OCT1656500PE",  # Already correct format
        "NIFTY-17-OCT-25200-CE",  # Hyphenated format
        "NSE:NIFTY-17-OCT-25200-CE",  # With NSE prefix
        "NIFTY_17_OCT_25200_CE",  # Underscore format
        "NIFTY 17 OCT 25200 CE",  # Space separated
        "BANKNIFTY-24-OCT-2024-56500-PE",  # Full year format
    ]
    
    print("Testing symbol formatting:")
    print("-" * 50)
    
    for symbol in test_symbols:
        result = convert_option_symbol_format(symbol)
        details = extract_option_details(result)
        print(f"Input:  {symbol}")
        print(f"Output: {result}")
        if details:
            print(f"Details: Strike={details['strike']}, Type={details['option_type']}, Expiry={details['expiry_date']}")
        print("-" * 50)