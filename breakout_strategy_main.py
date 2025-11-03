# BANKNIFTY 5-min Breakout Strategy (Clean Implementation)
import time
import logging
import os
import pytz
import threading
from datetime import datetime, timedelta
from src.config import load_config
from src.token_helper import ensure_valid_token
from src.fyers_api_utils import get_fyers_client, start_market_data_websocket, get_ltp
from src.data_fetcher import DataFetcher
from src.symbol_formatter import convert_option_symbol_format, generate_option_symbol

class ISTFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.ist = pytz.timezone('Asia/Kolkata')
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, self.ist)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.strftime("%Y-%m-%d %H:%M:%S")
        return s

os.makedirs('logs', exist_ok=True)
log_file = 'logs/strategy.log'
log_fmt = '%(levelname)s - %(message)s'
ist_formatter = ISTFormatter(fmt=log_fmt)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
file_handler = logging.FileHandler(log_file, mode='w')  # Overwrite log file each run
file_handler.setFormatter(ist_formatter)
root_logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ist_formatter)
root_logger.addHandler(console_handler)

class Breakout5MinStrategy:
    def __init__(self, simulation=False, paper_trading=False):
        self.simulation = simulation
        self.paper_trading = paper_trading
        self.config = load_config()
        self.fyers = get_fyers_client() if not simulation or paper_trading else None
        self.logger = logging.getLogger()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.banknifty_symbol = self.config.get('strategy', {}).get('banknifty_symbol', 'NSE:NIFTYBANK-INDEX')
        self.banknifty_qty = self.config.get('strategy', {}).get('banknifty_qty', 35)
    # self.sl_points and self.target_points are deprecated; use % of premium instead
        self.breakout_buffer = self.config.get('strategy', {}).get('breakout_buffer', 5)
        self.log_file = 'logs/trade_history.csv'
        self.live_prices = {}
        self.data_socket = None
        # Initialize DataFetcher if we have a Fyers client (used for live or paper runs)
        self.data_fetcher = DataFetcher(self.fyers) if self.fyers is not None else None

    def log_info(self, msg):
        self.logger.info(msg)

    def run(self):
        self.log_info('Starting 5-min breakout strategy (BANKNIFTY).')
        self.wait_for_market_open()
        self.wait_until_920()
        t = threading.Thread(target=self.monitor_index, args=(self.banknifty_symbol, self.banknifty_qty, 'BANKNIFTY'), daemon=True)
        t.start()
        t.join()

    def wait_for_market_open(self):
        now = datetime.now(self.ist)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        while now < market_open:
            self.log_info('Waiting for market to open (09:15 IST)...')
            time.sleep(30)
            now = datetime.now(self.ist)

    def wait_until_920(self):
        now = datetime.now(self.ist)
        target = now.replace(hour=9, minute=20, second=0, microsecond=0)
        if now < target:
            seconds = (target - now).total_seconds()
            self.log_info(f'Waiting {int(seconds)} seconds until 9:20 IST for first 5-min candle to form...')
            time.sleep(seconds)
        self.log_info('Reached 9:20 IST. Proceeding to fetch first 5-min candle.')

    def fetch_5min_candle(self, symbol):
        # Use DataFetcher for reliable candle data
        candle_data = self.data_fetcher.get_first_5min_candle(symbol)
        if candle_data:
            o, h, l, cl, candle_time = candle_data
            self.log_info(f"5-min OHLC for {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
            return candle_data
        self.log_info(f"[ERROR] Could not fetch 5-min candle for {symbol}.")
        return None

    def fetch_option_ohlc(self, symbol):
        candle_data = self.data_fetcher.get_first_5min_candle(symbol)
        if candle_data:
            o, h, l, cl, candle_time = candle_data
            self.log_info(f"5-min OHLC for option {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
            return candle_data
        self.log_info(f"[ERROR] Could not fetch 5-min candle for option {symbol}.")
        return None

    def get_atm_option_symbol(self, spot, option_type, index_name):
        """Generate ATM option symbol with proper expiry selection (BANKNIFTY: Fyers option chain only)"""
        try:
            # Check if BANKNIFTY options are enabled
            if 'BANK' in index_name.upper():
                banknifty_options_enabled = self.config.get('strategy', {}).get('banknifty_options_enabled', False)
                if not banknifty_options_enabled:
                    self.log_info(f"BANKNIFTY options not enabled in config - skipping {option_type} for {index_name}")
                    return None
            # Calculate step size and ATM strike
            step = 100 if 'BANK' in index_name.upper() else 50
            strike = round(spot / step) * step
            today = datetime.now(self.ist)
            if 'BANK' in index_name.upper():
                # BANKNIFTY: Always use next available expiry from Fyers option chain
                from src.banknifty_symbol_helper import get_next_banknifty_expiry, get_banknifty_option_symbol
                expiry_date = get_next_banknifty_expiry(today)
                self.log_info(f"[DEBUG] Selected BANKNIFTY expiry date: {expiry_date}")
                underlying = 'BANKNIFTY'
                try:
                    symbol = get_banknifty_option_symbol(int(strike), option_type, expiry_date.date())
                    self.log_info(f"Selected BANKNIFTY {option_type} symbol from Fyers option chain: {symbol}")
                    return symbol
                except Exception as e:
                    self.log_info(f"[ERROR] BANKNIFTY option chain lookup failed: {e}")
                    # Fallback to formatter if option chain fails
                    from src.symbol_formatter import generate_option_symbol
                    symbol = generate_option_symbol(underlying, expiry_date.date(), int(strike), option_type)
                    self.log_info(f"Fallback BANKNIFTY symbol: {symbol}")
                    return symbol
            else:
                # NIFTY: Weekly options expire on Thursday
                target_weekday = 3  # Thursday
                days_to_expiry = (target_weekday - today.weekday()) % 7
                if days_to_expiry == 0:  # Today is Thursday
                    if today.hour > 15 or (today.hour == 15 and today.minute >= 30):
                        days_to_expiry = 7  # Next Thursday after market close
                expiry_date = today + timedelta(days=days_to_expiry)
            # For NIFTY, use Fyers option chain to get exact symbol
            from src.nifty_symbol_helper import get_nifty_atm_option_symbol
            try:
                symbol = get_nifty_atm_option_symbol(spot, expiry_date.strftime('%d-%m-%Y'), option_type)
                if symbol:
                    self.log_info(f"Selected NIFTY {option_type} symbol from Fyers option chain: {symbol}")
                    return symbol
                else:
                    self.log_info(f"[ERROR] NIFTY option chain lookup failed, falling back to formatter.")
                    symbol = generate_option_symbol('NIFTY', expiry_date.date(), int(strike), option_type)
                    self.log_info(f"Fallback NIFTY symbol: {symbol}")
                    return symbol
            except Exception as e:
                self.log_info(f"[ERROR] NIFTY option chain lookup exception: {e}")
                symbol = generate_option_symbol('NIFTY', expiry_date.date(), int(strike), option_type)
                self.log_info(f"Fallback NIFTY symbol: {symbol}")
                return symbol
        except Exception as e:
            self.log_info(f"[ERROR] Failed to generate option symbol: {e}")
            return None

    def get_ltp(self, symbol):
        # Use Fyers API utility for LTP
        from src.fyers_api_utils import get_ltp
        if self.fyers:
            return get_ltp(self.fyers, symbol)
        else:
            self.log_info(f"[ERROR] Fyers client not initialized for LTP fetch.")
            return None

    def setup_websocket(self, symbols):
        # Dummy websocket setup
        pass

    def monitor_index(self, symbol, qty, index_name):
        candle = self.fetch_5min_candle(symbol)
        if not candle:
            return
        open_, high, low, close, candle_time = candle
        ce_symbol = self.get_atm_option_symbol(high, 'CE', index_name)
        pe_symbol = self.get_atm_option_symbol(low, 'PE', index_name)
        ce_ohlc = self.fetch_option_ohlc(ce_symbol)
        pe_ohlc = self.fetch_option_ohlc(pe_symbol)
        if not ce_ohlc or not pe_ohlc:
            return
        ce_high = ce_ohlc[1]
        pe_high = pe_ohlc[1]
        ce_breakout = ce_high + self.breakout_buffer
        pe_breakout = pe_high + self.breakout_buffer
        self.log_info(f"Monitoring CE {ce_symbol} for breakout above {ce_breakout}")
        self.log_info(f"Monitoring PE {pe_symbol} for breakout above {pe_breakout}")
        self.monitor_option_high_breakout(ce_symbol, pe_symbol, ce_breakout, pe_breakout, qty, index_name)

    def monitor_option_high_breakout(self, ce_symbol, pe_symbol, ce_breakout, pe_breakout, qty, index_name):
        breakout_taken = False
        start_time = time.time()
        max_monitor_time = 60 * 60
        max_premium_pct = self.config.get('strategy', {}).get('max_entry_premium_pct', 5)  # Default 5%
        try:
            while not breakout_taken and (time.time() - start_time < max_monitor_time):
                for opt_symbol, breakout_level, opt_type in [
                    (ce_symbol, ce_breakout, 'CE'),
                    (pe_symbol, pe_breakout, 'PE')
                ]:
                    ltp = self.get_ltp(opt_symbol)
                    if ltp is not None and ltp > breakout_level:
                        premium_over_breakout = ((ltp - breakout_level) / breakout_level) * 100
                        if premium_over_breakout > max_premium_pct:
                            self.log_info(f"WARNING: BREAKOUT DETECTED but ENTRY TOO RISKY!")
                            self.log_info(f"   {opt_type} LTP: {ltp} | Breakout: {breakout_level}")
                            self.log_info(f"   Premium over breakout: {premium_over_breakout:.1f}% (max allowed: {max_premium_pct}%)")
                            self.log_info(f"   Skipping entry to avoid overpriced trade")
                            continue
                        self.log_info(f"*** BREAKOUT DETECTED! {opt_type} {opt_symbol} LTP: {ltp} > {breakout_level}")
                        self.log_info(f"   Premium over breakout: {premium_over_breakout:.1f}% (within {max_premium_pct}% limit)")
                        self.execute_trade(opt_symbol, ltp, qty, 'BUY', index_name)
                        breakout_taken = True
                        break
                    else:
                        if ltp is not None:
                            self.log_info(f"Monitoring: {opt_type} {opt_symbol} LTP: {ltp:.2f} | Need > {breakout_level:.2f}")
                        else:
                            self.log_info(f"Monitoring: {opt_type} {opt_symbol} LTP: None | Need > {breakout_level:.2f}")
                if breakout_taken:
                    break
                time.sleep(0.5)
            if not breakout_taken:
                self.log_info(f"No breakout detected for CE or PE option within monitoring window.")
        except Exception as e:
            self.log_info(f"[ERROR] Exception in monitoring loop: {e}")

    def execute_trade(self, symbol, entry_price, lots, side, index_name):
        import pandas as pd
        import os
        import csv
        # local import for Excel formatting
        try:
            import openpyxl
            from openpyxl.utils import get_column_letter
            from openpyxl.styles import Font, numbers
        except Exception:
            openpyxl = None
            get_column_letter = None
            Font = None
            numbers = None
        excel_file = 'logs/trade_status_history.xlsx'
        csv_file = 'logs/trade_status_history.csv'
        status_columns = [
            'Time', 'Symbol', 'Entry', 'LTP', 'SL', 'Trailing SL', 'Target', 'PnL', 'MaxUp (₹)', 'MaxUp (%)', 'MaxDown (₹)'
        ]
        if not os.path.exists('logs'):
            os.makedirs('logs')
        quantity = lots * 35
    # SL and target are now 10% of entry price (premium)
    sl = entry_price * 0.90
    target = entry_price * 1.10
        entry_time = datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S')
        self.log_info(f"Trade ENTRY: {side} {symbol} - {lots} lots ({quantity} qty) at {entry_price} | Time: {entry_time}")
        self.log_info(f"   Stop Loss: {sl} | Target: {target}")
        self.log_trade(symbol, entry_price, quantity, side, 'ENTRY', entry_time)
        # Continuous trade monitoring loop
        max_holding_minutes = self.config.get('strategy', {}).get('max_holding_minutes', 30)
        start_time = time.time()
        maxup = float('-inf')
        maxdown = float('inf')
    trailing_sl = sl
        exit_reason = None
        exit_price = None
        while (time.time() - start_time) < max_holding_minutes * 60:
            ltp = self.get_ltp(symbol)
            if ltp is None:
                self.log_info(f"[MONITOR] Could not fetch LTP for {symbol}. Skipping this check.")
                time.sleep(5)
                continue
            pnl = (ltp - entry_price) * quantity
            maxup = max(maxup, pnl)
            maxdown = min(maxdown, pnl)
            maxup_pct = (maxup / (entry_price * quantity)) * 100 if entry_price and quantity else 0
            # Example trailing SL logic: move up trailing SL if price moves up by 10% from entry
            if ltp > entry_price * 1.10:
                trailing_sl = max(trailing_sl, ltp * 0.90)
            # Log every second to the main log file for live monitoring
            self.log_info(f"[TRADE STATUS] Symbol: {symbol} | Entry: {entry_price} | LTP: {ltp} | SL: {sl} | Trailing SL: {trailing_sl} | Target: {target} | PnL: {pnl} | MaxUp: {maxup} | MaxUp(%): {maxup_pct:.2f} | MaxDown: {maxdown}")
            # (no per-update Excel writes anymore)
            if ltp <= trailing_sl:
                exit_reason = 'STOPLOSS'
                exit_price = ltp
                self.log_info(f"[EXIT] Stop Loss hit for {symbol} at {ltp}")
                break
            elif ltp >= target:
                exit_reason = 'TARGET'
                exit_price = ltp
                self.log_info(f"[EXIT] Target hit for {symbol} at {ltp}")
                break
            time.sleep(1)
        if exit_reason:
            exit_time = datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S')
            self.log_trade(symbol, exit_price, quantity, side, exit_reason, exit_time)
            # Write final status to Excel
            final_ltp = exit_price
            final_pnl = (final_ltp - entry_price) * quantity if final_ltp is not None else None
            final_maxup_pct = (maxup / (entry_price * quantity) * 100) if entry_price and quantity else 0
            final_row = [exit_time, symbol, entry_price, final_ltp, sl, trailing_sl, target, final_pnl, maxup, final_maxup_pct, maxdown]
            # Append and write with Excel formatting
            self._append_final_row_with_format(excel_file, csv_file, final_row, status_columns)
            # Also append to CSV (create header if not exists)
            write_header = not os.path.exists(csv_file)
            with open(csv_file, 'a', newline='') as cf:
                writer = csv.writer(cf)
                if write_header:
                    writer.writerow(status_columns)
                # Ensure values are serializable
                writer.writerow([str(x) if x is not None else '' for x in final_row])
        else:
            # Max holding period exit
            exit_time = datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S')
            ltp = self.get_ltp(symbol)
            self.log_info(f"[EXIT] Max holding period reached for {symbol} at {ltp}")
            self.log_trade(symbol, ltp, quantity, side, 'MAX_HOLDING', exit_time)
            # Write final status to Excel for max holding exit
            final_ltp = ltp
            final_pnl = (final_ltp - entry_price) * quantity if final_ltp is not None else None
            final_maxup_pct = (maxup / (entry_price * quantity) * 100) if entry_price and quantity else 0
            final_row = [exit_time, symbol, entry_price, final_ltp, sl, trailing_sl, target, final_pnl, maxup, final_maxup_pct, maxdown]
            # Append and write with Excel formatting
            self._append_final_row_with_format(excel_file, csv_file, final_row, status_columns)
            # Also append to CSV (create header if not exists)
            write_header = not os.path.exists(csv_file)
            with open(csv_file, 'a', newline='') as cf:
                writer = csv.writer(cf)
                if write_header:
                    writer.writerow(status_columns)
                writer.writerow([str(x) if x is not None else '' for x in final_row])

    def log_trade(self, symbol, price, qty, side, reason, time_str):
        row = f'{time_str},{symbol},{side},{price},{qty},{reason}\n'
        with open(self.log_file, 'a') as f:
            f.write(row)
        self.logger.info(f"Trade logged: {row.strip()}")

    def _append_final_row_with_format(self, excel_file, csv_file, final_row, columns):
        """Append a final_row to excel_file with nice formatting (bold headers, number formats, auto-width).
        Also append to CSV. This keeps the heavy formatting logic in one place.
        """
        import pandas as pd
        import csv
        try:
            # Read existing Excel if available, else create DataFrame
            if os.path.exists(excel_file):
                df = pd.read_excel(excel_file)
                df.loc[len(df)] = final_row
            else:
                df = pd.DataFrame([final_row], columns=columns)
            # Write to Excel first (pandas -> openpyxl)
            df.to_excel(excel_file, index=False)
            # If openpyxl is available, apply formatting
            try:
                from openpyxl import load_workbook
                from openpyxl.utils import get_column_letter
                from openpyxl.styles import Font, numbers
                wb = load_workbook(excel_file)
                ws = wb.active
                # Bold headers
                header_font = Font(bold=True)
                for col_idx, col in enumerate(columns, start=1):
                    cell = ws[f"{get_column_letter(col_idx)}1"]
                    cell.font = header_font
                # Apply number formats for numeric columns (Entry,LTP,SL,Trailing SL,Target,PnL,MaxUp,MaxUp(%),MaxDown)
                # Use Indian currency format for rupee columns and percent format for MaxUp (%)
                # Currency format example: ₹#,##0.00 (Excel may not display the currency symbol on systems without locale support,
                # but the number_format will still format numbers with thousand separators and two decimals.)
                currency_format = '₹#,##0.00'
                num_format = '#,##0.00'
                pct_format = '0.00%'
                col_map = {name: idx+1 for idx, name in enumerate(columns)}
                # Money columns: Entry, LTP, SL, Trailing SL, Target, PnL, MaxUp (₹), MaxDown (₹)
                numeric_cols = ['Entry', 'LTP', 'SL', 'Trailing SL', 'Target', 'PnL', 'MaxUp (₹)', 'MaxDown (₹)']
                pct_cols = ['MaxUp (%)']
                for name in numeric_cols:
                    if name in col_map:
                        col_letter = get_column_letter(col_map[name])
                        for r in range(2, ws.max_row+1):
                            try:
                                # Use currency format for PnL/rupee columns, generic number format for others
                                if name in ('PnL', 'MaxUp (₹)', 'MaxDown (₹)'):
                                    ws[f"{col_letter}{r}"].number_format = currency_format
                                else:
                                    ws[f"{col_letter}{r}"].number_format = num_format
                            except Exception:
                                pass
                for name in pct_cols:
                    if name in col_map:
                        col_letter = get_column_letter(col_map[name])
                        for r in range(2, ws.max_row+1):
                            try:
                                ws[f"{col_letter}{r}"].number_format = pct_format
                            except Exception:
                                pass
                # Auto-width columns
                for col in ws.columns:
                    max_length = 0
                    col_letter = get_column_letter(col[0].column)
                    for cell in col:
                        try:
                            val = str(cell.value) if cell.value is not None else ''
                            if len(val) > max_length:
                                max_length = len(val)
                        except Exception:
                            pass
                    adjusted_width = (max_length + 2)
                    ws.column_dimensions[col_letter].width = adjusted_width
                wb.save(excel_file)
            except Exception as e:
                self.log_info(f"[WARN] Could not apply Excel formatting: {e}")
        except Exception as e:
            self.log_info(f"[ERROR] Failed to write Excel file {excel_file}: {e}")

        # Append to CSV (create header if not exists)
        try:
            write_header = not os.path.exists(csv_file)
            with open(csv_file, 'a', newline='') as cf:
                writer = csv.writer(cf)
                if write_header:
                    writer.writerow(columns)
                writer.writerow([str(x) if x is not None else '' for x in final_row])
        except Exception as e:
            self.log_info(f"[ERROR] Failed to write CSV file {csv_file}: {e}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--simulate', action='store_true', help='Run in simulation mode (dummy data)')
    parser.add_argument('--paper', action='store_true', help='Run in paper trading mode (real data, no real trades)')
    args = parser.parse_args()
    strategy = Breakout5MinStrategy(simulation=args.simulate, paper_trading=args.paper)
    strategy.run()

    def wait_for_market_open(self):
        now = datetime.now(self.ist)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        if now >= market_open:
            # After 09:15, but always want to use 09:15-09:20 window for breakout
            self.skip_time_rule = False  # Always use 09:15-09:20
            self.log_info("[USER] Script started after 09:15. Will attempt to fetch 09:15-09:20 OHLC for breakout.")
            return
        while True:
            now = datetime.now(self.ist).time()
            if now >= datetime.strptime('09:15', '%H:%M').time():
                break
            self.log_info('Waiting for market to open (09:15 IST)...')
            time.sleep(30)

    def wait_until_920(self):
        now = datetime.now(self.ist)
        target = now.replace(hour=9, minute=20, second=0, microsecond=0)
        if now < target:
            seconds = (target - now).total_seconds()
            self.log_info(f'Waiting {int(seconds)} seconds until 9:20 IST for first 5-min candle to form...')
            time.sleep(seconds)
            self.log_info('Reached 9:20 IST. Proceeding to fetch first 5-min candle.')

    def collect_live_5min_ohlc(self, symbol):
        # Deprecated: No longer used. Always use Fyers historical API for index OHLC.
        self.log_info(f"[SKIP] collect_live_5min_ohlc is disabled. Using Fyers historical API only for {symbol}.")
        return None

    def fetch_5min_candle(self, symbol):
        # Always use Fyers historical API to fetch 5-min OHLC for index at 09:20 IST
        if self.simulation and not self.paper_trading:
            return (20000, 20020, 19980, 20010, '09:15')
            
        # Use the new DataFetcher for more reliable candle data
        candle_data = self.data_fetcher.get_first_5min_candle(symbol)
        if candle_data:
            o, h, l, cl, candle_time = candle_data
            self.log_info(f"[ENHANCED] 5-min OHLC for {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
            return candle_data
            
        # If DataFetcher fails, fall back to the old method
        self.log_info(f"[FALLBACK] DataFetcher failed for {symbol}, trying old method")
        
        from datetime import datetime, timedelta
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        # Target 09:15-09:20 candle for breakout
        target_time = now.replace(hour=9, minute=20, second=0, microsecond=0)
        if now < target_time:
            # If before 9:20, wait until 9:20
            wait_sec = (target_time - now).total_seconds()
            if wait_sec > 0:
                self.log_info(f"Waiting {int(wait_sec)} seconds until 9:20 IST for first 5-min candle to form...")
                time.sleep(wait_sec)
            now = datetime.now(ist)
        # Retry logic for Fyers API
        for attempt in range(5):
            try:
                from_time = target_time - timedelta(minutes=5)
                to_time = target_time
                range_from = int(from_time.timestamp())
                range_to = int(to_time.timestamp())
                data = {
                    "symbol": symbol,
                    "resolution": "5",
                    "date_format": "0",  # Use 0 for epoch timestamps
                    "range_from": range_from,
                    "range_to": range_to,
                    "cont_flag": "1"
                }
                candles = self.fyers.history(data)
                if candles.get('s') == 'ok' and candles.get('candles'):
                    c = candles['candles'][-1]
                    o, h, l, cl = c[1], c[2], c[3], c[4]
                    candle_time = datetime.fromtimestamp(c[0], ist).strftime('%H:%M')
                    self.log_info(f"[API] 5-min OHLC for {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
                    return (o, h, l, cl, candle_time)
                else:
                    self.log_info(f"[RETRY] No 5-min candle data returned for {symbol} from Fyers (attempt {attempt+1}/5). Retrying...")
                    time.sleep(2)
            except Exception as e:
                self.log_info(f"[RETRY] Error fetching 5-min candle for {symbol} (attempt {attempt+1}/5): {e}")
                time.sleep(2)
        # Fallback: try to fetch the most recent 5-min candle for today
        try:
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            data = {
                "symbol": symbol,
                "resolution": "5",
                "date_format": "0",
                "range_from": int(today.timestamp()),
                "range_to": int(now.timestamp()),
                "cont_flag": "1"
            }
            candles = self.fyers.history(data)
            if candles.get('s') == 'ok' and candles.get('candles'):
                c = candles['candles'][-1]
                o, h, l, cl = c[1], c[2], c[3], c[4]
                candle_time = datetime.fromtimestamp(c[0], ist).strftime('%H:%M')
                self.log_info(f"[FALLBACK-LAST] Using most recent 5-min candle for {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
                return (o, h, l, cl, candle_time)
            else:
                self.log_info(f"[ERROR] No 5-min candle data available for {symbol} even after all fallbacks.")
                return None
        except Exception as e:
            self.log_info(f"[ERROR] Final fallback error fetching 5-min candle for {symbol}: {e}")
            return None

    def fetch_option_ohlc(self, symbol):
        # Fetch 5-min OHLC for option symbol using Fyers historical API with retry/fallback
        if self.simulation and not self.paper_trading:
            return (100, 106, 99, 105, '09:20')
            
        # Use the new DataFetcher for more reliable option data
        if self.data_fetcher:
            try:
                candle_data = self.data_fetcher.get_first_5min_candle(symbol)
                if candle_data:
                    o, h, l, cl, candle_time = candle_data
                    self.log_info(f"[ENHANCED] 5-min option OHLC for {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
                    return candle_data
            except Exception as e:
                self.log_info(f"[ERROR] DataFetcher failed for option {symbol}: {e}")
        
        # If DataFetcher fails, fall back to the old method
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        # Try up to 5 times with 2s delay to allow for Fyers data lag
        for attempt in range(5):
            try:
                # Try to get the 09:15-09:20 candle, else fallback to latest available before 09:20
                target_time = now.replace(hour=9, minute=20, second=0, microsecond=0)
                if now < target_time:
                    target_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
                else:
                    minute = (now.minute // 5) * 5
                    target_time = now.replace(minute=minute, second=0, microsecond=0)
                from_time = target_time - timedelta(minutes=5)
                to_time = target_time
                range_from = int(from_time.timestamp())
                range_to = int(to_time.timestamp())
                data = {
                    "symbol": symbol,
                    "resolution": "5",
                    "date_format": "0",
                    "range_from": range_from,
                    "range_to": range_to,
                    "cont_flag": "1"
                }
                candles = self.fyers.history(data)
                if candles.get('s') == 'ok' and candles.get('candles'):
                    c = candles['candles'][-1]
                    o, h, l, cl = c[1], c[2], c[3], c[4]
                    candle_time = datetime.fromtimestamp(c[0], ist).strftime('%H:%M')
                    self.log_info(f"[FALLBACK] Using available 5-min option candle for {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
                    return (o, h, l, cl, candle_time)
                else:
                    self.log_info(f"[RETRY] No 5-min option candle data returned for {symbol} from Fyers (attempt {attempt+1}/5). Retrying...")
                    time.sleep(2)
            except Exception as e:
                self.log_info(f"[RETRY] Error fetching 5-min option candle for {symbol} (attempt {attempt+1}/5): {e}")
                time.sleep(2)
        # As a last resort, try to fetch the most recent 5-min candle for today
        try:
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            data = {
                "symbol": symbol,
                "resolution": "5",
                "date_format": "0",
                "range_from": int(today.timestamp()),
                "range_to": int(now.timestamp()),
                "cont_flag": "1"
            }
            candles = self.fyers.history(data)
            if candles.get('s') == 'ok' and candles.get('candles'):
                c = candles['candles'][-1]
                o, h, l, cl = c[1], c[2], c[3], c[4]
                candle_time = datetime.fromtimestamp(c[0], ist).strftime('%H:%M')
                self.log_info(f"[FALLBACK-LAST] Using most recent 5-min option candle for {symbol}: O={o}, H={h}, L={l}, C={cl}, Time={candle_time}")
                return (o, h, l, cl, candle_time)
            else:
                self.log_info(f"[ERROR] No 5-min option candle data available for {symbol} even after all fallbacks.")
                return None
        except Exception as e:
            self.log_info(f"[ERROR] Final fallback error fetching 5-min option candle for {symbol}: {e}")
            return None

    def get_atm_option_symbol(self, spot, option_type, index_name):
        """Generate ATM option symbol with proper formatting"""
        try:
            # Check if BANKNIFTY options are enabled
            if 'BANK' in index_name.upper():
                banknifty_options_enabled = self.config.get('strategy', {}).get('banknifty_options_enabled', False)
                if not banknifty_options_enabled:
                    self.log_info(f"BANKNIFTY options not enabled in config - skipping {option_type} for {index_name}")
                    return None
            
            # Calculate step size and ATM strike
            step = 100 if 'BANK' in index_name.upper() else 50
            strike = round(spot / step) * step
            
            # Calculate expiry based on index type
            today = datetime.now(self.ist)
            
            if 'BANK' in index_name.upper():
                # BANKNIFTY: Always use next available expiry from Fyers option chain
                from src.banknifty_symbol_helper import get_next_banknifty_expiry, get_banknifty_option_symbol
                expiry_date = get_next_banknifty_expiry(today)
                self.log_info(f"[DEBUG] Selected BANKNIFTY expiry date: {expiry_date}")
                underlying = 'BANKNIFTY'
                strike = round(spot / 100) * 100
                try:
                    symbol = get_banknifty_option_symbol(int(strike), option_type, expiry_date.date())
                    self.log_info(f"Selected BANKNIFTY {option_type} symbol from Fyers option chain: {symbol}")
                    return symbol
                except Exception as e:
                    self.log_info(f"[ERROR] BANKNIFTY option chain lookup failed: {e}")
                    # Fallback to formatter if option chain fails
                    from src.symbol_formatter import generate_option_symbol
                    symbol = generate_option_symbol(underlying, expiry_date.date(), int(strike), option_type)
                    self.log_info(f"Fallback BANKNIFTY symbol: {symbol}")
                    return symbol
            else:
                # NIFTY: Weekly options expire on Thursday  
                target_weekday = 3  # Thursday
                days_to_expiry = (target_weekday - today.weekday()) % 7
                if days_to_expiry == 0:  # Today is Thursday
                    if today.hour > 15 or (today.hour == 15 and today.minute >= 30):
                        days_to_expiry = 7  # Next Thursday after market close
                
                # For Oct 10, 2025, use Oct 14 expiry (which works based on logs)
                if today.date() <= datetime(2025, 10, 14).date():
                    expiry_date = datetime(2025, 10, 14, tzinfo=self.ist)
                else:
                    expiry_date = today + timedelta(days=days_to_expiry)
            
            # ...existing code for NIFTY only...
            # For NIFTY, use Fyers option chain to get exact symbol
            from src.nifty_symbol_helper import get_nifty_atm_option_symbol
            try:
                symbol = get_nifty_atm_option_symbol(spot, expiry_date.strftime('%d-%m-%Y'), option_type)
                if symbol:
                    self.log_info(f"Selected NIFTY {option_type} symbol from Fyers option chain: {symbol}")
                    return symbol
                else:
                    self.log_info(f"[ERROR] NIFTY option chain lookup failed, falling back to formatter.")
                    symbol = generate_option_symbol('NIFTY', expiry_date.date(), int(strike), option_type)
                    self.log_info(f"Fallback NIFTY symbol: {symbol}")
                    return symbol
            except Exception as e:
                self.log_info(f"[ERROR] NIFTY option chain lookup exception: {e}")
                symbol = generate_option_symbol('NIFTY', expiry_date.date(), int(strike), option_type)
                self.log_info(f"Fallback NIFTY symbol: {symbol}")
                return symbol
            
        except Exception as e:
            self.log_info(f"[ERROR] Failed to generate option symbol: {e}")
            return None
        # Convert to Fyers format
        return convert_option_symbol_format(symbol)

    def get_ltp(self, symbol):
        if self.simulation and not self.paper_trading:
            return 100
            
        # Use enhanced LTP method from DataFetcher if available
        if self.data_fetcher:
            try:
                ltp = self.data_fetcher.get_ltp_enhanced(symbol)
                if ltp is not None:
                    return ltp
            except Exception as e:
                self.log_info(f"[ERROR] DataFetcher LTP method failed: {e}")
        
        # Fall back to original method
        try:
            return get_ltp(self.fyers, symbol)
        except Exception as e:
            self.log_info(f"Error fetching LTP for {symbol}: {e}")
            return None

    def setup_websocket(self, symbols):
        # Temporarily disable WebSocket due to API parameter issues
        websocket_enabled = self.config.get('strategy', {}).get('enable_websocket', False)
        if not websocket_enabled:
            self.log_info("WebSocket disabled in configuration - using polling for live prices")
            return
            
        def ws_handler(symbol, key, value, tick_data):
            if key == 'ltp':
                self.live_prices[symbol] = float(value)
        try:
            self.data_socket = start_market_data_websocket(symbols=symbols, callback_handler=ws_handler)
            if self.data_socket:
                self.log_info(f"WebSocket subscription successful for: {symbols}")
            else:
                self.log_info("WebSocket subscription failed.")
        except Exception as e:
            self.log_info(f"WebSocket setup error: {e}")

    def monitor_breakout(self, symbol, ce_symbol, pe_symbol, ce_breakout, pe_breakout, qty, index_name, entry_buffer=2):
        self.log_info(f"Monitoring {symbol} for breakout. CE: {ce_symbol} ({ce_breakout}), PE: {pe_symbol} ({pe_breakout})")
        symbols_to_subscribe = [ce_symbol, pe_symbol]
        if not self.simulation or self.paper_trading:
            self.setup_websocket(symbols_to_subscribe)
        breakout_taken = False
        start_time = time.time()
        max_monitor_time = 60 * 60  # 1 hour max
        while not breakout_taken and (time.time() - start_time < max_monitor_time):
            for opt_symbol, breakout_level, opt_type in [
                (ce_symbol, ce_breakout, 'CE'),
                (pe_symbol, pe_breakout, 'PE')
            ]:
                # Do NOT fetch option OHLC at 9:20 here; just monitor LTP for breakout
                if self.simulation and not self.paper_trading:
                    ltp = breakout_level  # Simulate immediate breakout
                else:
                    ltp = self.live_prices.get(opt_symbol) or self.get_ltp(opt_symbol)
                # Check if LTP has broken above the breakout level
                if ltp is not None and ltp >= breakout_level:
                    # Check if entry price is not too far above breakout level (risk management)
                    max_premium_pct = self.config.get('strategy', {}).get('max_entry_premium_pct', 5)
                    premium_over_breakout = ((ltp - breakout_level) / breakout_level) * 100
                    
                    if premium_over_breakout > max_premium_pct:
                        self.log_info(f"WARNING: BREAKOUT DETECTED but ENTRY TOO RISKY!")
                        self.log_info(f"   {opt_type} LTP: {ltp} | Breakout: {breakout_level}")
                        self.log_info(f"   Premium over breakout: {premium_over_breakout:.1f}% (max allowed: {max_premium_pct}%)")
                        self.log_info(f"   Skipping entry to avoid overpriced trade")
                        # Continue monitoring for better entry or timeout
                        continue
                    
                    self.log_info(f"*** BREAKOUT DETECTED! {opt_type} option {opt_symbol} ***")
                    self.log_info(f"   Current LTP: {ltp} | Breakout Level: {breakout_level}")
                    self.log_info(f"   Premium over breakout: {premium_over_breakout:.1f}% (within {max_premium_pct}% limit)")
                    self.log_info(f"   Executing BUY order for {qty} lots...")
                    self.execute_trade(opt_symbol, ltp, qty, 'BUY', index_name)
                    breakout_taken = True
                    break
                else:
                    # Log current monitoring status every 30 seconds
                    if int(time.time()) % 30 == 0:
                        if ltp is not None:
                            self.log_info(f"Monitoring: {opt_type} {ltp:.2f} | Need: {breakout_level:.2f} | Gap: {(breakout_level - ltp):.2f}")
            time.sleep(0.5)  # Faster polling for better SL/Target execution
        if not breakout_taken:
            self.log_info(f"No breakout detected for {symbol} within monitoring window.")

    def execute_trade(self, symbol, entry_price, lots, side, index_name):
        # Convert lots to quantity
        if 'NIFTY' in index_name and 'BANK' not in index_name:
            quantity = lots * 75  # NIFTY lot size
        else:
            quantity = lots * 35  # BANKNIFTY lot size
            
        sl = entry_price - self.sl_points
        target = entry_price + self.target_points
        entry_time = datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S')
        
        if self.paper_trading:
            self.log_info(f"[PAPER TRADE] {side} {symbol} - {lots} lots ({quantity} qty) at {entry_price}")
            self.log_info(f"   Stop Loss: {sl} | Target: {target}")
        else:
            self.log_info(f"Trade executed: {side} {symbol} - {lots} lots ({quantity} qty) at {entry_price}")
            self.log_info(f"   Stop Loss: {sl} | Target: {target}")
        
        self.log_trade(symbol, entry_price, quantity, side, 'BREAKOUT', entry_time)
        self.manage_position(symbol, entry_price, quantity, sl, target, side, entry_time, index_name)

    def manage_position(self, symbol, entry, qty, sl, target, side, entry_time, index_name):
        max_holding_minutes = 60
        trailing_sl = sl
        exit_reason = None
        max_up = float('-inf')  # Maximum unrealized profit
        max_down = float('inf') # Maximum drawdown (largest unrealized loss)
        for minute in range(max_holding_minutes * 60):  # every second
            if self.simulation and not self.paper_trading:
                ltp = entry + self.target_points  # Simulate target hit
            else:
                ltp = self.get_ltp(symbol)
            pnl = (ltp - entry) * qty if side == 'BUY' else (entry - ltp) * qty
            pnl_pct = ((ltp - entry) / entry) * 100 if entry else 0
            # Track max_up and max_down
            if pnl > max_up:
                max_up = pnl
            if pnl < max_down:
                max_down = pnl
            self.log_info(f"[MONITOR] {symbol} | Entry: {entry} | LTP: {ltp} | PnL: {pnl:.2f} | SL: {sl} | Trailing SL: {trailing_sl} | PnL%: {pnl_pct:.2f} | MaxUp: {max_up:.2f} | MaxDown: {max_down:.2f}")
            if ltp <= trailing_sl:
                exit_reason = 'STOPLOSS'
                exit_price = trailing_sl
                break
            elif ltp >= target:
                exit_reason = 'TARGET'
                exit_price = target
                break
            # Trailing SL logic
            if ltp > entry and ltp - entry > self.sl_points:
                new_trailing = ltp - self.sl_points
                if new_trailing > trailing_sl:
                    self.log_info(f"Trailing SL moved up to {new_trailing}")
                    trailing_sl = new_trailing
            time.sleep(0.2)  # Ultra-fast 200ms polling for SL/Target execution
        else:
            exit_reason = 'TIME_EXIT'
            exit_price = ltp
        exit_time = datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S')
        self.log_info(f"Exiting {symbol} at {exit_price} due to {exit_reason} | MaxUp: {max_up:.2f} | MaxDown: {max_down:.2f}")
        self.log_trade(symbol, exit_price, qty, 'SELL', exit_reason, exit_time)

    def log_trade(self, symbol, price, qty, side, reason, time_str):
        row = f'{time_str},{symbol},{side},{price},{qty},{reason}\n'
        with open(self.log_file, 'a') as f:
            f.write(row)
        self.logger.info(f"Trade logged: {row.strip()}")
        
    # ...existing code...

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--simulate', action='store_true', help='Run in simulation mode (dummy data)')
    parser.add_argument('--paper', action='store_true', help='Run in paper trading mode (real data, no real trades)')
    args = parser.parse_args()
    strategy = Breakout5MinStrategy(simulation=args.simulate, paper_trading=args.paper)
    strategy.run()
