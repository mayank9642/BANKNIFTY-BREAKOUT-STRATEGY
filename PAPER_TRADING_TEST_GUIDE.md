# Paper Trading Test Guide for Bracket Order OCO

## Date: November 21, 2025

## Overview
The strategy now includes **paper trading simulation** for Bracket Order OCO logic. You can test the entire flow without placing real orders!

---

## How Paper Trading Simulation Works

### 1. Order Placement (Simulated)
When breakout is detected in `--paper` mode:
```python
# Creates simulated orders
ce_order_id = "PAPER_59_1732178400"  # CE order
pe_order_id = "PAPER_59_1732178400"  # PE order

# Stores in self.paper_orders dict:
{
    'PAPER_59_1732178400': {
        'symbol': 'NSE:BANKNIFTY25NOV59200CE',
        'status': 'PENDING',
        'entry_limit': 248.50,
        'placed_at': 1732178400,
        'qty': 35,
        'sl': 233.50,
        'target': 273.25
    },
    'PAPER_59_1732178401': {
        'symbol': 'NSE:BANKNIFTY25NOV59100PE',
        'status': 'PENDING',
        'entry_limit': 243.80,
        ...
    }
}
```

### 2. Order Status Monitoring (Simulated)
Every status check:
1. Fetches **real LTP** from Fyers API
2. Compares LTP with `entry_limit`
3. If `LTP >= entry_limit` → Order status changes to `'FILLED'`
4. If still below → Remains `'PENDING'`

**This tests if prices actually reach your limit orders!**

### 3. OCO Cancellation (Simulated)
When one order fills:
1. Detects `ce_status == 'FILLED'`
2. Calls `cancel_order(pe_order_id)`
3. Changes PE order status to `'CANCELLED'`
4. Logs the cancellation

**This tests your OCO logic without real cancellation API calls!**

---

## Running Paper Trading Test

### Command:
```bash
cd "c:\vs code projects\BANKNIFTY-BREAKOUT-STRATEGY"
python breakout_strategy_main.py --paper
```

### Expected Output:

