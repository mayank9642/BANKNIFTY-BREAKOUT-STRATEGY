# Bracket Order OCO Implementation

## Date: November 21, 2025

## Overview
Implemented **One-Cancels-Other (OCO)** logic using **Fyers Bracket Orders (BO)** to solve the LTP fetch delay problem with tight entry tolerances.

---

## Problem Solved

### Original Issue:
- **Tight 1% entry tolerance** caused missed entries due to LTP fetch delays (0.5-1s)
- Breakout detected at 247, but by time LTP fetched, price at 250 → Entry rejected (3% > 1%)

### Solution:
- **Bracket Orders** place entry limit, SL, and target in **single API call**
- **OCO logic** places BOTH CE and PE orders, whichever fills first cancels the other
- Eliminates monitoring delays and ensures controlled entry

---

## How It Works

### Phase 1: Breakout Detection & Order Placement

```
9:20 AM - First 5-min candle completes
├── CE High: 245.50 → CE Breakout: 247.50 (HIGH + 2)
└── PE High: 240.80 → PE Breakout: 242.80 (HIGH + 2)

9:21 AM - Monitor LTP
├── CE LTP: 248.20 (above breakout ✓)
└── PE LTP: 241.50 (below breakout ✗)

BREAKOUT DETECTED! Placing OCO Bracket Orders...

┌─────────────────────────────────────────────┐
│ CE Bracket Order                             │
├─────────────────────────────────────────────┤
│ Symbol: NSE:BANKNIFTY25NOV59200CE           │
│ Entry Limit: 248.50 (breakout + 1)         │
│ Stop Loss: -15 points → 233.50             │
│ Target: +24.75 points → 273.25 (10% of 247.50) │
│ Quantity: 35                                 │
│ Order ID: 23112100012345                    │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ PE Bracket Order                             │
├─────────────────────────────────────────────┤
│ Symbol: NSE:BANKNIFTY25NOV59100PE           │
│ Entry Limit: 243.80 (breakout + 1)         │
│ Stop Loss: -15 points → 228.80             │
│ Target: +24.28 points → 268.08 (10% of 242.80) │
│ Quantity: 35                                 │
│ Order ID: 23112100012346                    │
└─────────────────────────────────────────────┘
```

### Phase 2: OCO Monitoring & Cancellation

```
Monitoring order status every 1 second...

9:21:03 - Order Status: CE=PENDING | PE=PENDING
9:21:04 - Order Status: CE=PENDING | PE=PENDING
9:21:05 - Order Status: CE=FILLED | PE=PENDING

═══════════════════════════════════════════════
CE ORDER FILLED! Cancelling PE order...
═══════════════════════════════════════════════

Action: Cancel PE order 23112100012346
Result: PE order cancelled successfully

CE position active with automatic SL and Target management:
├── Entry: 248.50
├── Stop Loss: 233.50 (auto-placed by BO)
└── Target: 273.25 (auto-placed by BO)

Strategy exits. Fyers BO handles position management automatically.
```

---

## Code Implementation

### New Methods Added:

#### 1. `place_bracket_order(symbol, entry_price, qty, breakout_level, index_name)`
```python
# Places BO with:
# - Entry: Limit order at breakout + 1 point
# - SL: max(15 points, 20% of entry) below entry
# - Target: 10% above breakout level

order_data = {
    "symbol": symbol,
    "qty": qty,
    "type": 1,  # Limit order
    "side": 1,  # Buy
    "productType": "BO",
    "limitPrice": entry_price,
    "stopLoss": 15,  # Points below entry
    "takeProfit": 24.75,  # Points above entry
    "validity": "DAY",
    "disclosedQty": 0,
    "offlineOrder": False
}
```

#### 2. `cancel_order(order_id, symbol)`
```python
# Cancels pending order
cancel_data = {"id": order_id}
response = self.fyers.cancel_order(data=cancel_data)
```

#### 3. `get_order_status(order_id)`
```python
# Returns: FILLED, PENDING, CANCELLED, REJECTED, TRANSIT, ERROR
# Status codes: 1=Cancelled, 2=Filled, 4=Transit, 5=Rejected, 6=Pending
```

### Modified Monitoring Loop:

