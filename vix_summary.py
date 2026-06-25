"""
vix_summary.py  —  Per-VIX-Range Trade Summary
================================================
Shows every trade in each VIX bucket with running cumulative P&L.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from optimize_trailing_sl import load_all_trades, BROKERAGE, LOGS_DIR

VIX_BUCKETS = [
    ( 0.0, 13.0, "< 13  "),
    (13.0, 15.0, "13–15 "),
    (15.0, 17.0, "15–17 "),
    (17.0, 19.0, "17–19 "),
    (19.0, 21.0, "19–21 "),
    (21.0, 24.0, "21–24 "),
    (24.0, 999., "> 24  "),
]

def get_bucket(vix):
    for lo, hi, lbl in VIX_BUCKETS:
        if lo <= vix < hi:
            return lbl
    return "other "

def calc_pnl(t):
    for price in t.ticks:
        if price <= t.initial_sl:
            return (price - t.entry) * t.qty - BROKERAGE
        if price >= t.target:
            return (price - t.entry) * t.qty - BROKERAGE
    return (t.ticks[-1] - t.entry) * t.qty - BROKERAGE

def result_icon(reason):
    if reason == "TARGET": return "✅ TARGET"
    if reason == "SL":     return "❌ SL    "
    return "⏱ TIME  "

all_trades = load_all_trades(LOGS_DIR)
real_vix   = [t for t in all_trades if t.vix != 15.0]

W = 88
print(f"\n{'═'*W}")
print(f"  {'VIX-RANGE TRADE BREAKDOWN  ·  61 Real-VIX Trades':^{W-4}}")
print(f"{'═'*W}\n")

grand_total = 0.0

for lo, hi, lbl in VIX_BUCKETS:
    bucket = [t for t in real_vix if lo <= t.vix < hi]
    if not bucket:
        continue

    pnls      = [calc_pnl(t) for t in bucket]
    wins      = sum(1 for p in pnls if p > 0)
    losses    = sum(1 for p in pnls if p <= 0)
    win_rate  = wins / len(bucket) * 100
    total_pnl = sum(pnls)
    grand_total += total_pnl

    # Bucket header
    print(f"{'─'*W}")
    print(f"  VIX {lbl}  │  {len(bucket)} trades  │  "
          f"{wins}W / {losses}L  │  Win Rate: {win_rate:.0f}%  │  "
          f"Cumulative P&L: ₹{total_pnl:+,.2f}")
    print(f"{'─'*W}")
    print(f"  {'#':>2}  {'Date':>8}  {'Symbol':<26}  {'VIX':>4}  "
          f"{'Result':^10}  {'Trade P&L':>10}  {'Cumulative':>12}")
    print(f"  {'─'*2}  {'─'*8}  {'─'*26}  {'─'*4}  "
          f"{'─'*10}  {'─'*10}  {'─'*12}")

    running = 0.0
    for i, (t, pnl) in enumerate(zip(bucket, pnls), 1):
        running += pnl
        sym = t.symbol.split(":")[-1]
        print(f"  {i:>2}  {t.log_date:>8}  {sym:<26}  {t.vix:>4.1f}  "
              f"{result_icon(t.exit_reason):^10}  {pnl:>+10,.2f}  {running:>+12,.2f}")

    print()

print(f"{'═'*W}")
print(f"  GRAND TOTAL across all VIX ranges  (61 real-VIX trades):  ₹{grand_total:+,.2f}")
excl = [t for t in all_trades if t.vix == 15.0]
if excl:
    excl_pnl = sum(calc_pnl(t) for t in excl)
    print(f"  + {len(excl)} older trades (VIX not recorded in log):          ₹{excl_pnl:+,.2f}")
    print(f"  ─────────────────────────────────────────────────────────────────────")
    print(f"  TOTAL all 97 trades:                                       ₹{grand_total+excl_pnl:+,.2f}")
print(f"{'═'*W}\n")
