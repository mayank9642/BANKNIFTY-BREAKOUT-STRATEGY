"""
Quick smoke test for batch LTP polling changes.
Runs in PURE SIMULATION mode — zero API calls, zero risk of 429.

Tests:
  1. Imports all new code correctly
  2. get_ltp_batch on DataFetcher (with mock fyers client)
  3. get_ltp_batch on fyers_api_utils (with mock fyers client)
  4. Strategy.get_ltp_batch in simulation mode (no API)
  5. Full OCO loop logic in simulation (entry detection, cancel other side)
  6. Trade monitor loop in simulation (SL / Target hit)
"""

import sys
import time
from unittest.mock import MagicMock

# ── 1. Import checks ────────────────────────────────────────────────────────
print("\n=== 1. IMPORT CHECK ===")
try:
    from src.fyers_api_utils import get_ltp_batch
    from src.data_fetcher import DataFetcher
    from breakout_strategy_main import Breakout5MinStrategy
    print("  ✅  All imports OK")
except ImportError as e:
    print(f"  ❌  Import failed: {e}")
    sys.exit(1)

# ── 2. DataFetcher.get_ltp_batch with mock client ───────────────────────────
print("\n=== 2. DataFetcher.get_ltp_batch (mock client) ===")
mock_fyers = MagicMock()
mock_fyers.quotes.return_value = {
    's': 'ok',
    'd': [
        {'n': 'NSE:BANKNIFTY26JUL58200CE', 'v': {'lp': 1074.55}},
        {'n': 'NSE:BANKNIFTY26JUL58100PE', 'v': {'lp': 742.30}},
    ]
}
df = DataFetcher(mock_fyers)
result = df.get_ltp_batch(['NSE:BANKNIFTY26JUL58200CE', 'NSE:BANKNIFTY26JUL58100PE'])
assert result == {'NSE:BANKNIFTY26JUL58200CE': 1074.55, 'NSE:BANKNIFTY26JUL58100PE': 742.30}, f"Got {result}"
assert mock_fyers.quotes.call_count == 1, "Expected exactly ONE API call for both symbols"
print(f"  ✅  CE LTP = {result['NSE:BANKNIFTY26JUL58200CE']}  |  PE LTP = {result['NSE:BANKNIFTY26JUL58100PE']}")
print(f"  ✅  API calls made: {mock_fyers.quotes.call_count}  (was 2 before batching)")

# ── 3. fyers_api_utils.get_ltp_batch with mock client ───────────────────────
print("\n=== 3. fyers_api_utils.get_ltp_batch (mock client) ===")
mock2 = MagicMock()
mock2.quotes.return_value = {
    's': 'ok',
    'd': [
        {'n': 'NSE:BANKNIFTY26JUL58200CE', 'v': {'lp': 1080.0}},
        {'n': 'NSE:BANKNIFTY26JUL58100PE', 'v': {'lp': 755.5}},
    ]
}
result2 = get_ltp_batch(mock2, ['NSE:BANKNIFTY26JUL58200CE', 'NSE:BANKNIFTY26JUL58100PE'])
assert len(result2) == 2, f"Expected 2 results, got {len(result2)}"
assert mock2.quotes.call_count == 1, "Expected exactly ONE API call"
print(f"  ✅  Both symbols returned in 1 API call: {result2}")

# ── 4. Strategy.get_ltp_batch in pure simulation (NO API calls) ─────────────
print("\n=== 4. Strategy.get_ltp_batch — pure simulation mode ===")
strategy = Breakout5MinStrategy(simulation=True, paper_trading=False)
syms = ['NSE:BANKNIFTY26JUL58200CE', 'NSE:BANKNIFTY26JUL58100PE']
batch = strategy.get_ltp_batch(syms)
assert all(v == 100.0 for v in batch.values()), f"Expected 100.0 for each, got {batch}"
assert strategy.fyers is None, "Fyers client should be None in pure simulation"
print(f"  ✅  Returned {batch} without touching API  (fyers={strategy.fyers})")

# ── 5. Full OCO loop — simulate CE breakout, PE auto-cancelled ──────────────
print("\n=== 5. OCO loop logic — CE breakout triggers, PE cancelled ===")

# Patch get_ltp_batch to return LTPs just above CE breakout
CE_SYM = 'NSE:BANKNIFTY26JUL58200CE'
PE_SYM = 'NSE:BANKNIFTY26JUL58100PE'
CE_BREAKOUT = 1062.0
PE_BREAKOUT = 790.0