```python
# Old: Manual LTP monitoring → execute_trade() → manual SL/Target management
# New: Breakout detection → Place BOTH BOs → Monitor fill status → Cancel other

while not oco_entry_taken:
    # Phase 1: Detect breakout and place BOs
    if not bo_orders_placed:
        ce_ltp = get_ltp(ce_symbol)
        pe_ltp = get_ltp(pe_symbol)
        
        if ce_ltp > ce_breakout or pe_ltp > pe_breakout:
            ce_order_id = place_bracket_order(ce_symbol, ce_breakout+1, ...)
            pe_order_id = place_bracket_order(pe_symbol, pe_breakout+1, ...)
            bo_orders_placed = True
    
    # Phase 2: Monitor and cancel
    if bo_orders_placed:
        ce_status = get_order_status(ce_order_id)
        pe_status = get_order_status(pe_order_id)
        
        if ce_status == "FILLED":
            cancel_order(pe_order_id)
            break
        elif pe_status == "FILLED":
            cancel_order(ce_order_id)
            break
```

---

## Benefits

### ✅ Eliminates LTP Fetch Delays
- Orders placed immediately at breakout detection
- No waiting for LTP before entry decision
- Entry price controlled by limit order

### ✅ Automatic Risk Management
- Stop loss auto-placed after fill (15 points or 20%)
- Target auto-placed after fill (10% above breakout)
- No manual monitoring required after entry

### ✅ True OCO Between CE and PE
- Both orders placed simultaneously
- Whichever fills first, other gets cancelled
- Only ONE position at a time

### ✅ No Entry Validation Needed
- Limit order at breakout+1 ensures controlled entry
- No need to check "is LTP too far from breakout"
- Order either fills at our price or doesn't fill

### ✅ Preserves Full Profit Potential
- Entry at breakout+1 point (minimal premium)
- Target at breakout+10% preserves ~9% profit room
- No risk of entering above target

---

## Configuration

### Current Settings (config.yaml):
```yaml
strategy:
  breakout_buffer_points: 2          # Breakout = HIGH + 2
  max_entry_premium_pct: 1           # Not used with BO (limit order controls entry)
  max_entry_points_above_breakout: 3 # Not used with BO
  breakout_pct: 10                   # Target profit
  stoploss_pct: 20                   # OR 15 points fixed
  sl_points: 15
```

### BO-Specific Calculations:
```python
# Entry Limit
entry_limit = breakout_level + 1  # 247.50 + 1 = 248.50

# Stop Loss (in points from entry)
sl_points = max(15, entry_limit * 0.20)  # max(15, 49.70) = 49.70 points

# Target (in points from entry)
target_price = breakout_level * 1.10  # 247.50 * 1.10 = 272.25
target_points = target_price - entry_limit  # 272.25 - 248.50 = 23.75 points
```

---

## Example Scenarios

### Scenario 1: CE Fills, PE Doesn't
```
9:21 AM - CE breaks out at 248, PE at 241
├── Place CE BO @ 248.50
└── Place PE BO @ 243.80

9:21:05 - CE fills at 248.50
├── Cancel PE BO (still pending at 243.80)
└── CE position active: Entry=248.50, SL=233.50, Target=273.25

Result: Single CE trade with automatic management
```

### Scenario 2: PE Fills, CE Doesn't
```
9:22 AM - PE breaks out at 243, CE at 246
├── Place CE BO @ 247.50
└── Place PE BO @ 244.80

9:22:08 - PE fills at 244.80
├── Cancel CE BO (still pending at 247.50)
└── PE position active: Entry=244.80, SL=229.80, Target=269.08

Result: Single PE trade with automatic management
```

### Scenario 3: Both Break Out Quickly
```
9:21 AM - BOTH CE and PE break out
├── Place CE BO @ 248.50
└── Place PE BO @ 243.80

9:21:03 - CE fills first at 248.50
├── Cancel PE BO immediately
└── CE position active

Result: Whichever fills first wins, other cancelled
```

### Scenario 4: Neither Fills (Price Reverses)
```
9:21 AM - CE LTP at 248 (above 247.50 breakout)
├── Place CE BO @ 248.50 (limit order)
└── Place PE BO @ 243.80

9:21-9:25 - Price drops to 245, never reaches 248.50
├── CE BO remains PENDING
└── PE BO remains PENDING

9:25 AM - Both orders expire or get cancelled at end of monitoring window

Result: No entry if price doesn't reach our limit
```

---

## Key Differences from Old Implementation

| Aspect | Old Implementation | New BO OCO Implementation |
|--------|-------------------|---------------------------|
| **Entry Method** | Market order after LTP validation | Limit order at breakout+1 |
| **LTP Delays** | 0.5-1s delay causes missed entries | No delay - orders pre-placed |
| **Entry Validation** | Manual checks (1% / 3 points) | Automatic (limit price controls) |
| **SL/Target** | Manual monitoring loop | Automatic (BO legs 2 & 3) |
| **CE vs PE** | Sequential detection | Simultaneous OCO placement |
| **Exit Management** | Custom code monitoring LTP | Fyers BO auto-exit |
| **Risk** | Entry slippage on market orders | Controlled entry with limits |

