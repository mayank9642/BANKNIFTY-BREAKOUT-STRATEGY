"""
optimize_trailing_sl.py  —  BANKNIFTY Trailing SL Optimizer
=============================================================
Parses REAL tick-by-tick LTP data from strategy_*.log files (the
[PAPER STATUS] lines that are logged every ~3 seconds during a live trade),
then replays each trade against 5 trailing-SL methods and compares P&L.

No synthetic price-path reconstruction — we use the actual market ticks
your strategy observed while the trade was running.

Usage
-----
    python optimize_trailing_sl.py              # 10 most-recent trades
    python optimize_trailing_sl.py --n 20       # any number
    python optimize_trailing_sl.py --n 0        # all trades found
    python optimize_trailing_sl.py --list       # list all parseable trades
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
LOGS_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
BROKERAGE  = 50.0

# ─────────────────────────────────────────────────────────────────────────────
# 1 ▸ Data model
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TradeRecord:
    log_file:    str
    log_date:    str
    symbol:      str
    entry:       float
    initial_sl:  float
    target:      float
    qty:         float
    vix:         float
    ticks:       List[float] = field(default_factory=list)
    exit_reason: str   = ""
    exit_price:  float = 0.0

    def max_up_pct(self):
        if not self.ticks or self.entry <= 0:
            return 0.0
        return (max(self.ticks) - self.entry) / self.entry * 100.0

    def max_down_pct(self):
        if not self.ticks or self.entry <= 0:
            return 0.0
        return (min(self.ticks) - self.entry) / self.entry * 100.0


# ─────────────────────────────────────────────────────────────────────────────
# 2 ▸ Log parser
# ─────────────────────────────────────────────────────────────────────────────
RE_STATUS = re.compile(
    r'\[PAPER STATUS\]\s+(?P<sym>\S+)\s+\|\s+LTP:\s+(?P<ltp>[\d.]+)\s+\|'
    r'\s+Entry:\s+(?P<entry>[\d.]+)\s+\|\s+SL:\s+(?P<sl>[\d.]+)\s+\|'
    r'\s+Target:\s+(?P<tgt>[\d.]+)'
)
RE_EXIT = re.compile(
    r'\[PAPER EXIT\]\s+(?P<reason>Stop Loss hit|Target hit)\s+at\s+(?P<price>[\d.]+)',
    re.IGNORECASE
)
RE_VIX  = re.compile(r'\[DEBUG\]\s+VIX value used at entry:\s+(?P<vix>[\d.]+)')
RE_QTY  = re.compile(r'\[SIMULATION\].*qty=(?P<qty>\d+)')


def parse_log_file(path: str) -> List[TradeRecord]:
    """Parse one strategy log file; return a list of complete TradeRecords."""
    trades: List[TradeRecord] = []
    log_date = ""
    m = re.search(r'strategy_(\d{8})_', os.path.basename(path))
    if m:
        log_date = m.group(1)

    current_ticks: List[float] = []
    current_entry:  Optional[float] = None
    current_sl:     Optional[float] = None
    current_target: Optional[float] = None
    current_symbol: str  = ""
    current_vix:    float = 15.0
    current_qty:    float = 35.0
    in_trade = False

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                mv = RE_VIX.search(line)
                if mv:
                    current_vix = float(mv.group("vix"))

                mq = RE_QTY.search(line)
                if mq:
                    current_qty = float(mq.group("qty"))

                ms = RE_STATUS.search(line)
                if ms:
                    sym    = ms.group("sym")
                    ltp    = float(ms.group("ltp"))
                    entry  = float(ms.group("entry"))
                    sl     = float(ms.group("sl"))
                    target = float(ms.group("tgt"))

                    if not in_trade:
                        in_trade       = True
                        current_symbol = sym
                        current_entry  = entry
                        current_sl     = sl
                        current_target = target
                        current_ticks  = []

                    if sym == current_symbol and abs(entry - current_entry) < 0.5:
                        current_ticks.append(ltp)
                    else:
                        # New trade started without explicit exit — close old one
                        if in_trade and len(current_ticks) >= 3:
                            trades.append(TradeRecord(
                                log_file=os.path.basename(path), log_date=log_date,
                                symbol=current_symbol, entry=current_entry,
                                initial_sl=current_sl, target=current_target,
                                qty=current_qty, vix=current_vix,
                                ticks=list(current_ticks),
                                exit_reason="TIME", exit_price=current_ticks[-1],
                            ))
                        in_trade       = True
                        current_symbol = sym
                        current_entry  = entry
                        current_sl     = sl
                        current_target = target
                        current_ticks  = [ltp]
                    continue

                me = RE_EXIT.search(line)
                if me and in_trade:
                    reason  = "SL" if "stop loss" in me.group("reason").lower() else "TARGET"
                    exit_px = float(me.group("price"))
                    if len(current_ticks) >= 3:
                        trades.append(TradeRecord(
                            log_file=os.path.basename(path), log_date=log_date,
                            symbol=current_symbol, entry=current_entry,
                            initial_sl=current_sl, target=current_target,
                            qty=current_qty, vix=current_vix,
                            ticks=list(current_ticks),
                            exit_reason=reason, exit_price=exit_px,
                        ))
                    in_trade      = False
                    current_ticks = []
                    current_entry = None

    except Exception:
        pass

    if in_trade and current_ticks and len(current_ticks) >= 3:
        trades.append(TradeRecord(
            log_file=os.path.basename(path), log_date=log_date,
            symbol=current_symbol, entry=current_entry,
            initial_sl=current_sl, target=current_target,
            qty=current_qty, vix=current_vix,
            ticks=list(current_ticks),
            exit_reason="TIME", exit_price=current_ticks[-1],
        ))

    return trades


def load_all_trades(logs_dir: str) -> List[TradeRecord]:
    """Scan every strategy_*.log and return all parsed trades, newest first."""
    all_trades: List[TradeRecord] = []
    files = sorted(
        [f for f in os.listdir(logs_dir) if f.startswith("strategy_") and f.endswith(".log")],
        reverse=True
    )
    for fname in files:
        path = os.path.join(logs_dir, fname)
        if os.path.getsize(path) < 500:
            continue
        all_trades.extend(parse_log_file(path))
    return all_trades


# ─────────────────────────────────────────────────────────────────────────────
# 3 ▸ Trailing-SL simulation on real ticks
# ─────────────────────────────────────────────────────────────────────────────
def simulate_trade(ticks, entry, initial_sl, target, qty, method, params):
    t_sl = initial_sl
    peak = entry

    if method == "baseline":
        for price in ticks:
            if price <= t_sl:
                return price, "SL",     (price - entry) * qty - BROKERAGE
            if price >= target:
                return price, "TARGET", (price - entry) * qty - BROKERAGE
        final = ticks[-1]
        return final, "TIME", (final - entry) * qty - BROKERAGE

    elif method == "pct_trail":
        act_pct   = float(params["activate_pct"])
        trail_pct = float(params["trail_pct"])
        activated = False
        for price in ticks:
            peak = max(peak, price)
            if not activated and price >= entry * (1.0 + act_pct):
                activated = True
            if activated:
                candidate = peak * (1.0 - trail_pct)
                if candidate > t_sl:
                    t_sl = candidate
            if price <= t_sl:
                return price, "TRAIL_SL", (price - entry) * qty - BROKERAGE
            if price >= target:
                return price, "TARGET",   (price - entry) * qty - BROKERAGE
        final = ticks[-1]
        return final, "TIME", (final - entry) * qty - BROKERAGE

    elif method == "step_lock":
        steps = params["steps"]
        for price in ticks:
            peak = max(peak, price)
            gain_pct = (price - entry) / entry * 100.0
            for thresh, lock_at in sorted(steps, reverse=True):
                if gain_pct >= thresh:
                    new_sl = entry * (1.0 + lock_at / 100.0)
                    if new_sl > t_sl:
                        t_sl = new_sl
                    break
            if price <= t_sl:
                locked_exit = max(price, t_sl)
                return locked_exit, "STEP_SL", (locked_exit - entry) * qty - BROKERAGE
            if price >= target:
                return price, "TARGET", (price - entry) * qty - BROKERAGE
        final = ticks[-1]
        return final, "TIME", (final - entry) * qty - BROKERAGE

    elif method == "vix_adapt":
        act_pct = float(params.get("activate_pct", 0.02))
        vix     = float(params.get("vix", 15.0))
        if   vix < 12.0: trail_pct = 0.025
        elif vix < 18.0: trail_pct = 0.040
        else:             trail_pct = 0.055
        activated = False
        for price in ticks:
            peak = max(peak, price)
            if not activated and price >= entry * (1.0 + act_pct):
                activated = True
            if activated:
                candidate = peak * (1.0 - trail_pct)
                if candidate > t_sl:
                    t_sl = candidate
            if price <= t_sl:
                return price, "TRAIL_SL", (price - entry) * qty - BROKERAGE
            if price >= target:
                return price, "TARGET",   (price - entry) * qty - BROKERAGE
        final = ticks[-1]
        return final, "TIME", (final - entry) * qty - BROKERAGE

    elif method == "breakeven":
        # Move SL to breakeven+buffer once price moves act_pct above entry.
        # After that, hold — no further trailing. Let target do the work.
        act_pct    = float(params.get("activate_pct", 0.04))
        be_buffer  = float(params.get("be_buffer",    0.005))   # 0.5% above entry
        be_locked  = False
        for price in ticks:
            if not be_locked and price >= entry * (1.0 + act_pct):
                be_locked = True
                new_sl = entry * (1.0 + be_buffer)
                if new_sl > t_sl:
                    t_sl = new_sl
            if price <= t_sl:
                return price, "BE_SL", (price - entry) * qty - BROKERAGE
            if price >= target:
                return price, "TARGET", (price - entry) * qty - BROKERAGE
        final = ticks[-1]
        return final, "TIME", (final - entry) * qty - BROKERAGE

    elif method == "wide_trail":
        # Wide trail: activate at +5%, trail 8% below running peak.
        # Designed to ride the full trend without firing on normal 3-4% oscillations.
        act_pct   = float(params.get("activate_pct", 0.05))
        trail_pct = float(params.get("trail_pct",    0.08))
        activated = False
        for price in ticks:
            peak = max(peak, price)
            if not activated and price >= entry * (1.0 + act_pct):
                activated = True
            if activated:
                candidate = peak * (1.0 - trail_pct)
                if candidate > t_sl:
                    t_sl = candidate
            if price <= t_sl:
                return price, "TRAIL_SL", (price - entry) * qty - BROKERAGE
            if price >= target:
                return price, "TARGET",   (price - entry) * qty - BROKERAGE
        final = ticks[-1]
        return final, "TIME", (final - entry) * qty - BROKERAGE

    raise ValueError(f"Unknown method: {method!r}")


# ─────────────────────────────────────────────────────────────────────────────
# 4 ▸ Methods & aggregation
# ─────────────────────────────────────────────────────────────────────────────
METHODS = [
    ("M0 Baseline (fixed SL)",       "baseline",    {}),
    ("M1 PctTrail act=2% trl=3%",    "pct_trail",   {"activate_pct": 0.02, "trail_pct": 0.03}),
    ("M2 PctTrail act=3% trl=4%",    "pct_trail",   {"activate_pct": 0.03, "trail_pct": 0.04}),
    ("M3 Step-Lock staircase",        "step_lock",   {"steps": [(2.5, 0.0), (5.0, 2.5), (7.5, 5.0)]}),
    ("M4 VIX-Adaptive",              "vix_adapt",   {"activate_pct": 0.02}),
    ("M5 Breakeven @+4%",            "breakeven",   {"activate_pct": 0.04, "be_buffer": 0.005}),
    ("M6 WideTrail act=5% trl=8%",   "wide_trail",  {"activate_pct": 0.05, "trail_pct": 0.08}),
]


def aggregate(pnls):
    arr  = np.array(pnls, dtype=float)
    wins = arr[arr > 0]
    loss = arr[arr <= 0]
    return {
        "Total P&L": round(float(arr.sum()),  2),
        "Win Rate":  round(100.0 * len(wins) / max(len(arr), 1), 1),
        "Wins":      int(len(wins)),
        "Losses":    int(len(loss)),
        "Avg Win":   round(float(wins.mean()),  2) if len(wins) else 0.0,
        "Avg Loss":  round(float(loss.mean()),  2) if len(loss) else 0.0,
        "Worst":     round(float(arr.min()),    2),
        "Sharpe":    round(float(arr.mean() / (arr.std() + 1e-9)), 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5 ▸ Main
# ─────────────────────────────────────────────────────────────────────────────
def run_analysis(n_trades: int = 10, list_only: bool = False, no_trace: bool = False):
    print(f"\n  Scanning {LOGS_DIR} ...")
    all_trades = load_all_trades(LOGS_DIR)

    if not all_trades:
        sys.exit("[ERROR] No trades with tick data found in logs/")

    print(f"  Found {len(all_trades)} complete trade(s) with real tick data.\n")

    if list_only:
        print(f"  {'#':>4}  {'Date':>8}  {'Symbol':<30}  {'Entry':>8}  "
              f"{'Ticks':>5}  {'MaxUp%':>7}  {'MaxDn%':>7}  {'Result':>7}  {'VIX':>5}")
        print("  " + "─" * 90)
        for i, t in enumerate(all_trades, 1):
            print(f"  {i:>4}  {t.log_date:>8}  {t.symbol.split(':')[-1]:<30}  "
                  f"{t.entry:>8.2f}  {len(t.ticks):>5}  "
                  f"{t.max_up_pct():>7.2f}  {t.max_down_pct():>7.2f}  "
                  f"{t.exit_reason:>7}  {t.vix:>5.1f}")
        return

    selected = all_trades if n_trades == 0 else all_trades[:n_trades]
    n = len(selected)

    method_pnls = {lbl: [] for lbl, _, _ in METHODS}
    rows = []

    for i, trade in enumerate(selected, 1):
        record = {
            "no":     i,
            "date":   trade.log_date,
            "symbol": trade.symbol.split(":")[-1][:26],
            "entry":  trade.entry,
            "isl":    trade.initial_sl,
            "target": trade.target,
            "ticks":  len(trade.ticks),
            "max_up": round(trade.max_up_pct(), 2),
            "max_dn": round(trade.max_down_pct(), 2),
            "vix":    trade.vix,
            "actual": trade.exit_reason,
        }

        _, _, actual_pnl = simulate_trade(
            trade.ticks, trade.entry, trade.initial_sl,
            trade.target, trade.qty, "baseline", {}
        )
        record["actual_pnl"] = round(actual_pnl, 2)

        for label, mtype, mparams in METHODS:
            params = {**mparams, "vix": trade.vix} if mtype == "vix_adapt" else mparams
            _, sim_reason, sim_pnl = simulate_trade(
                trade.ticks, trade.entry, trade.initial_sl,
                trade.target, trade.qty, mtype, params
            )
            record[label] = (sim_reason, round(sim_pnl, 2))
            method_pnls[label].append(sim_pnl)

        rows.append(record)

    stats = {lbl: aggregate(method_pnls[lbl]) for lbl, _, _ in METHODS}

    # ── Report ────────────────────────────────────────────────────────────────
    W   = 136
    SEP = "═" * W
    S2  = "─" * W

    print(SEP)
    print(f"  {'BANKNIFTY BREAKOUT — TRAILING SL OPTIMIZER  (REAL TICK DATA FROM LOG FILES)':^{W-4}}")
    print(f"  {f'Analysing {n} trades  |  Each tick = actual LTP polled every ~3 sec by the strategy':^{W-4}}")
    print(SEP)

    # Trade summary
    print(f"\n  {'#':>3}  {'Date':>8}  {'Symbol':<28}  {'Entry':>8}  "
          f"{'SL':>8}  {'Target':>8}  {'Ticks':>5}  "
          f"{'MaxUp%':>7}  {'MaxDn%':>7}  {'VIX':>5}  {'Result':>7}  {'Act P&L':>10}")
    print("  " + "─" * 115)
    for r in rows:
        print(f"  {r['no']:>3}  {r['date']:>8}  {r['symbol']:<28}  "
              f"{r['entry']:>8.2f}  {r['isl']:>8.2f}  {r['target']:>8.2f}  "
              f"{r['ticks']:>5}  {r['max_up']:>7.2f}  {r['max_dn']:>7.2f}  "
              f"{r['vix']:>5.1f}  {r['actual']:>7}  {r['actual_pnl']:>10.2f}")

    # P&L comparison
    CW = 19
    print(f"\n{S2}")
    print(f"  {'PER-TRADE NET P&L  (real ticks, each trailing-SL method)':^{W-4}}")
    print(S2)
    hdr = f"  {'#':>3}  {'Symbol':<24}  {'Actual':>9}"
    for lbl, _, _ in METHODS:
        hdr += f"  {lbl[:CW]:>{CW}}"
    print(hdr)
    print("  " + "─" * (len(hdr) - 2))

    for r in rows:
        line = f"  {r['no']:>3}  {r['symbol']:<24}  {r['actual_pnl']:>9.2f}"
        for lbl, _, _ in METHODS:
            sim_reason, sim_pnl = r[lbl]
            delta = sim_pnl - r["actual_pnl"]
            tag   = " +" if delta > 100 else (" -" if delta < -50 else "  ")
            line += f"  {sim_pnl:>{CW-2}.2f}{tag}"
        print(line)
    print(f"\n  Note:  + = beats actual by >₹100  |  - = worse by >₹50")

    # Tick trace — show exactly when M1 trailing SL activates / fires
    if not no_trace:
        print(f"\n{S2}")
        print(f"  {'TICK-BY-TICK TRACE  (M1: activate=2%, trail=3%)':^{W-4}}")
        print(S2)

        for r in rows:
            trade   = selected[r["no"] - 1]
            lbl_m1  = METHODS[1][0]
            sim_reason_m1, sim_pnl_m1 = r[lbl_m1]
            sim_reason_bl, sim_pnl_bl = r[METHODS[0][0]]
            delta   = sim_pnl_m1 - sim_pnl_bl

            mark = "★" if delta > 100 else " "
            print(f"\n {mark} #{r['no']}  {r['symbol']}  [{r['date']}]")
            print(f"   Entry={r['entry']:.2f}  InitSL={r['isl']:.2f}  "
                  f"Target={r['target']:.2f}  VIX={r['vix']:.1f}  "
                  f"SL-distance={(r['entry']-r['isl'])/r['entry']*100:.1f}%  "
                  f"Ticks={r['ticks']}")

            act_pct   = 0.02
            trail_pct = 0.03
            t_sl_m1   = trade.initial_sl
            peak      = trade.entry
            activated = False
            events    = []

            for j, price in enumerate(trade.ticks):
                peak = max(peak, price)
                if not activated and price >= trade.entry * (1 + act_pct):
                    activated = True
                    events.append(
                        f"   tick {j+1:>4}  LTP={price:>8.2f}  "
                        f"[TRAIL ACTIVATED]  peak={peak:.2f} → SL set to {peak*(1-trail_pct):.2f}"
                    )
                if activated:
                    candidate = peak * (1 - trail_pct)
                    if candidate > t_sl_m1:
                        old_sl   = t_sl_m1
                        t_sl_m1  = candidate
                        events.append(
                            f"   tick {j+1:>4}  LTP={price:>8.2f}  "
                            f"[SL RATCHET]  {old_sl:.2f} → {t_sl_m1:.2f}  (peak={peak:.2f})"
                        )
                if price <= t_sl_m1:
                    events.append(
                        f"   tick {j+1:>4}  LTP={price:>8.2f}  "
                        f"[TRAIL EXIT]  SL={t_sl_m1:.2f}  P&L={sim_pnl_m1:+.2f}"
                    )
                    break
                if price >= trade.target:
                    events.append(
                        f"   tick {j+1:>4}  LTP={price:>8.2f}  [TARGET HIT]"
                    )
                    break
            else:
                events.append(
                    f"   tick {len(trade.ticks):>4}  LTP={trade.ticks[-1]:>8.2f}  "
                    f"[TIME EXIT]  P&L={sim_pnl_m1:+.2f}"
                )

            if not activated:
                act_level = trade.entry * (1 + act_pct)
                peak_seen = max(trade.ticks)
                print(f"   ⚠  Trail NEVER activated — "
                      f"price needed to reach {act_level:.2f} (+{act_pct*100:.0f}%), "
                      f"but peaked at {peak_seen:.2f} "
                      f"({(peak_seen-trade.entry)/trade.entry*100:+.2f}%)")
            else:
                for ev in events[:12]:
                    print(ev)
                if len(events) > 12:
                    print(f"   ... ({len(events)-12} more events)")

            print(f"   Baseline → {sim_reason_bl:8}  ₹{sim_pnl_bl:>+9.2f}  "
                  f"|  M1 Trail → {sim_reason_m1:8}  ₹{sim_pnl_m1:>+9.2f}  "
                  f"|  Δ = ₹{delta:>+9.2f}")

    # Aggregate metrics
    CW2 = 22
    print(f"\n{SEP}")
    print(f"  {'AGGREGATE METRICS':^{W-4}}")
    print(SEP)
    mhdr = f"  {'Metric':<24}"
    for lbl, _, _ in METHODS:
        mhdr += f"  {lbl[:CW2]:>{CW2}}"
    print(mhdr)
    print("  " + "─" * (24 + (CW2+2)*len(METHODS)))

    for display, key, fmt in [
        ("Total P&L (₹)",    "Total P&L", "{:>+12.2f}"),
        ("Win Rate",          "Win Rate",  "{:>11.1f}%"),
        ("Wins / Losses",     "Wins",      ""),
        ("Avg Win (₹)",       "Avg Win",   "{:>+12.2f}"),
        ("Avg Loss (₹)",      "Avg Loss",  "{:>+12.2f}"),
        ("Worst Trade (₹)",   "Worst",     "{:>+12.2f}"),
        ("Sharpe Ratio",      "Sharpe",    "{:>12.4f}"),
    ]:
        row = f"  {display:<24}"
        for lbl, _, _ in METHODS:
            s = stats[lbl]
            if key == "Wins":
                val = f"{s['Wins']}W / {s['Losses']}L"
                row += f"  {val:>{CW2}}"
            else:
                row += f"  {fmt.format(s[key]):>{CW2}}"
        print(row)

    bl_lbl = METHODS[0][0]
    print("  " + "─" * (24 + (CW2+2)*len(METHODS)))
    drow = f"  {'Δ Total vs Baseline':<24}"
    for lbl, _, _ in METHODS:
        d = stats[lbl]["Total P&L"] - stats[bl_lbl]["Total P&L"]
        drow += f"  {f'{d:>+12.2f}':>{CW2}}"
    print(drow)

    # Recommendation
    best_lbl = max(stats, key=lambda m: stats[m]["Total P&L"])
    best     = stats[best_lbl]
    base     = stats[bl_lbl]
    delta_t  = best["Total P&L"] - base["Total P&L"]

    print(f"\n{SEP}")
    print(f"  {'★  RECOMMENDATION  ★':^{W-4}}")
    print(SEP)
    print(f"""
  Best method     : {best_lbl}
  Total P&L       : ₹{best['Total P&L']:>+10.2f}   (Baseline: ₹{base['Total P&L']:>+10.2f})
  Improvement     : ₹{delta_t:>+10.2f}   ({delta_t / max(abs(base['Total P&L']), 1) * 100:>+.1f}%)
  Win Rate        : {best['Win Rate']:.1f}%   ({best['Wins']}W / {best['Losses']}L)
  Avg Win         : ₹{best['Avg Win']:>+10.2f}
  Avg Loss        : ₹{best['Avg Loss']:>+10.2f}
  Worst Trade     : ₹{best['Worst']:>+10.2f}
  Sharpe Ratio    : {best['Sharpe']:.4f}
