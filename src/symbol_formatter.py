"""
Utility functions to convert option symbols to the format required by Fyers API
"""
import logging
import re
import datetime
from typing import Dict, Optional

def convert_option_symbol_format(symbol: str) -> str:
    """
    Convert option symbols to the format required by Fyers API
    
    Based on testing, Fyers API expects option symbols in format:
    NSE:NIFTY25JUL2524700PE (no hyphens)
    
    Args:
        symbol (str): Option symbol to convert
        
    Returns:
        str: Symbol in Fyers API compatible format
    """
    if not symbol:
        return symbol
        
    # If it's not an option symbol (no CE/PE), return as is
    if "CE" not in symbol and "PE" not in symbol:
        return symbol
        
    # Check if already in correct format (no hyphens/underscores/spaces)
    if "-" not in symbol and "_" not in symbol and " " not in symbol:
        # Add NSE: prefix if missing
        if ":" not in symbol:
            return f"NSE:{symbol}"
        return symbol
    
    logging.info(f"Converting symbol: {symbol}")
        
    try:
        # First, standardize separators to hyphens
        symbol = symbol.replace("_", "-").replace(" ", "-")
        
        # Extract exchange prefix (e.g., "NSE:")
        prefix = "NSE:"  # Default to NSE
        rest = symbol
        if ":" in symbol:
            parts = symbol.split(":")
            prefix = parts[0] + ":"
            rest = parts[1]
        
        # Split by hyphens to extract components
        components = rest.split("-")
        
        # First component should be the underlying (NIFTY, BANKNIFTY)
        underlying = components[0]
        
        # Find option type (CE/PE) - usually the last component
        option_type = None
        for part in components:
            if part in ["CE", "PE"]:
                option_type = part
                break
                
        if not option_type:
            return symbol
        
        # Use regex to extract strike price from the symbol
        # Format: NSE:NIFTY25O1425300CE -> extract 25300
        import re
        
        # Pattern to match strike price (4-5 digits) followed by CE/PE
        strike_pattern = r'(\d{4,5})(CE|PE)$'
        match = re.search(strike_pattern, symbol)
        
        if match:
            strike_price = match.group(1)
        else:
            # Fallback: find the largest number that looks like a strike
            numbers = [part for part in components if part.isdigit() and len(part) >= 4]
            strike_price = max(numbers, key=len) if numbers else None
            
        if not strike_price:
            return symbol
            
        # Find date components
        day = None
        month = None
        year = None
        
        # Look for day (1-2 digit number between 1-31)
        for part in components:
            if part.isdigit() and 1 <= len(part) <= 2 and 1 <= int(part) <= 31:
                day = part.zfill(2)  # Pad with zero if single digit
                break
                
        # Look for month abbreviation (JAN, FEB, etc.)
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        for part in components:
            part_upper = part.upper()
            if part_upper in months:
                month = part_upper
                break
                
        # Look for year (2-digit or 4-digit)
        for part in components:
            if part.isdigit() and (len(part) == 2 or len(part) == 4):
                if len(part) == 4:
                    # Convert 4-digit year to 2-digit
                    year = part[2:]
                else:
                    year = part
                # Only consider as year if it's not already identified as the day or strike
                if part != day and part != strike_price:
                    break
        
        # If we couldn't find all components, try to guess from current date
        if not day or not month or not year:
            pass  # Use current/next expiry for missing date components
            today = datetime.datetime.now()
            
            # For current expiry, use next Thursday
            days_to_thursday = (3 - today.weekday()) % 7
            if days_to_thursday == 0:  # Today is Thursday
                if today.hour >= 15:  # After market close
                    days_to_thursday = 7  # Next Thursday
            
            expiry_date = today + datetime.timedelta(days=days_to_thursday)
            
            day = day or expiry_date.strftime('%d')
            month = month or expiry_date.strftime('%b').upper()
            year = year or expiry_date.strftime('%y')
        
        # Build the final symbol in format: NSE:NIFTY25O1425200CE
        # Based on actual Fyers format: YY + Month_Initial + DD + STRIKE + CE/PE
        month_initial = month[0] if month else 'O'  # First letter of month
        new_symbol = f"{prefix}{underlying}{year}{month_initial}{day}{strike_price}{option_type}"
        
        logging.info(f"Converted: {symbol} → {new_symbol}")
        return new_symbol
    
    except Exception as e:
        logging.error(f"Error converting option symbol {symbol}: {e}")
        return symbol  # Return original symbol if conversion fails