```
2025-11-22 09:20:15 - INFO - Starting 5-min breakout strategy (BANKNIFTY).
2025-11-22 09:20:15 - INFO - [PAPER MODE] Using paper trading for testing
...
2025-11-22 09:20:21 - INFO - Monitoring CE NSE:BANKNIFTY25NOV59200CE for breakout above 247.50
2025-11-22 09:20:21 - INFO - Monitoring PE NSE:BANKNIFTY25NOV59100PE for breakout above 242.80

2025-11-22 09:21:05 - INFO - ======================================================================
2025-11-22 09:21:05 - INFO - BREAKOUT DETECTED! Placing OCO bracket orders...
2025-11-22 09:21:05 - INFO - ======================================================================

2025-11-22 09:21:05 - INFO - [PAPER BO] Placing bracket order for NSE:BANKNIFTY25NOV59200CE
2025-11-22 09:21:05 - INFO -    Entry Limit: 248.5 | SL: -49.70 pts (198.80) | Target: +23.75 pts (272.25)
2025-11-22 09:21:05 - INFO -    Order ID: PAPER_59_1732249265

2025-11-22 09:21:05 - INFO - [PAPER BO] Placing bracket order for NSE:BANKNIFTY25NOV59100PE
2025-11-22 09:21:05 - INFO -    Entry Limit: 243.8 | SL: -48.76 pts (195.04) | Target: +23.28 pts (267.08)
2025-11-22 09:21:05 - INFO -    Order ID: PAPER_59_1732249265

2025-11-22 09:21:05 - INFO - Both bracket orders placed successfully!
2025-11-22 09:21:05 - INFO - CE Order ID: PAPER_59_1732249265 | PE Order ID: PAPER_59_1732249265
2025-11-22 09:21:05 - INFO - Monitoring for fill... whichever fills first will cancel the other.

2025-11-22 09:21:06 - INFO - Order Status: CE=PENDING | PE=PENDING
2025-11-22 09:21:07 - INFO - Order Status: CE=PENDING | PE=PENDING
2025-11-22 09:21:08 - INFO - [PAPER FILL] Order PAPER_59_1732249265 FILLED at 248.5 (LTP: 251.20)
2025-11-22 09:21:08 - INFO -    Symbol: NSE:BANKNIFTY25NOV59200CE
2025-11-22 09:21:08 - INFO -    Position now active with SL: 198.80, Target: 272.25

2025-11-22 09:21:08 - INFO - Order Status: CE=FILLED | PE=PENDING

2025-11-22 09:21:08 - INFO - ======================================================================
2025-11-22 09:21:08 - INFO - CE ORDER FILLED! Cancelling PE order...
2025-11-22 09:21:08 - INFO - ======================================================================

2025-11-22 09:21:08 - INFO - [PAPER CANCEL] Order PAPER_59_1732249265 for NSE:BANKNIFTY25NOV59100PE cancelled (was PENDING)
2025-11-22 09:21:08 - INFO - CE position active with automatic SL and Target management

2025-11-22 09:21:08 - INFO - 
2025-11-22 09:21:08 - INFO - ================================================================================
2025-11-22 09:21:08 - INFO - PAPER TRADING SUMMARY - Bracket Order OCO Test
2025-11-22 09:21:08 - INFO - ================================================================================

2025-11-22 09:21:08 - INFO - 
2025-11-22 09:21:08 - INFO - Order ID: PAPER_59_1732249265
2025-11-22 09:21:08 - INFO -   Symbol: NSE:BANKNIFTY25NOV59200CE
2025-11-22 09:21:08 - INFO -   Status: FILLED
2025-11-22 09:21:08 - INFO -   Entry Limit: 248.5
2025-11-22 09:21:08 - INFO -   SL: 198.80 | Target: 272.25
2025-11-22 09:21:08 - INFO -   Qty: 35
2025-11-22 09:21:08 - INFO -   Filled at: 09:21:08 @ 248.50

2025-11-22 09:21:08 - INFO - 
2025-11-22 09:21:08 - INFO - Order ID: PAPER_59_1732249265
2025-11-22 09:21:08 - INFO -   Symbol: NSE:BANKNIFTY25NOV59100PE
2025-11-22 09:21:08 - INFO -   Status: CANCELLED
2025-11-22 09:21:08 - INFO -   Entry Limit: 243.8
2025-11-22 09:21:08 - INFO -   SL: 195.04 | Target: 267.08
2025-11-22 09:21:08 - INFO -   Qty: 35
2025-11-22 09:21:08 - INFO -   Cancelled (OCO - other leg filled)

2025-11-22 09:21:08 - INFO - 
2025-11-22 09:21:08 - INFO - ================================================================================
2025-11-22 09:21:08 - INFO - OCO Test Result:
2025-11-22 09:21:08 - INFO - ✅ OCO LOGIC WORKING CORRECTLY!
2025-11-22 09:21:08 - INFO -    One order filled: BANKNIFTY25NOV59200CE
2025-11-22 09:21:08 - INFO -    Other order cancelled: BANKNIFTY25NOV59100PE
2025-11-22 09:21:08 - INFO - ================================================================================
```

---

## What Gets Tested?

### ✅ Bracket Order Placement
- Both CE and PE BOs placed simultaneously
- Entry limits calculated correctly (breakout + 1)
- SL and Target calculated correctly
- Order IDs generated and tracked

### ✅ LTP-Based Fill Simulation
- Real LTP fetched from Fyers API
- Order fills when LTP >= entry_limit
- Fill price = entry_limit (no slippage simulation)
- Fill timestamp recorded

### ✅ OCO Cancellation Logic
- When CE fills → PE cancelled
- When PE fills → CE cancelled
- Only ONE order can be filled
- Other order status changes to CANCELLED

### ✅ Summary Report
- All orders listed with details
- Final status of each order
- Validation check: One filled, one cancelled = Success!

---

## Test Scenarios

### Scenario 1: CE Fills, PE Doesn't
```
Breakout: CE at 248, PE at 241
├── CE LTP reaches 248.50 → CE fills
├── PE LTP stays at 241 → PE pending
└── OCO: PE cancelled

Expected Result: ✅ One filled (CE), one cancelled (PE)
```

### Scenario 2: PE Fills, CE Doesn't
```
Breakout: PE at 243, CE at 246
├── PE LTP reaches 243.80 → PE fills
├── CE LTP stays at 247 → CE pending
└── OCO: CE cancelled

Expected Result: ✅ One filled (PE), one cancelled (CE)
```