""")

    # Engagement stats for M1
    engaged = sum(1 for r in rows if r[METHODS[1][0]][1] != r[METHODS[0][0]][1])
    saved   = sum(r[METHODS[1][0]][1] - r[METHODS[0][0]][1] for r in rows)
    print(f"  M1 engagement across {n} trades:")
    print(f"    Trades where trail SL changed the exit : {engaged}/{n}")
    print(f"    Total P&L difference from trail SL     : ₹{saved:>+.2f}")
    if engaged == 0:
        print(f"""
  ⚠  The trailing SL NEVER activated on any of these {n} trades.
  This is a critical insight from the REAL tick data:

     Your option prices at entry barely moved UP before reversing.
     The max-up seen across these trades was very small — the 2%
     activation threshold was never crossed.

  What this tells us:
    1. These are fast SL-hits (options gap down quickly after entry).
    2. A trailing SL that requires a +2% bounce cannot help.

  Actionable alternatives to investigate:
    A) LOWER activation — try 0.5% or even 0% (trail from tick 1).
       Run:  python optimize_trailing_sl.py --n 30
       (The script will re-run with tighter parameters if --tune flag added)
    B) TIME-BASED exit — cut the loss after X minutes regardless.
    C) BREAKEVEN-FAST — move SL to entry the moment price is up ₹50.
