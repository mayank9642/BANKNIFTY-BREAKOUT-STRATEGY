"""
Enhanced 5-Minute Breakout Strategy for Bank Nifty Options
A sophisticated algorithmic trading system with advanced risk management
"""

import pandas as pd
import numpy as np
import logging
import pytz
import yaml
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from fyers_apiv3 import fyersModel
import websocket
import queue
import traceback

# Configure logging with IST timezone
class ISTFormatter(logging.Formatter):
    def converter(self, timestamp):
        dt = datetime.fromtimestamp(timestamp)
        ist = pytz.timezone('Asia/Kolkata')
        return dt.replace(tzinfo=pytz.utc).astimezone(ist)
    
    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.strftime("%Y-%m-%d %H:%M:%S")
        return s

@dataclass
class TradeRecord:
    """Data class to store trade information"""
    symbol: str
    entry_time: datetime
    entry_price: float
    quantity: int
    direction: str  # 'LONG' or 'SHORT'
    stop_loss: float
    target: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    pnl: float = 0.0
    partial_exits: List[Dict] = field(default_factory=list)

@dataclass
class BreakoutLevel:
    """Data class to store breakout levels"""
    symbol: str
    ce_symbol: str
    pe_symbol: str
    ce_breakout_level: float
    pe_breakout_level: float
    ce_closing_price: float
    pe_closing_price: float
    spot_price: float
    calculated_time: datetime