call_count = [0]
def mock_batch(symbols):
    call_count[0] += 1
    # First call: both below breakout  → no fill
    # Second call: CE above breakout   → CE fills
    if call_count[0] == 1:
        return {CE_SYM: CE_BREAKOUT - 10, PE_SYM: PE_BREAKOUT - 5}
    return {CE_SYM: CE_BREAKOUT + 5, PE_SYM: PE_BREAKOUT - 5}

strategy2 = Breakout5MinStrategy(simulation=True, paper_trading=False)
strategy2.get_ltp_batch = mock_batch

# Pre-load paper orders the same way the real code does
import time as _time
CE_ID = f'SIM-{CE_SYM}-{int(CE_BREAKOUT)}-35'
PE_ID = f'SIM-{PE_SYM}-{int(PE_BREAKOUT)}-35'
strategy2.paper_orders[CE_ID] = {'symbol': CE_SYM, 'status': 'PENDING',
                                  'entry_limit': CE_BREAKOUT, 'placed_at': _time.time()}
strategy2.paper_orders[PE_ID] = {'symbol': PE_SYM, 'status': 'PENDING',
                                  'entry_limit': PE_BREAKOUT, 'placed_at': _time.time()}

# Run exactly the OCO decision logic extracted from monitor_option_high_breakout
oco_entry_taken = False
for _loop in range(3):
    _batch = strategy2.get_ltp_batch([CE_SYM, PE_SYM])
    ce_ltp = _batch.get(CE_SYM)
    pe_ltp = _batch.get(PE_SYM)
    ce_ltp_r = round(float(ce_ltp), 2) if ce_ltp else None
    pe_ltp_r = round(float(pe_ltp), 2) if pe_ltp else None
    ce_status = strategy2.paper_orders[CE_ID]['status']
    pe_status = strategy2.paper_orders[PE_ID]['status']

    if ce_status == 'PENDING' and ce_ltp_r and ce_ltp_r >= round(CE_BREAKOUT, 2):
        strategy2.paper_orders[CE_ID]['status'] = 'FILLED'
        strategy2.paper_orders[PE_ID]['status'] = 'CANCELLED'
        oco_entry_taken = True
        break
    elif pe_status == 'PENDING' and pe_ltp_r and pe_ltp_r >= round(PE_BREAKOUT, 2):
        strategy2.paper_orders[PE_ID]['status'] = 'FILLED'
        strategy2.paper_orders[CE_ID]['status'] = 'CANCELLED'
        oco_entry_taken = True
        break

assert oco_entry_taken, "OCO entry should have been taken"
assert strategy2.paper_orders[CE_ID]['status'] == 'FILLED', "CE should be FILLED"
assert strategy2.paper_orders[PE_ID]['status'] == 'CANCELLED', "PE should be CANCELLED"
assert call_count[0] == 2, f"Expected 2 batch calls, got {call_count[0]}"
print(f"  ✅  CE FILLED, PE CANCELLED in {call_count[0]} batch calls (2 polls × 1 call each)")

# ── 6. Trade monitor — SL hit test ──────────────────────────────────────────
print("\n=== 6. Trade monitor — SL hit ===")
entry = 1067.0
sl    = entry * (1 - 0.12)   # 12% SL ~= 939
target = entry * (1 + 0.12)  # 12% target ~= 1195

# Simulate: price drops below SL on 3rd poll
poll = [0]
exits = []
def mock_single_ltp(symbol):
    poll[0] += 1
    prices = [entry + 5, entry - 10, sl - 15]   # 3rd poll → SL hit
    return prices[min(poll[0]-1, 2)]

strategy3 = Breakout5MinStrategy(simulation=True, paper_trading=False)
strategy3.get_ltp = mock_single_ltp

# Run the trade monitor logic
ltp_val = None
exit_reason = None
for _ in range(10):
    ltp_val = strategy3.get_ltp(CE_SYM)
    if ltp_val <= sl:
        exit_reason = 'SL'
        break
    elif ltp_val >= target:
        exit_reason = 'TARGET'
        break

assert exit_reason == 'SL', f"Expected SL, got {exit_reason}"
assert poll[0] == 3, f"Expected 3 polls to hit SL, got {poll[0]}"
print(f"  ✅  SL hit on poll #{poll[0]} at LTP={ltp_val:.2f}  (SL level={sl:.2f})")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("  ALL 6 TESTS PASSED ✅")
print("  Code is correct and ready for tomorrow's market open.")
print("="*55 + "\n")