""")
    else:
        print()

    # Code snippet
    print(SEP)
    print(f"  {'IMPLEMENTATION SNIPPET':^{W-4}}")
    print(SEP)
    print("""
  Replace the 'trailing_sl' block in monitor_filled_paper_order():

  TRAIL_ACTIVATE_PCT = 0.02   # +2% from entry before trailing kicks in
  TRAIL_PCT          = 0.03   # trail 3% below running peak

  trailing_sl = sl            # start with the original SL
  peak        = entry_price
  activated   = False

  while trade_active:
      ltp = self.get_ltp(symbol)
      if ltp is None:
          time.sleep(0.25); continue

      if ltp > peak:
          peak = ltp

      if not activated and ltp >= entry_price * (1 + TRAIL_ACTIVATE_PCT):
          activated = True
          self.log_info(f"[TRAIL] Activated. peak={peak:.2f} SL→{peak*(1-TRAIL_PCT):.2f}")

      if activated:
          candidate = peak * (1 - TRAIL_PCT)
          if candidate > trailing_sl:
              self.log_info(f"[TRAIL] SL {trailing_sl:.2f} → {candidate:.2f}")
              trailing_sl = candidate

      if ltp <= trailing_sl:
          exit_reason = "TRAIL_SL"; break
      if ltp >= target:
          exit_reason = "TARGET";   break
""")
    print(SEP + "\n")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BANKNIFTY Trailing SL Optimizer (real log data)")
    parser.add_argument("--n",       type=int, default=10,
                        help="Number of most-recent trades to analyse (0 = all)")
    parser.add_argument("--list",    action="store_true",
                        help="List all parseable trades and exit")
    parser.add_argument("--no-trace", action="store_true",
                        help="Skip tick-by-tick trace (faster for large runs)")
    args = parser.parse_args()
    run_analysis(n_trades=args.n, list_only=args.list, no_trace=args.no_trace)
