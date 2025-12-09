# Multiple Strike Price Monitoring System - No LTP Mixup Architecture

## Overview
This document explains how our BANKNIFTY breakout strategy monitors multiple option strike prices (CE and PE) simultaneously without any LTP (Last Traded Price) mixups. This is a robust pattern you can apply to any multi-instrument trading system.

## Core Architecture

### 1. **Symbol-Based LTP Storage (Dictionary Pattern)**
```python
class Breakout5MinStrategy:
    def __init__(self):
        self.live_prices = {}  # Key-Value store: {symbol: ltp}
        self.data_socket = None
```

**Why This Works:**
- Each option symbol gets its own dictionary entry
- No possibility of LTP crossover between instruments
- Thread-safe for concurrent updates

### 2. **WebSocket Callback Handler**
```python
def setup_websocket(self, symbols):
    def ws_handler(symbol, key, value, tick_data):
        if key == 'ltp':
            self.live_prices[symbol] = float(value)  # CRITICAL: Symbol-specific storage
    
    self.data_socket = start_market_data_websocket(
        symbols=symbols, 
        callback_handler=ws_handler
    )
```

**Key Features:**
- `symbol` parameter ensures exact mapping
- Each websocket tick updates only the correct symbol's LTP
- Real-time updates without polling overhead

### 3. **Dual Strike Monitoring Loop**
```python
def monitor_breakout(self, symbol, ce_symbol, pe_symbol, ce_breakout, pe_breakout, qty, index_name):
    # Subscribe to BOTH strikes simultaneously
    symbols_to_subscribe = [ce_symbol, pe_symbol]
    self.setup_websocket(symbols_to_subscribe)
    
    while not breakout_taken:
        # Monitor BOTH strikes in single loop
        for opt_symbol, breakout_level, opt_type in [
            (ce_symbol, ce_breakout, 'CE'),
            (pe_symbol, pe_breakout, 'PE')
        ]:
            # Get symbol-specific LTP
            ltp = self.live_prices.get(opt_symbol) or self.get_ltp(opt_symbol)
            
            # Check breakout condition
            if ltp is not None and ltp >= breakout_level:
                # Execute trade for THIS specific symbol
                self.execute_trade(opt_symbol, ltp, qty, 'BUY', index_name)
                breakout_taken = True
                break
```

**Anti-Mixup Mechanisms:**
1. **Explicit Symbol Mapping**: Each iteration uses `opt_symbol` variable
2. **Fallback LTP Fetch**: If websocket fails, `get_ltp(opt_symbol)` ensures correct symbol
3. **First-Win Logic**: `breakout_taken = True` prevents multiple executions

### 4. **Symbol Generation Isolation**
```python
def get_atm_option_symbol(self, spot, option_type, index_name):
    # BANKNIFTY: 100-point step size
    if 'BANK' in index_name:
        step = 100
        strike = round(spot / step) * step
        symbol = get_banknifty_option_symbol(int(strike), option_type, expiry_date.date())
    
    # NIFTY: 50-point step size  
    else:
        step = 50
        strike = round(spot / step) * step
        symbol = generate_option_symbol('NIFTY', expiry_date.date(), int(strike), option_type)
    
    return symbol
```

**Symbol Uniqueness:**
- Each CE/PE gets distinct symbol based on strike calculation
- No possibility of symbol collision
- Format: `NSE:BANKNIFTY25DEC52000CE` vs `NSE:BANKNIFTY25DEC51500PE`

## Real-World Implementation Example

### Scenario: BANKNIFTY at 52,000
```python
# 9:20 AM - First candle analysis
high = 52,150  # First candle high
low = 51,850   # First candle low

# Generate unique symbols
ce_symbol = "NSE:BANKNIFTY25DEC52200CE"  # ATM based on high
pe_symbol = "NSE:BANKNIFTY25DEC51900PE"  # ATM based on low

# Set breakout levels
ce_breakout = 125.50  # CE option high from 9:15-9:20
pe_breakout = 110.25  # PE option high from 9:15-9:20

# Start monitoring BOTH simultaneously
monitor_breakout(
    symbol="NSE:NIFTYBANK-INDEX",
    ce_symbol=ce_symbol,      # Unique CE symbol
    pe_symbol=pe_symbol,      # Unique PE symbol  
    ce_breakout=ce_breakout,  # CE-specific breakout level
    pe_breakout=pe_breakout,  # PE-specific breakout level
    qty=1,                    # 1 lot = 35 units
    index_name="BANKNIFTY"
)
```