class Enhanced5MinBreakoutStrategy:
    """
    Enhanced 5-Minute Breakout Strategy Implementation
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the strategy with configuration"""
        self.config = self._load_config(config_path)
        self.setup_logging()
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # Trading state
        self.active_trades: Dict[str, TradeRecord] = {}
        self.breakout_levels: Dict[str, BreakoutLevel] = {}
        self.first_candle_captured = False
        self.trading_active = False
        self.daily_pnl = 0.0
        self.daily_trades_count = 0
        
        # Data caches
        self.price_cache: Dict[str, Dict] = {}
        self.volume_cache: Dict[str, List] = {}
        self.momentum_cache: Dict[str, List] = {}
        
        # WebSocket related
        self.ws = None
        self.ws_thread = None
        self.price_queue = queue.Queue()
        
        # Fyers API client
        self.fyers = None
        self.initialize_api()
        
        logging.info("Enhanced 5-Minute Breakout Strategy initialized")

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            return config
        except Exception as e:
            raise Exception(f"Failed to load config: {e}")

    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config['logging']['level'].upper())
        
        # Create formatter
        formatter = ISTFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S IST'
        )
        
        # Setup file handler
        if self.config['logging']['log_trades']:
            file_handler = logging.FileHandler(self.config['logging']['log_file'])
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)
        
        # Setup console handler
        if self.config['logging']['console_output']:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logging.getLogger().addHandler(console_handler)
        
        logging.getLogger().setLevel(log_level)

    def initialize_api(self):
        """Initialize Fyers API connection with automatic token management"""
        try:
            # Import token manager
            from token_manager import ensure_valid_token
            
            # Ensure we have a valid token
            access_token = ensure_valid_token()
            if not access_token:
                logging.error("Failed to get valid access token. Please run authenticate.py")
                return False
            
            client_id = self.config['fyers']['client_id']
                
            self.fyers = fyersModel.FyersModel(
                client_id=client_id,
                token=access_token,
                log_path=""
            )
            
            # Test connection
            profile = self.fyers.get_profile()
            if profile['s'] == 'ok':
                logging.info(f"API initialized successfully. User: {profile['data']['name']}")
                return True
            else:
                logging.error(f"API initialization failed: {profile}")
                # Try to refresh token once more
                logging.info("Attempting to refresh token...")
                new_token = ensure_valid_token(use_totp=False)
                if new_token:
                    self.fyers = fyersModel.FyersModel(
                        client_id=client_id,
                        token=new_token,
                        log_path=""
                    )
                    profile = self.fyers.get_profile()
                    if profile['s'] == 'ok':
                        logging.info(f"API initialized successfully after token refresh. User: {profile['data']['name']}")
                        return True
                
                return False
                
        except Exception as e:
            logging.error(f"Failed to initialize API: {e}")
            return False

    def get_current_ist_time(self) -> datetime:
        """Get current time in IST"""
        return datetime.now(self.ist_tz)

    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = self.get_current_ist_time()
        current_time = now.time()
        current_date = now.date()
        
        # Check if it's a weekend
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Check if it's a market holiday
        if current_date.strftime('%Y-%m-%d') in self.config.get('market_holidays', []):
            return False
        
        # Check trading hours (9:15 AM to 3:30 PM IST)
        market_open = datetime.strptime(self.config['timing']['market_open_time'], '%H:%M').time()
        market_close = datetime.strptime(self.config['timing']['trading_end_time'], '%H:%M').time()
        
        return market_open <= current_time <= market_close

    def wait_for_market_open(self):
        """Wait for market to open if configured"""
        if not self.config['timing']['wait_for_market_open']:
            return
        
        while not self.is_market_open():
            now = self.get_current_ist_time()
            logging.info(f"Market is closed. Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
            time.sleep(60)  # Check every minute
        
        logging.info("Market is now open. Starting strategy...")

    def get_expiry_date(self) -> str:
        """Get the current week's Thursday expiry date"""
        now = self.get_current_ist_time()
        
        # Find next Thursday
        days_ahead = 3 - now.weekday()  # Thursday = 3
        if days_ahead < 0:  # Thursday already passed this week
            days_ahead += 7
        elif days_ahead == 0:  # Today is Thursday
            # Check if it's after 3:30 PM, then next Thursday
            if now.time() > datetime.strptime('15:30', '%H:%M').time():
                days_ahead = 7
        
        expiry_date = now + timedelta(days=days_ahead)
        return expiry_date.strftime('%y%m%d')

    def get_atm_strike(self, spot_price: float, step_size: int) -> int:
        """Get ATM strike price based on spot price and step size"""
        return round(spot_price / step_size) * step_size

    def generate_option_symbol(self, index: str, strike: int, option_type: str, expiry: str) -> str:
        """Generate option symbol for Fyers API"""
        # Format: NSE:NIFTY2410317000CE
        return f"NSE:{index.upper()}{expiry}{strike}{option_type.upper()}"

    def get_historical_data(self, symbol: str, days: int = 1) -> pd.DataFrame:
        """Fetch historical data with fallback mechanisms"""
        max_retries = self.config['data']['max_retries']
        retry_delay = self.config['data']['retry_delay']
        
        for attempt in range(max_retries):
            try:
                # Calculate date range
                end_date = self.get_current_ist_time()
                start_date = end_date - timedelta(days=days)
                
                data = {
                    "symbol": symbol,
                    "resolution": self.config['data']['timeframe'],
                    "date_format": "1",
                    "range_from": start_date.strftime('%Y-%m-%d'),
                    "range_to": end_date.strftime('%Y-%m-%d'),
                    "cont_flag": "1"
                }
                
                response = self.fyers.history(data=data)
                
                if response['s'] == 'ok' and 'candles' in response:
                    df = pd.DataFrame(response['candles'], 
                                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df.set_index('timestamp', inplace=True)
                    return df
                else:
                    logging.warning(f"Historical data fetch failed for {symbol}: {response}")
                    
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed for {symbol}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    
        logging.error(f"Failed to fetch historical data for {symbol} after {max_retries} attempts")
        return pd.DataFrame()

    def calculate_atr(self, df: pd.DataFrame, periods: int = 14) -> float:
        """Calculate Average True Range"""
        if len(df) < periods:
            return 0.0
            
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=periods).mean().iloc[-1]
        
        return atr if not np.isnan(atr) else 0.0

    def capture_first_candle(self):
        """Capture and analyze the first 5-minute candle"""
        try:
            logging.info("Capturing first 5-minute candle...")
            
            for index_name, index_config in self.config['trading']['symbols'].items():
                if not index_config['enabled']:
                    continue
                    
                symbol = index_config['index_symbol']
                step_size = index_config['step_size']
                
                # Get historical data
                df = self.get_historical_data(symbol, days=1)
                if df.empty:
                    logging.error(f"No data received for {symbol}")
                    continue
                
                # Get the latest candle (should be the first 5-minute candle)
                latest_candle = df.iloc[-1]
                spot_price = latest_candle['close']
                
                logging.info(f"{index_name.upper()} - First candle: O:{latest_candle['open']:.2f}, "
                           f"H:{latest_candle['high']:.2f}, L:{latest_candle['low']:.2f}, "
                           f"C:{latest_candle['close']:.2f}, V:{latest_candle['volume']}")
                
                # Calculate ATM strikes
                atm_strike = self.get_atm_strike(spot_price, step_size)
                expiry = self.get_expiry_date()
                
                # Generate option symbols
                ce_symbol = self.generate_option_symbol(index_name, atm_strike, 'CE', expiry)
                pe_symbol = self.generate_option_symbol(index_name, atm_strike, 'PE', expiry)
                
                # Get option prices
                ce_price = self.get_option_price(ce_symbol)
                pe_price = self.get_option_price(pe_symbol)
                
                if ce_price is None or pe_price is None:
                    logging.error(f"Failed to get option prices for {index_name}")
                    continue
                
                # Calculate breakout levels
                buffer = self.config['trading']['risk_management']['breakout_buffer']
                ce_breakout = ce_price + buffer
                pe_breakout = pe_price + buffer
                
                # Store breakout levels
                self.breakout_levels[index_name] = BreakoutLevel(
                    symbol=symbol,
                    ce_symbol=ce_symbol,
                    pe_symbol=pe_symbol,
                    ce_breakout_level=ce_breakout,
                    pe_breakout_level=pe_breakout,
                    ce_closing_price=ce_price,
                    pe_closing_price=pe_price,
                    spot_price=spot_price,
                    calculated_time=self.get_current_ist_time()
                )
                
                logging.info(f"{index_name.upper()} Breakout Levels - "
                           f"CE: {ce_breakout:.2f} (Strike: {atm_strike}), "
                           f"PE: {pe_breakout:.2f} (Strike: {atm_strike})")
            
            self.first_candle_captured = True
            logging.info("First candle analysis completed successfully")
            
        except Exception as e:
            logging.error(f"Error capturing first candle: {e}")
            logging.error(traceback.format_exc())

    def get_option_price(self, symbol: str) -> Optional[float]:
        """Get current option price"""
        try:
            response = self.fyers.quotes(data={"symbols": symbol})
            if response['s'] == 'ok' and 'd' in response:
                return response['d'][0]['v']['lp']  # Last price
        except Exception as e:
            logging.error(f"Error getting option price for {symbol}: {e}")
        return None

    def check_volume_confirmation(self, symbol: str) -> bool:
        """Check if current volume exceeds threshold"""
        if not self.config['trading']['entry_filters']['volume_confirmation']:
            return True
            
        try:
            df = self.get_historical_data(symbol, days=2)
            if len(df) < self.config['trading']['entry_filters']['volume_periods']:
                return True  # Skip check if insufficient data
                
            recent_volumes = df['volume'].tail(self.config['trading']['entry_filters']['volume_periods'])
            avg_volume = recent_volumes.mean()
            current_volume = df['volume'].iloc[-1]
            
            threshold = self.config['trading']['entry_filters']['volume_threshold']
            return current_volume >= (avg_volume * threshold)
            
        except Exception as e:
            logging.error(f"Error checking volume confirmation: {e}")
            return True  # Default to True on error

    def check_momentum_confirmation(self, symbol: str) -> bool:
        """Check momentum confirmation"""
        if not self.config['trading']['entry_filters']['momentum_confirmation']:
            return True
            
        try:
            df = self.get_historical_data(symbol, days=1)
            periods = self.config['trading']['entry_filters']['momentum_periods']
            
            if len(df) < periods:
                return True
                
            recent_closes = df['close'].tail(periods)
            # Simple momentum check: more recent closes should be higher
            return recent_closes.iloc[-1] > recent_closes.iloc[0]
            
        except Exception as e:
            logging.error(f"Error checking momentum confirmation: {e}")
            return True

    def calculate_stop_loss(self, entry_price: float, symbol: str, direction: str) -> float:
        """Calculate stop loss using ATR or fixed points"""
        risk_config = self.config['trading']['risk_management']
        
        if risk_config['use_atr_stop_loss']:
            # Get index symbol for ATR calculation
            index_symbol = None
            for idx_name, idx_config in self.config['trading']['symbols'].items():
                if idx_name in symbol.lower():
                    index_symbol = idx_config['index_symbol']
                    break
            
            if index_symbol:
                df = self.get_historical_data(index_symbol, days=5)
                if not df.empty:
                    atr = self.calculate_atr(df, risk_config['atr_periods'])
                    atr_stop = atr * risk_config['atr_multiplier']
                    
                    if direction == 'LONG':
                        return entry_price - atr_stop
                    else:
                        return entry_price + atr_stop
        
        # Fallback to fixed points
        stop_points = risk_config['stop_loss_points']
        if direction == 'LONG':
            return entry_price - stop_points
        else:
            return entry_price + stop_points

    def execute_trade(self, symbol: str, direction: str, quantity: int, 
                     entry_price: float) -> bool:
        """Execute trade through Fyers API"""
        try:
            if self.config['simulation']['enabled']:
                logging.info(f"SIMULATION: Would execute {direction} trade for {symbol}")
                return True
                
            # Prepare order data
            order_data = {
                "symbol": symbol,
                "qty": quantity,
                "type": 2,  # Market order
                "side": 1 if direction == 'LONG' else -1,
                "productType": "INTRADAY",
                "limitPrice": 0,
                "stopPrice": 0,
                "validity": "DAY",
                "disclosedQty": 0,
                "offlineOrder": "False"
            }
            
            response = self.fyers.place_order(data=order_data)
            
            if response['s'] == 'ok':
                logging.info(f"Order placed successfully: {response['id']}")
                return True
            else:
                logging.error(f"Order placement failed: {response}")
                return False
                
        except Exception as e:
            logging.error(f"Error executing trade: {e}")
            return False

    def monitor_breakouts(self):
        """Monitor for breakout conditions and execute trades"""
        logging.info("Starting breakout monitoring...")
        
        while self.trading_active and not self.first_candle_captured:
            time.sleep(5)
        
        while self.trading_active:
            try:
                for index_name, breakout_level in self.breakout_levels.items():
                    if index_name in self.active_trades:
                        continue  # Already have position in this index
                    
                    # Check CE breakout
                    ce_price = self.get_option_price(breakout_level.ce_symbol)
                    if ce_price and ce_price >= breakout_level.ce_breakout_level:
                        if self.validate_entry_conditions(breakout_level.symbol):
                            self.enter_trade(breakout_level.ce_symbol, 'LONG', 
                                           ce_price, index_name)
                    
                    # Check PE breakout  
                    pe_price = self.get_option_price(breakout_level.pe_symbol)
                    if pe_price and pe_price >= breakout_level.pe_breakout_level:
                        if self.validate_entry_conditions(breakout_level.symbol):
                            self.enter_trade(breakout_level.pe_symbol, 'LONG', 
                                           pe_price, index_name)
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logging.error(f"Error in breakout monitoring: {e}")
                time.sleep(5)

    def validate_entry_conditions(self, symbol: str) -> bool:
        """Validate all entry conditions"""
        # Check daily limits
        if self.daily_trades_count >= self.config['monitoring']['max_daily_trades']:
            logging.info("Daily trade limit reached")
            return False
        
        if self.daily_pnl <= self.config['monitoring']['max_daily_loss']:
            logging.info("Daily loss limit reached")
            return False
        
        # Check confirmations
        volume_ok = self.check_volume_confirmation(symbol)
        momentum_ok = self.check_momentum_confirmation(symbol)
        
        logging.debug(f"Entry validation - Volume: {volume_ok}, Momentum: {momentum_ok}")
        return volume_ok and momentum_ok

    def enter_trade(self, symbol: str, direction: str, entry_price: float, index_name: str):
        """Enter a new trade"""
        try:
            quantity = self.config['trading']['symbols'][index_name]['quantity']
            
            # Calculate stop loss and target
            stop_loss = self.calculate_stop_loss(entry_price, symbol, direction)
            target_points = self.config['trading']['risk_management']['target_points']
            
            if direction == 'LONG':
                target = entry_price + target_points
            else:
                target = entry_price - target_points
            
            # Execute trade
            if self.execute_trade(symbol, direction, quantity, entry_price):
                # Create trade record
                trade_record = TradeRecord(
                    symbol=symbol,
                    entry_time=self.get_current_ist_time(),
                    entry_price=entry_price,
                    quantity=quantity,
                    direction=direction,
                    stop_loss=stop_loss,
                    target=target
                )
                
                self.active_trades[index_name] = trade_record
                self.daily_trades_count += 1
                
                logging.info(f"TRADE ENTERED - {symbol} {direction} @ {entry_price:.2f}, "
                           f"SL: {stop_loss:.2f}, Target: {target:.2f}")
                
                # Start monitoring this trade
                thread = threading.Thread(target=self.monitor_trade, args=(index_name,))
                thread.daemon = True
                thread.start()
                
        except Exception as e:
            logging.error(f"Error entering trade: {e}")

    def monitor_trade(self, index_name: str):
        """Monitor an active trade"""
        trade = self.active_trades.get(index_name)
        if not trade:
            return
        
        logging.info(f"Starting trade monitoring for {trade.symbol}")
        
        while index_name in self.active_trades:
            try:
                current_price = self.get_option_price(trade.symbol)
                if current_price is None:
                    time.sleep(1)
                    continue
                
                # Check exit conditions
                exit_reason = self.check_exit_conditions(trade, current_price)
                
                if exit_reason:
                    self.exit_trade(index_name, current_price, exit_reason)
                    break
                
                # Check partial exits
                self.check_partial_exits(trade, current_price)
                
                # Check trailing stop
                self.update_trailing_stop(trade, current_price)
                
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Error monitoring trade {trade.symbol}: {e}")
                time.sleep(5)

    def check_exit_conditions(self, trade: TradeRecord, current_price: float) -> str:
        """Check if trade should be exited"""
        # Stop loss hit
        if trade.direction == 'LONG' and current_price <= trade.stop_loss:
            return "STOP_LOSS"
        elif trade.direction == 'SHORT' and current_price >= trade.stop_loss:
            return "STOP_LOSS"
        
        # Target hit
        if trade.direction == 'LONG' and current_price >= trade.target:
            return "TARGET"
        elif trade.direction == 'SHORT' and current_price <= trade.target:
            return "TARGET"
        
        # Time-based exit
        max_holding = self.config['trading']['risk_management']['max_holding_period_minutes']
        time_elapsed = (self.get_current_ist_time() - trade.entry_time).total_seconds() / 60
        
        if time_elapsed >= max_holding:
            return "TIME_EXIT"
        
        return ""

    def check_partial_exits(self, trade: TradeRecord, current_price: float):
        """Check and execute partial exits"""
        if not self.config['trading']['partial_exits']['enabled']:
            return
        
        current_time = self.get_current_ist_time()
        time_elapsed = (current_time - trade.entry_time).total_seconds() / 60
        
        for exit_config in self.config['trading']['partial_exits']['exits']:
            # Check if this partial exit already executed
            if any(pe['time_minutes'] == exit_config['time_minutes'] for pe in trade.partial_exits):
                continue
            
            if time_elapsed >= exit_config['time_minutes']:
                # Calculate current profit percentage
                if trade.direction == 'LONG':
                    profit_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100
                else:
                    profit_pct = ((trade.entry_price - current_price) / trade.entry_price) * 100
                
                if profit_pct >= exit_config['min_profit_percentage']:
                    exit_qty = int(trade.quantity * exit_config['exit_percentage'] / 100)
                    
                    if self.execute_partial_exit(trade, exit_qty, current_price):
                        partial_exit = {
                            'time_minutes': exit_config['time_minutes'],
                            'exit_price': current_price,
                            'quantity': exit_qty,
                            'profit_pct': profit_pct
                        }
                        trade.partial_exits.append(partial_exit)
                        trade.quantity -= exit_qty
                        
                        logging.info(f"PARTIAL EXIT - {trade.symbol} {exit_qty} qty @ {current_price:.2f}, "
                                   f"Profit: {profit_pct:.1f}%")

    def execute_partial_exit(self, trade: TradeRecord, quantity: int, price: float) -> bool:
        """Execute partial exit"""
        try:
            if self.config['simulation']['enabled']:
                return True
            
            # Execute exit order through API
            order_data = {
                "symbol": trade.symbol,
                "qty": quantity,
                "type": 2,  # Market order
                "side": -1 if trade.direction == 'LONG' else 1,  # Opposite side
                "productType": "INTRADAY",
                "limitPrice": 0,
                "stopPrice": 0,
                "validity": "DAY",
                "disclosedQty": 0,
                "offlineOrder": "False"
            }
            
            response = self.fyers.place_order(data=order_data)
            return response['s'] == 'ok'
            
        except Exception as e:
            logging.error(f"Error executing partial exit: {e}")
            return False

    def update_trailing_stop(self, trade: TradeRecord, current_price: float):
        """Update trailing stop loss"""
        trailing_config = self.config['trading']['trailing_stop']
        if not trailing_config['enabled']:
            return
        
        # Calculate current profit
        if trade.direction == 'LONG':
            profit = current_price - trade.entry_price
            profit_pct = (profit / trade.entry_price) * 100
        else:
            profit = trade.entry_price - current_price
            profit_pct = (profit / trade.entry_price) * 100
        
        # Check if trailing should be activated
        target_profit = trade.target - trade.entry_price if trade.direction == 'LONG' else trade.entry_price - trade.target
        activation_profit = target_profit * (trailing_config['activation_percentage'] / 100)
        
        if profit >= activation_profit:
            # Calculate new trailing stop
            trailing_amount = profit * (trailing_config['trailing_percentage'] / 100)
            
            if trade.direction == 'LONG':
                new_stop = current_price - trailing_amount
                if new_stop > trade.stop_loss:
                    trade.stop_loss = new_stop
                    logging.debug(f"Trailing stop updated to {new_stop:.2f}")
            else:
                new_stop = current_price + trailing_amount
                if new_stop < trade.stop_loss:
                    trade.stop_loss = new_stop
                    logging.debug(f"Trailing stop updated to {new_stop:.2f}")

    def exit_trade(self, index_name: str, exit_price: float, exit_reason: str):
        """Exit a trade completely"""
        trade = self.active_trades.get(index_name)
        if not trade:
            return
        
        try:
            # Execute exit order
            if self.execute_trade(trade.symbol, 
                                'SHORT' if trade.direction == 'LONG' else 'LONG',
                                trade.quantity, exit_price):
                
                # Calculate P&L
                if trade.direction == 'LONG':
                    pnl = (exit_price - trade.entry_price) * trade.quantity
                else:
                    pnl = (trade.entry_price - exit_price) * trade.quantity
                
                # Add partial exit P&L
                for partial_exit in trade.partial_exits:
                    if trade.direction == 'LONG':
                        partial_pnl = (partial_exit['exit_price'] - trade.entry_price) * partial_exit['quantity']
                    else:
                        partial_pnl = (trade.entry_price - partial_exit['exit_price']) * partial_exit['quantity']
                    pnl += partial_pnl
                
                # Update trade record
                trade.exit_time = self.get_current_ist_time()
                trade.exit_price = exit_price
                trade.exit_reason = exit_reason
                trade.pnl = pnl
                
                # Update daily P&L
                self.daily_pnl += pnl
                
                # Log trade completion
                logging.info(f"TRADE EXITED - {trade.symbol} @ {exit_price:.2f}, "
                           f"Reason: {exit_reason}, P&L: ₹{pnl:.2f}")
                
                # Remove from active trades
                del self.active_trades[index_name]
                
                # Log to trade history file
                self.log_trade_to_file(trade)
                
        except Exception as e:
            logging.error(f"Error exiting trade: {e}")

    def log_trade_to_file(self, trade: TradeRecord):
        """Log completed trade to file"""
        try:
            trade_data = {
                'timestamp': trade.entry_time.isoformat(),
                'symbol': trade.symbol,
                'direction': trade.direction,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'pnl': trade.pnl,
                'exit_reason': trade.exit_reason,
                'partial_exits': trade.partial_exits,
                'holding_time_minutes': (trade.exit_time - trade.entry_time).total_seconds() / 60
            }
            
            # Append to trade log file
            with open('trade_history.json', 'a') as f:
                f.write(json.dumps(trade_data) + '\n')
                
        except Exception as e:
            logging.error(f"Error logging trade to file: {e}")

    def run_strategy(self):
        """Main strategy execution loop"""
        try:
            logging.info("Starting Enhanced 5-Minute Breakout Strategy")
            
            # Wait for market open
            self.wait_for_market_open()
            
            # Set trading active
            self.trading_active = True
            
            # Wait for first candle completion (9:20 AM)
            first_candle_end = datetime.strptime(
                self.config['timing']['first_candle_end_time'], '%H:%M'
            ).time()
            
            while self.get_current_ist_time().time() < first_candle_end:
                time.sleep(10)
            
            # Capture first candle
            self.capture_first_candle()
            
            if not self.first_candle_captured:
                logging.error("Failed to capture first candle. Exiting.")
                return
            
            # Start monitoring for breakouts
            self.monitor_breakouts()
            
        except KeyboardInterrupt:
            logging.info("Strategy stopped by user")
        except Exception as e:
            logging.error(f"Strategy error: {e}")
            logging.error(traceback.format_exc())
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources and close positions"""
        logging.info("Cleaning up...")
        
        self.trading_active = False
        
        # Close any remaining positions
        for index_name in list(self.active_trades.keys()):
            trade = self.active_trades[index_name]
            current_price = self.get_option_price(trade.symbol)
            if current_price:
                self.exit_trade(index_name, current_price, "CLEANUP")
        
        # Close WebSocket connection
        if self.ws:
            self.ws.close()
        
        logging.info(f"Strategy completed. Daily P&L: ₹{self.daily_pnl:.2f}")

if __name__ == "__main__":
    # Initialize and run strategy
    strategy = Enhanced5MinBreakoutStrategy()
    strategy.run_strategy()