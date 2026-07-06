"""
Enhanced data fetcher with caching and reliability improvements
"""
import concurrent.futures
import logging
import time
import pytz
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from .symbol_formatter import generate_option_symbol

# Add parent directory to path to import symbol_formatter
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_QUOTES_TIMEOUT = 8  # seconds — max wait for any quotes() call

def _quotes_with_timeout(fyers_client, data, timeout=_QUOTES_TIMEOUT):
    """Call fyers_client.quotes() with a hard timeout to prevent indefinite hang."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fyers_client.quotes, data)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"fyers_client.quotes() hung for >{timeout}s — no response from API")
from symbol_formatter import convert_option_symbol_format, apply_symbol_formatting

class DataFetcher:
    """Enhanced data fetcher with caching and fallback mechanisms"""
    
    def __init__(self, fyers_client):
        """Initialize data fetcher"""
        self.fyers = fyers_client
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.cache = {}
        self.cache_expiry = {}
        self.logger = logging.getLogger(__name__)
        
    def _get_cache_key(self, symbol: str, resolution: str, date_range: str) -> str:
        """Generate cache key"""
        return f"{symbol}_{resolution}_{date_range}"
    
    def _is_cache_valid(self, cache_key: str, max_age_minutes: int = 5) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache_expiry:
            return False
        
        expiry_time = self.cache_expiry[cache_key]
        return datetime.now() < expiry_time
    
    def _cache_data(self, cache_key: str, data, max_age_minutes: int = 5):
        """Cache data with expiry"""
        self.cache[cache_key] = data
        self.cache_expiry[cache_key] = datetime.now() + timedelta(minutes=max_age_minutes)
    
    def get_historical_data(self, symbol: str, resolution: str = "5", days: int = 1) -> Optional[pd.DataFrame]:
        """Get historical data with caching"""
        try:
            # Generate cache key
            end_date = datetime.now(self.ist_tz)
            start_date = end_date - timedelta(days=days)
            date_range = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            cache_key = self._get_cache_key(symbol, resolution, date_range)
            
            # Check cache first
            if self._is_cache_valid(cache_key):
                self.logger.debug(f"Using cached data for {symbol}")
                return self.cache[cache_key]
            
            # Fetch fresh data
            data_request = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "0",  # Use 0 for epoch timestamps
                "range_from": int(start_date.timestamp()),
                "range_to": int(end_date.timestamp()),
                "cont_flag": "1"
            }
            
            response = self.fyers.history(data=data_request)
            
            if response.get('s') == 'ok' and response.get('candles'):
                df = pd.DataFrame(
                    response['candles'],
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                df['timestamp'] = df['timestamp'].dt.tz_convert(self.ist_tz)
                df.set_index('timestamp', inplace=True)
                
                # Cache the data
                self._cache_data(cache_key, df)
                
                return df
            else:
                self.logger.error(f"Failed to fetch historical data for {symbol}: {response}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    def get_first_5min_candle(self, symbol: str) -> Optional[Tuple[float, float, float, float, str]]:
        """Get the first 5-minute candle (9:15-9:20) with enhanced reliability"""
        try:
            now = datetime.now(self.ist_tz)
            
            # Target the 9:15-9:20 candle
            target_date = now.replace(hour=9, minute=20, second=0, microsecond=0)
            
            # If it's before 9:20, wait or use most recent data
            if now < target_date:
                # Use the most recent available candle
                df = self.get_historical_data(symbol, resolution="5", days=1)
                if df is not None and not df.empty:
                    latest_candle = df.iloc[-1]
                    candle_time = latest_candle.name.strftime('%H:%M')
                    return (
                        latest_candle['open'],
                        latest_candle['high'], 
                        latest_candle['low'],
                        latest_candle['close'],
                        candle_time
                    )
            else:
                # Try to get the specific 9:15-9:20 candle
                df = self.get_historical_data(symbol, resolution="5", days=1)
                if df is not None and not df.empty:
                    # Filter for candles around 9:15-9:20
                    morning_candles = df[(df.index.hour == 9) & (df.index.minute == 15)]
                    
                    if not morning_candles.empty:
                        first_candle = morning_candles.iloc[0]
                        candle_time = first_candle.name.strftime('%H:%M')
                        return (
                            first_candle['open'],
                            first_candle['high'],
                            first_candle['low'], 
                            first_candle['close'],
                            candle_time
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting first 5min candle for {symbol}: {e}")
            return None
    
    def get_ltp_enhanced(self, symbol: str) -> Optional[float]:
        """Get LTP with retry mechanism"""
        max_retries = 4
        backoff = 0.5
        last_warn = None

        for attempt in range(1, max_retries + 1):
            try:
                response = _quotes_with_timeout(self.fyers, {"symbols": symbol})

                if isinstance(response, dict) and response.get('s') == 'error':
                    code = response.get('code')
                    # on rate-limit, sleep longer
                    if code == 429:
                        # Log once per symbol per run to avoid spam
                        if last_warn != 429:
                            self.logger.warning(f"Rate limited fetching LTP for {symbol}: {response}")
                            last_warn = 429
                        time.sleep(backoff * 4)
                    else:
                        self.logger.debug(f"API error fetching LTP for {symbol}: {response}")
                        time.sleep(backoff)
                    backoff *= 2
                    continue

                if response and response.get('s') == 'ok' and response.get('d'):
                    v = response['d'][0].get('v', {})
                    ltp = None
                    if isinstance(v, dict):
                        ltp = v.get('lp') or v.get('ltp') or v.get('lt')
                    if ltp is not None:
                        try:
                            ltp_val = float(ltp)
                            if ltp_val > 0:
                                return ltp_val
                        except Exception:
                            pass

                # unexpected result -> retry
                self.logger.debug(f"Unexpected LTP response for {symbol} (attempt {attempt}/{max_retries}): {response}")
                time.sleep(backoff)
                backoff *= 2

            except Exception as e:
                # Avoid spamming error logs for transient network issues
                self.logger.error(f"Error getting LTP for {symbol} (attempt {attempt}/{max_retries}): {e}")
                time.sleep(backoff)
                backoff *= 2

        return None
    
    def get_ltp_batch(self, symbols: list) -> dict:
        """Fetch LTP for multiple symbols in a SINGLE API call.
        Returns dict: {symbol: float_ltp}.  Missing/failed symbols are absent.
        """
        if not self.fyers or not symbols:
            return {}
        symbols_str = ",".join(symbols)
        max_retries = 4
        backoff = 0.5
        for attempt in range(1, max_retries + 1):
            try:
                response = _quotes_with_timeout(self.fyers, {"symbols": symbols_str})
                if isinstance(response, dict) and response.get('s') == 'error':
                    code = response.get('code')
                    if code == 429:
                        self.logger.warning(f"Rate limited on batch LTP attempt {attempt}/{max_retries}: {response}")
                        time.sleep(backoff * 4)
                    else:
                        time.sleep(backoff)
                    backoff *= 2
                    continue
                if response and response.get('s') == 'ok' and response.get('d'):
                    result = {}
                    for item in response['d']:
                        sym = item.get('n')
                        v = item.get('v', {})
                        if isinstance(v, dict) and sym:
                            raw = v.get('lp') or v.get('ltp') or v.get('lt')
                            try:
                                result[sym] = float(raw)
                            except (TypeError, ValueError):
                                pass
                    return result
                time.sleep(backoff)
                backoff *= 2
            except Exception as e:
                self.logger.error(f"Error in batch LTP attempt {attempt}/{max_retries}: {e}")
                time.sleep(backoff)
                backoff *= 2
        return {}

    def get_option_symbols(self, index_name: str, spot_price: float) -> Optional[Dict]:
        """Generate option symbols for ATM, ITM, OTM strikes with proper formatting"""
        try:
            # Determine step size based on index
            if 'BANK' in index_name.upper():
                step_size = 100
                base_name = 'BANKNIFTY'
            else:
                step_size = 50
                base_name = 'NIFTY'
            
            # Calculate ATM strike
            atm_strike = round(spot_price / step_size) * step_size
            
            # Calculate expiry based on index type
            now = datetime.now(self.ist_tz)
            
            if 'BANK' in index_name.upper():
                # BANKNIFTY: Weekly options expire on Wednesday
                target_weekday = 2  # Wednesday (0=Monday, 2=Wednesday)
                days_to_expiry = (target_weekday - now.weekday()) % 7
                if days_to_expiry == 0:  # Today is Wednesday
                    if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
                        days_to_expiry = 7  # Next Wednesday after market close
                # For Oct 10, 2025 (Friday), next Wednesday is Oct 15
                expiry_date = now + timedelta(days=days_to_expiry)
            else:
                # NIFTY: Weekly options expire on Thursday
                target_weekday = 3  # Thursday
                days_to_expiry = (target_weekday - now.weekday()) % 7
                if days_to_expiry == 0:  # Today is Thursday
                    if days_to_expiry == 0:
                        if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
                            days_to_expiry = 7  # Next Thursday after market close
                
                # For Oct 10, 2025, use Oct 14 expiry (which works based on logs)
                if now.date() <= datetime(2025, 10, 14).date():
                    expiry_date = datetime(2025, 10, 14, tzinfo=self.ist_tz)
                else:
                    expiry_date = now + timedelta(days=days_to_expiry)
            
            # Generate symbols using proper formatter
            symbols = {
                'ATM': {
                    'CE': generate_option_symbol(base_name, expiry_date.date(), int(atm_strike), 'CE'),
                    'PE': generate_option_symbol(base_name, expiry_date.date(), int(atm_strike), 'PE')
                },
                'ITM': {
                    'CE': generate_option_symbol(base_name, expiry_date.date(), int(atm_strike - step_size), 'CE'),
                    'PE': generate_option_symbol(base_name, expiry_date.date(), int(atm_strike + step_size), 'PE')
                },
                'OTM': {
                    'CE': generate_option_symbol(base_name, expiry_date.date(), int(atm_strike + step_size), 'CE'), 
                    'PE': generate_option_symbol(base_name, expiry_date.date(), int(atm_strike - step_size), 'PE')
                }
            }
            
            self.logger.info(f"Generated option symbols for {base_name} @ {spot_price}:")
            self.logger.info(f"  ATM Strike: {atm_strike}")
            self.logger.info(f"  Expiry: {expiry_date.date()}")
            self.logger.info(f"  ATM CE: {symbols['ATM']['CE']}")
            self.logger.info(f"  ATM PE: {symbols['ATM']['PE']}")
            
            return symbols
            
        except Exception as e:
            self.logger.error(f"Error generating option symbols: {e}")
            return None
    
    def prefetch_data(self, symbols: List[str], resolutions: List[str] = ["5", "1"]):
        """Pre-fetch and cache data for faster access"""
        try:
            self.logger.info(f"Pre-fetching data for {len(symbols)} symbols...")
            
            for symbol in symbols:
                for resolution in resolutions:
                    try:
                        df = self.get_historical_data(symbol, resolution, days=2)
                        if df is not None:
                            self.logger.debug(f"Pre-fetched {resolution}min data for {symbol}")
                        else:
                            self.logger.warning(f"Failed to pre-fetch {resolution}min data for {symbol}")
                    except Exception as e:
                        self.logger.error(f"Error pre-fetching {resolution}min data for {symbol}: {e}")
            
            self.logger.info("Data pre-fetching complete")
            
        except Exception as e:
            self.logger.error(f"Error in data pre-fetching: {e}")
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.cache_expiry.clear()
        self.logger.info("Cache cleared")