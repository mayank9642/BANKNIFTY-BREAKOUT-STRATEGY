"""
vix_filter_analysis.py  —  VIX-Based Trading Day Filter
=========================================================
Groups your real trades (parsed from strategy_*.log tick data) by India VIX
regime at the time of entry, then answers three questions:

  1. Which VIX buckets have the best / worst win rate and P&L?
  2. What happens if we AVOID trading on bad-VIX days?
  3. What happens if we trade at REDUCED QTY on uncertain-VIX days?

Three scenarios are compared:
  A — Baseline      : trade every day, full size (current behaviour)
  B — Hard Filter   : skip AVOID-rated VIX buckets entirely
  C — Smart Filter  : skip AVOID buckets + reduced qty on CAUTION buckets

Usage:
    python vix_filter_analysis.py                 # default 50% qty on CAUTION
    python vix_filter_analysis.py --caution-qty 0.6
    python vix_filter_analysis.py --caution-qty 0     # treat CAUTION = skip too
"""

import argparse
import os
import sys
import numpy as np
from collections import defaultdict

# ── Reuse trade loader from the optimizer (no code duplication) ────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from optimize_trailing_sl import load_all_trades, BROKERAGE, LOGS_DIR

# ─────────────────────────────────────────────────────────────────────────────
# India VIX regime buckets  (boundaries from historical RBI/NSE VIX research)
# ─────────────────────────────────────────────────────────────────────────────
VIX_BUCKETS = [
    ( 0.0, 13.0, "< 13  "),
    (13.0, 15.0, "13–15 "),
    (15.0, 17.0, "15–17 "),
    (17.0, 19.0, "17–19 "),
    (19.0, 21.0, "19–21 "),
    (21.0, 24.0, "21–24 "),
    (24.0, 999., "> 24  "),
]


def get_bucket(vix: float) -> str:
    for lo, hi, label in VIX_BUCKETS:
        if lo <= vix < hi:
            return label
    return "other "


def calc_pnl(trade, qty_mult: float = 1.0) -> float:
    """Replay baseline fixed-SL / fixed-Target on real ticks with qty scaling."""
    qty = trade.qty * qty_mult
    for price in trade.ticks:
        if price <= trade.initial_sl:
            return (price - trade.entry) * qty - BROKERAGE
        if price >= trade.target:
            return (price - trade.entry) * qty - BROKERAGE
    # Time exit (trade still open at end of log)
    final = trade.ticks[-1]
    return (final - trade.entry) * qty - BROKERAGE


def bucket_stats(pnls: list) -> dict:
    arr  = np.array(pnls, dtype=float)
    wins = arr[arr > 0]
    loss = arr[arr <= 0]
    return {
        "n":         int(len(arr)),
        "wins":      int(len(wins)),
        "losses":    int(len(loss)),
        "win_rate":  round(100.0 * len(wins) / max(len(arr), 1), 1),
        "total_pnl": round(float(arr.sum()),  2),
        "avg_pnl":   round(float(arr.mean()), 2),
        "avg_win":   round(float(wins.mean()), 2) if len(wins) else 0.0,
        "avg_loss":  round(float(loss.mean()), 2) if len(loss) else 0.0,
        "worst":     round(float(arr.min()),  2),
        "sharpe":    round(float(arr.mean() / (arr.std() + 1e-9)), 4),
    }


def classify(s: dict) -> str:
    """
    Signal logic:
      ✅ TRADE   : win_rate >= 58% AND avg_pnl > 0
      ⚠  CAUTION : win_rate >= 45% AND avg_pnl > -300  (or any bucket with < 5 trades)
      ❌ AVOID   : everything else
    Require at least 4 trades for a reliable signal.
    """
    if s["n"] < 4:
        return "⚠  CAUTION"   # insufficient data
    if s["win_rate"] >= 58 and s["avg_pnl"] > 0:
        return "✅ TRADE  "
    if s["win_rate"] >= 45 and s["avg_pnl"] > -300:
        return "⚠  CAUTION"
    return "❌ AVOID  "