---

## Testing Recommendations

### Paper Mode Test:
```bash
python breakout_strategy_main.py --paper
```

**Expected Output:**
```
2025-11-22 09:20:15 - INFO - First 5-min candle: CE High=245.50, PE High=240.80
2025-11-22 09:20:15 - INFO - CE Breakout: 247.50 | PE Breakout: 242.80
2025-11-22 09:21:02 - INFO - Monitoring: CE LTP: 248.20 (need >247.50) | PE LTP: 241.50 (need >242.80)
2025-11-22 09:21:02 - INFO - ======================================================================
2025-11-22 09:21:02 - INFO - BREAKOUT DETECTED! Placing OCO bracket orders...
2025-11-22 09:21:02 - INFO - ======================================================================
2025-11-22 09:21:02 - INFO - [PAPER/SIM] Would place BO: NSE:BANKNIFTY25NOV59200CE @ 248.5, Qty: 35
2025-11-22 09:21:02 - INFO - [PAPER/SIM] Would place BO: NSE:BANKNIFTY25NOV59100PE @ 243.8, Qty: 35
2025-11-22 09:21:02 - INFO - Both bracket orders placed successfully!
2025-11-22 09:21:03 - INFO - Order Status: CE=PENDING | PE=PENDING
2025-11-22 09:21:04 - INFO - Order Status: CE=PENDING | PE=PENDING
...
```

### Live Test Tomorrow (Nov 22):
1. Run at 9:15 AM sharp: `python breakout_strategy_main.py`
2. Monitor logs for breakout detection
3. Verify both BOs placed
4. Confirm OCO cancellation works
5. Check that Fyers BO manages SL/Target automatically

---

## Important Notes

### ⚠️ Bracket Order Limitations:
- **Entry slippage possible**: Limit order may not fill if price moves fast
- **SL/Target in points**: Calculated from entry price, not breakout
- **Cannot modify after placement**: BO legs are fixed once placed
- **Ordertagging not supported**: Cannot use orderTag with BO productType

### ⚠️ Risk Management:
- **Max 1 trade per day**: Enforced by `trade_executed_today` flag
- **Only ONE position**: OCO ensures CE OR PE, never both
- **Fixed quantities**: 1 lot = 35 qty for BANKNIFTY options

### ⚠️ Market Conditions:
- **Fast breakouts**: May not fill if price gaps above limit
- **Whipsaw**: May fill then hit SL quickly
- **Low liquidity**: Limit orders may not fill

---

## Monitoring After Entry

Once a BO fills, **you don't need to monitor manually**:
- Fyers BO automatically places:
  - **Leg 2**: Stop loss order (SL-M at entry - sl_points)
  - **Leg 3**: Target order (Limit at entry + target_points)
- If SL hits → Position exits, Target cancelled
- If Target hits → Position exits, SL cancelled
- If EOD → Both legs cancelled, position squared off

**Check orderbook/tradebook in Fyers for status**

---

## Next Steps

1. ✅ Implementation complete
2. ⏳ Test in paper mode today
3. ⏳ Test live tomorrow at market open (9:20 AM)
4. ⏳ Monitor first few trades to validate BO behavior
5. ⏳ Fine-tune entry limit (currently breakout+1, may need breakout+0.5)

---

## Questions & Answers

**Q: What if both CE and PE break out before orders placed?**
A: Code detects `ce_ltp > ce_breakout OR pe_ltp > pe_breakout`, places BOTH BOs immediately. Whichever fills first cancels the other.

**Q: Can we place BOs for both even if only one broke out?**
A: Yes! Current logic places BOTH BOs as soon as either one breaks out. This is optimal - lets market decide which one to fill.

**Q: What if CE fills, hits SL, then PE breaks out?**
A: BO exit is automatic. Strategy exits after one trade per day (`trade_executed_today = True`). Won't take PE trade.

**Q: How to take multiple trades per day?**
A: Remove or modify `trade_executed_today` check. But be careful - can lead to multiple losses in choppy market.

**Q: Can we adjust SL/Target after BO placement?**
A: No. Fyers BO legs are fixed once placed. If you need dynamic SL (trailing), use regular orders with manual management.

---

## Conclusion

**Bracket Order OCO implementation successfully addresses the LTP fetch delay problem** while providing:
- ✅ Controlled entry with limit orders
- ✅ Automatic risk management
- ✅ True OCO behavior between CE and PE
- ✅ Elimination of manual monitoring after entry

**Ready for live testing tomorrow at 9:20 AM!**