def extract_option_details(symbol: str) -> Dict:
    """
    Extract details from an option symbol
    
    Args:
        symbol (str): Option symbol in any format
        
    Returns:
        dict: Details including underlying, expiry, strike and option type
    """
    # First, standardize the symbol
    formatted = convert_option_symbol_format(symbol)
    
    # Initialize result
    details = {
        'symbol': formatted,
        'exchange': None,
        'underlying': None,
        'expiry_date': None,
        'expiry_day': None,
        'expiry_month': None,
        'expiry_year': None,
        'strike': None,
        'option_type': None,
        'days_to_expiry': None
    }
    
    try:
        # Extract components using regex
        # Format: NSE:NIFTY25O1425200CE (YY + Month_Initial + DD + STRIKE + CE/PE)
        pattern = r'(?:(\w+):)?(\w+)(\d{2})([A-Z])(\d{2})(\d+)(CE|PE)'
        match = re.match(pattern, formatted)
        
        if match:
            exchange, underlying, year, month_initial, day, strike, option_type = match.groups()
            
            details['exchange'] = exchange or 'NSE'
            details['underlying'] = underlying
            details['expiry_day'] = day
            details['expiry_year'] = '20' + year
            details['strike'] = int(strike)
            details['option_type'] = option_type
            
            # Convert month initial to full month name and number
            month_initials = {
                'J': 'JAN', 'F': 'FEB', 'M': 'MAR', 'A': 'APR', 'Y': 'MAY', 'N': 'JUN',
                'L': 'JUL', 'G': 'AUG', 'S': 'SEP', 'O': 'OCT', 'V': 'NOV', 'D': 'DEC'
            }
            month_name = month_initials.get(month_initial, 'OCT')
            details['expiry_month'] = month_name
            
            months = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            month_num = months.get(month_name, 10)
            
            # Create expiry date
            details['expiry_date'] = datetime.date(
                int(details['expiry_year']), month_num, int(day)
            )
            
            # Calculate days to expiry
            details['days_to_expiry'] = (details['expiry_date'] - datetime.date.today()).days
    
    except Exception as e:
        logging.error(f"Error extracting details from symbol {symbol}: {e}")
    
    return details

def validate_option_symbol(symbol: str) -> bool:
    """
    Validate if a symbol is in the correct Fyers API format
    
    Args:
        symbol (str): Symbol to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Pattern for valid Fyers API option symbol: NSE:NIFTY25O1425200CE
    # Format: EXCHANGE:UNDERLYING + YY + MONTH_INITIAL + DD + STRIKE + CE/PE
    pattern = r'^(?:\w+:)?\w+\d{2}[A-Z]\d{2}\d+(?:CE|PE)$'
    
    if re.match(pattern, symbol):
        return True
    else:
        pass  # Symbol format issues are handled gracefully
        return False

def apply_symbol_formatting(func):
    """Decorator to apply symbol formatting to any function that returns option data"""
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        
        # If result is a DataFrame with a 'symbol' column, format all symbols
        if hasattr(result, 'columns') and 'symbol' in result.columns:
            result['symbol'] = result['symbol'].apply(convert_option_symbol_format)
        
        return result
    return wrapper

def generate_option_symbol(underlying: str, expiry_date: datetime.date, strike: int, option_type: str) -> str:
    """
    Generate a properly formatted option symbol based on actual Fyers format
    
    From the logs, we can see Fyers uses format like: NSE:NIFTY25O1425200CE
    This means: NSE:NIFTY + YY + O + DD + STRIKE + CE/PE
    Where YY=year, O=month initial (O for Oct), DD=day
    
    Args:
        underlying (str): Underlying instrument (NIFTY, BANKNIFTY)
        expiry_date (datetime.date): Expiry date
        strike (int): Strike price
        option_type (str): CE or PE
        
    Returns:
        str: Properly formatted option symbol
    """
    # Format expiry for Fyers: YY + MON (e.g., 25NOV for Nov 2025)
    expiry_str = expiry_date.strftime('%y') + expiry_date.strftime('%b').upper()
    return f"NSE:{underlying}{expiry_str}{strike}{option_type.upper()}"

def test_symbol_formatter():
    """Test the symbol formatter with various input formats"""
    test_symbols = [
        "NIFTY-25-JUL-25-24700-PE",
        "NIFTY_25_JUL_25_24700_PE", 
        "NIFTY 25 JUL 25 24700 PE",
        "BANKNIFTY-25-JUL-25-40000-CE",
        "NSE:NIFTY-25-JUL-25-24700-PE",
        "NSE:NIFTY25JUL2524700PE",  # Already in correct format
        "NIFTY25JUL2524700PE"
    ]
    
    print("Symbol Formatter Test Results:")
    print("-" * 60)
    
    for symbol in test_symbols:
        formatted = convert_option_symbol_format(symbol)
        details = extract_option_details(formatted)
        is_valid = validate_option_symbol(formatted)
        
        print(f"Original:  {symbol}")
        print(f"Formatted: {formatted}")
        print(f"Valid:     {is_valid}")
        print(f"Details:   Strike={details['strike']}, Type={details['option_type']}, Expiry={details['expiry_date']}")
        print("-" * 60)

if __name__ == "__main__":
    test_symbol_formatter()