def run(caution_qty: float = 0.5) -> None:
    # ── Load data ─────────────────────────────────────────────────────────────
    print(f"\n  Scanning {LOGS_DIR} ...")
    all_trades = load_all_trades(LOGS_DIR)

    # Trades where VIX = 15.0 (the parser's default) come from older logs that
    # didn't log VIX — exclude them from the bucket analysis to avoid polluting
    # the 15–17 bucket with ~36 trades that have no real VIX data.
    real_vix = [t for t in all_trades if t.vix != 15.0]
    default_vix = [t for t in all_trades if t.vix == 15.0]

    print(f"  {len(all_trades)} total trades  |  "
          f"{len(real_vix)} with real VIX data  |  "
          f"{len(default_vix)} excluded (older logs — VIX not recorded, default=15.0)\n")

    if not real_vix:
        sys.exit("[ERROR] No trades with real VIX data found.")

    # ── Group by bucket ────────────────────────────────────────────────────────
    groups: dict[str, list] = defaultdict(list)
    for t in real_vix:
        groups[get_bucket(t.vix)].append(t)

    # ── Per-bucket stats ───────────────────────────────────────────────────────
    W   = 122
    SEP = "═" * W
    S2  = "─" * W

    print(SEP)
    print(f"  {'VIX REGIME ANALYSIS  ·  WIN RATE & P&L BY INDIA VIX BUCKET':^{W-4}}")
    print(f"  {'Real tick data from strategy log files  ·  Fixed SL / Target  ·  Baseline qty':^{W-4}}")
    print(SEP)

    bucket_info: dict[str, dict] = {}

    print(f"\n  {'VIX':^8}  {'n':>4}  {'W':>3}  {'L':>3}  {'Win%':>5}  "
          f"{'Total P&L':>11}  {'Avg/trade':>9}  "
          f"{'Avg Win':>9}  {'Avg Loss':>9}  {'Worst':>9}  "
          f"{'Sharpe':>7}  {'Signal'}")
    print("  " + S2)

    for lo, hi, lbl in VIX_BUCKETS:
        trades_in = groups.get(lbl, [])
        if not trades_in:
            continue
        pnls = [calc_pnl(t) for t in trades_in]
        s    = bucket_stats(pnls)
        sig  = classify(s)
        bucket_info[lbl] = {**s, "signal": sig}

        print(f"  {lbl}  {s['n']:>4}  {s['wins']:>3}  {s['losses']:>3}  "
              f"{s['win_rate']:>4.1f}%  "
              f"{s['total_pnl']:>+11.2f}  {s['avg_pnl']:>+9.2f}  "
              f"{s['avg_win']:>+9.2f}  {s['avg_loss']:>+9.2f}  "
              f"{s['worst']:>+9.2f}  {s['sharpe']:>7.4f}  {sig}")

    # ── Per-trade listing by bucket ────────────────────────────────────────────
    print(f"\n{S2}")
    print(f"  {'TRADE-BY-TRADE LISTING BY VIX BUCKET':^{W-4}}")
    print(S2)

    for lo, hi, lbl in VIX_BUCKETS:
        trades_in = groups.get(lbl, [])
        if not trades_in:
            continue
        sig = bucket_info[lbl]["signal"]
        print(f"\n  ── VIX {lbl.strip()}  {sig}  ──")
        print(f"  {'Date':>8}  {'Symbol':<26}  {'Entry':>7}  {'VIX':>5}  "
              f"{'Ticks':>5}  {'Result':>7}  {'P&L':>9}")
        for t in trades_in:
            pnl = calc_pnl(t)
            print(f"  {t.log_date:>8}  {t.symbol.split(':')[-1]:<26}  "
                  f"{t.entry:>7.2f}  {t.vix:>5.1f}  "
                  f"{len(t.ticks):>5}  {t.exit_reason:>7}  {pnl:>+9.2f}")

    # ── Scenario simulation ────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  {'SCENARIO SIMULATION  ·  IMPACT OF VIX FILTER ON P&L':^{W-4}}")
    print(SEP)
    print(f"""
  Scenario A — Baseline          : trade every day, full qty (current behaviour)
  Scenario B — Hard Filter       : skip AVOID-rated VIX buckets entirely
  Scenario C — Smart Filter      : skip AVOID buckets  +  {int(caution_qty*100)}% qty on CAUTION buckets
""")

    pnl_a, pnl_b, pnl_c = [], [], []
    n_avoided_b = 0
    n_avoided_c = 0
    n_caution_c = 0

    for t in real_vix:
        lbl = get_bucket(t.vix)
        sig = bucket_info.get(lbl, {}).get("signal", "⚠  CAUTION")

        # A: always trade
        pnl_a.append(calc_pnl(t, 1.0))

        # B: skip AVOID
        if "AVOID" in sig:
            n_avoided_b += 1
        else:
            pnl_b.append(calc_pnl(t, 1.0))

        # C: skip AVOID, half qty on CAUTION
        if "AVOID" in sig:
            n_avoided_c += 1
        elif "CAUTION" in sig:
            n_caution_c += 1
            if caution_qty > 0:
                pnl_c.append(calc_pnl(t, caution_qty))
            # else skip (caution_qty=0 means avoid those too)
        else:
            pnl_c.append(calc_pnl(t, 1.0))

    sa = bucket_stats(pnl_a)
    sb = bucket_stats(pnl_b) if pnl_b else {k: 0 for k in ["n","wins","losses","win_rate","total_pnl","avg_pnl","sharpe"]}
    sc = bucket_stats(pnl_c) if pnl_c else {k: 0 for k in ["n","wins","losses","win_rate","total_pnl","avg_pnl","sharpe"]}

    rows = [
        ("Trades taken",       "n",         "{:>16}",      "{:>16}",      "{:>18}"),
        ("Win Rate",           "win_rate",  "{:>15.1f}%",  "{:>15.1f}%",  "{:>17.1f}%"),
        ("Total P&L (₹)",     "total_pnl", "{:>+15.2f}",  "{:>+15.2f}",  "{:>+17.2f}"),
        ("Avg P&L / trade (₹)","avg_pnl",  "{:>+15.2f}",  "{:>+15.2f}",  "{:>+17.2f}"),
        ("Sharpe Ratio",       "sharpe",    "{:>16.4f}",   "{:>16.4f}",   "{:>18.4f}"),
    ]

    print(f"  {'Metric':<28}  {'A — Baseline':>16}  {'B — Hard Filter':>16}  {'C — Smart Filter':>18}")
    print("  " + "─" * 84)
    for display, key, fa, fb, fc in rows:
        va, vb, vc = sa[key], sb[key], sc[key]
        print(f"  {display:<28}  {fa.format(va)}  {fb.format(vb)}  {fc.format(vc)}")

    delta_b = sb["total_pnl"] - sa["total_pnl"]
    delta_c = sc["total_pnl"] - sa["total_pnl"]

    print(f"\n  B: skipped {n_avoided_b} AVOID-bucket trade(s)")
    print(f"  C: skipped {n_avoided_c} AVOID-bucket trade(s), "
          f"used {int(caution_qty*100)}% qty on {n_caution_c} CAUTION-bucket trade(s)")
    print(f"\n  ▶  B vs Baseline: ₹{delta_b:+.2f}")
    print(f"  ▶  C vs Baseline: ₹{delta_c:+.2f}")

    # ── Final recommendation ───────────────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  {'★  RECOMMENDATION  ★':^{W-4}}")
    print(SEP)
    print()

    for lo, hi, lbl in VIX_BUCKETS:
        info = bucket_info.get(lbl)
        if not info:
            print(f"  VIX {lbl}  —  (no data)")
            continue
        sig  = info["signal"]
        rule = {
            "✅ TRADE  ": "Trade full qty, normal entry",
            "⚠  CAUTION": f"Trade at {int(caution_qty*100)}% qty  (or sit out if unsure)",
            "❌ AVOID  ": "Skip the day — do NOT enter",
        }.get(sig, "")
        print(f"  VIX {lbl}  {sig}  "
              f"Win={info['win_rate']:4.1f}%  Avg={info['avg_pnl']:+8.2f}  "
              f"n={info['n']:>3}    →  {rule}")

    print()
    # Best scenario
    best_pnl = max(sa["total_pnl"], sb["total_pnl"], sc["total_pnl"])
    if best_pnl == sc["total_pnl"]:
        best_name = "C — Smart Filter"
    elif best_pnl == sb["total_pnl"]:
        best_name = "B — Hard Filter"
    else:
        best_name = "A — Baseline (no filter helps)"

    print(f"  Best scenario on {len(real_vix)} real-VIX trades: "
          f"{best_name}  →  ₹{best_pnl:+.2f}")

    # Note about excluded trades
    if default_vix:
        excl_pnl = sum(calc_pnl(t) for t in default_vix)
        print(f"\n  Note: {len(default_vix)} older trades (VIX not logged, default=15.0) "
              f"generated ₹{excl_pnl:+.2f} and are NOT included in any scenario above.")
        print(f"  To include them, add VIX logging to the strategy for all runs.")

    print(f"\n{SEP}\n")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VIX-Based Trading Day Filter Analysis")
    parser.add_argument(
        "--caution-qty", type=float, default=0.5,
        help="Qty multiplier for CAUTION-bucket trades (default 0.5 = half size; 0 = skip)"
    )
    args = parser.parse_args()
    run(caution_qty=args.caution_qty)
