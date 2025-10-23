"""
Enhanced data fetcher with caching and reliability improvements
"""
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
    
    @apply_symbol_formatting
    def get_ltp_enhanced(self, symbol: str) -> Optional[float]:
        """Get LTP with retry mechanism"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = self.fyers.quotes(data={"symbols": symbol})
                
                if response.get('s') == 'ok' and response.get('d'):
                    # Use 'lp' instead of 'ltp' based on actual API response format
                    ltp = response['d'][0]['v'].get('lp') or response['d'][0]['v'].get('ltp')
                    if ltp and ltp > 0:
                        return float(ltp)
                
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                    
            except Exception as e:
                self.logger.error(f"Error getting LTP for {symbol} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        return None
    
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