### Real-Time Monitoring Flow:
```python
# Websocket receives ticks for BOTH symbols
# Tick 1: NSE:BANKNIFTY25DEC52200CE LTP = 123.50
self.live_prices["NSE:BANKNIFTY25DEC52200CE"] = 123.50

# Tick 2: NSE:BANKNIFTY25DEC51900PE LTP = 108.75  
self.live_prices["NSE:BANKNIFTY25DEC51900PE"] = 108.75

# Monitoring loop checks BOTH
# CE Check: 123.50 < 125.50 (No breakout)
# PE Check: 108.75 < 110.25 (No breakout)

# Later: PE breaks out first
# Tick 3: NSE:BANKNIFTY25DEC51900PE LTP = 112.00
self.live_prices["NSE:BANKNIFTY25DEC51900PE"] = 112.00

# Monitoring detects: 112.00 >= 110.25 (PE BREAKOUT!)
# Executes: BUY NSE:BANKNIFTY25DEC51900PE at 112.00
```

## Anti-Mixup Safety Features

### 1. **Dictionary Key Isolation**
```python
# Each symbol has isolated storage
self.live_prices = {
    "NSE:BANKNIFTY25DEC52200CE": 123.50,  # CE LTP
    "NSE:BANKNIFTY25DEC51900PE": 108.75   # PE LTP  
}
# No way for CE LTP to overwrite PE LTP
```

### 2. **Explicit Symbol Passing**
```python
def execute_trade(self, symbol, entry_price, lots, side, index_name):
    # 'symbol' parameter ensures correct instrument execution
    # No ambiguity - exact symbol is passed from monitoring loop
    self.log_info(f"Trade executed: {side} {symbol} at {entry_price}")
```

### 3. **Fallback LTP Protection**
```python
def get_ltp(self, symbol):
    # If websocket fails, direct API call with exact symbol
    if self.data_fetcher:
        ltp = self.data_fetcher.get_ltp_enhanced(symbol)  # Symbol-specific call
        if ltp is not None:
            return ltp
    
    # Final fallback with symbol validation
    return get_ltp(self.fyers, symbol)
```

### 4. **Monitoring Status Logging**
```python
# Every 30 seconds, log status for EACH symbol separately
if int(time.time()) % 30 == 0:
    if ltp is not None:
        self.log_info(f"Monitoring: {opt_type} {ltp:.2f} | Need: {breakout_level:.2f} | Gap: {(breakout_level - ltp):.2f}")
```

## Implementation Checklist for Your Project

### ✅ **Essential Components:**
1. **Symbol-Key Dictionary**: `{symbol: ltp}` storage pattern
2. **WebSocket Handler**: Symbol-specific callback updates  
3. **Explicit Symbol Loops**: Never rely on implicit symbol references
4. **Fallback LTP Methods**: API calls with exact symbol parameters
5. **Single Execution Logic**: First breakout wins, others ignored

### ✅ **Testing Strategies:**
1. **Symbol Collision Test**: Ensure different symbols don't overwrite
2. **Concurrent Update Test**: Multiple websocket ticks arriving simultaneously  
3. **Fallback Test**: WebSocket failure → API fallback works correctly
4. **Race Condition Test**: Both strikes breaking out within milliseconds

### ✅ **Common Pitfalls to Avoid:**
1. ❌ **Global LTP Variable**: Never use single `current_ltp` for multiple symbols
2. ❌ **Symbol String Matching**: Avoid partial symbol matches (`if 'CE' in symbol`)
3. ❌ **Async Without Locking**: Ensure thread-safe dictionary updates
4. ❌ **Cached Stale Data**: Always validate LTP freshness for active monitoring

## Summary

The key to no-mixup multi-symbol monitoring is **symbol-specific data isolation** combined with **explicit parameter passing**. Each symbol gets its own storage slot, its own monitoring logic, and its own execution path. The dictionary pattern `self.live_prices[symbol]` is the foundation that prevents any cross-contamination between instruments.

This architecture scales to any number of symbols and any combination of instruments (options, futures, stocks) without LTP confusion.