### Scenario 3: Both Break Out, CE Fills First
```
Breakout: Both CE and PE break out
├── CE LTP reaches 248.50 at 09:21:05 → CE fills
├── PE LTP reaches 243.80 at 09:21:07 (but already cancelled)
└── OCO: PE cancelled before it could fill

Expected Result: ✅ One filled (CE), one cancelled (PE)
```

### Scenario 4: Neither Fills (Prices Reverse)
```
Breakout: CE at 248, PE at 241
├── CE LTP peaks at 248.20 (below 248.50) → CE pending
├── PE LTP peaks at 242.50 (below 243.80) → PE pending
└── Monitoring ends, both orders expire

Expected Result: ⚠️ Neither filled (prices didn't reach limits)
```

---

## Interpreting Results

### Success (✅):
```
OCO Test Result:
✅ OCO LOGIC WORKING CORRECTLY!
   One order filled: BANKNIFTY25NOV59200CE
   Other order cancelled: BANKNIFTY25NOV59100PE
```
**Meaning:** Your OCO logic is perfect! One filled, other cancelled.

### No Fill (⚠️):
```
OCO Test Result:
⚠️ Neither order filled (prices didn't reach limits)
```
**Meaning:** Breakout detected but prices didn't reach your entry limits. This is normal market behavior - not every breakout fills immediately.

### Both Filled (❌):
```
OCO Test Result:
❌ ERROR: Both orders filled! OCO cancellation may have failed
```
**Meaning:** Bug in OCO logic - both orders filled. Check cancellation timing.

---

## Key Differences from Live Mode

| Aspect | Paper Mode | Live Mode |
|--------|-----------|-----------|
| **Order Placement** | Logged only | Real API call to Fyers |
| **Order ID** | Simulated string | Real Fyers order ID |
| **Fill Simulation** | Based on LTP check | Real market fill |
| **Fill Price** | Always = entry_limit | May vary (slippage) |
| **Cancellation** | Status change only | Real API cancellation |
| **Risk** | Zero (no real money) | Real capital at risk |
| **SL/Target Management** | Not simulated | Fyers BO auto-manages |

---

## What's NOT Tested in Paper Mode?

⚠️ **The following require live testing:**

1. **Actual Order Placement API** - Paper mode doesn't call `fyers.place_order()`
2. **Order Rejection** - Real orders may get rejected (margin, limits, etc.)
3. **Fill Slippage** - Paper assumes fill at limit, real market may slip
4. **Cancellation API** - Paper mode doesn't call `fyers.cancel_order()`
5. **BO Leg Management** - SL and Target legs (Leg 2 & 3) not simulated
6. **Real Exit Execution** - When SL or Target hits in live market

---

## Troubleshooting

### Problem: "Neither order filled" every time
**Cause:** Entry limits too high, prices not reaching them  
**Fix:** Reduce entry buffer from `breakout + 1` to `breakout + 0.5`

### Problem: "Both orders filled" in paper mode
**Cause:** Bug in OCO cancellation logic  
**Fix:** Check the monitoring loop - cancellation should happen immediately after fill

### Problem: No LTP data in paper mode
**Cause:** Fyers API not connected or symbol invalid  
**Fix:** Check `access.txt` token, verify option symbols are correct

### Problem: Orders always pending
**Cause:** LTP never reaches entry limits during test window  
**Fix:** Either wait longer OR adjust entry limits closer to current price

---

## Next Steps

### Today (Paper Testing):
1. ✅ Run: `python breakout_strategy_main.py --paper`
2. ✅ Verify both BOs placed
3. ✅ Check if OCO logic works (one fills, other cancels)
4. ✅ Review summary report

### Tomorrow (Live Testing):
1. Run at 9:15 AM: `python breakout_strategy_main.py` (no --paper flag)
2. **Real orders will be placed!**
3. Monitor orderbook in Fyers app
4. Verify BO legs (SL and Target) auto-placed after fill
5. Let Fyers BO manage exits automatically

---

## Summary

**Paper trading mode now simulates:**
- ✅ Bracket order placement
- ✅ LTP-based fill detection
- ✅ OCO cancellation logic
- ✅ Order status tracking
- ✅ Summary report validation

**You can safely test the entire BO OCO flow without risking real money!**

**Check the logs for:**
- `[PAPER BO]` - Order placement
- `[PAPER FILL]` - Simulated fill
- `[PAPER CANCEL]` - OCO cancellation
- `PAPER TRADING SUMMARY` - Final report

**Ready to test! Run it and check if OCO logic works correctly.**
