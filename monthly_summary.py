"""
monthly_summary.py
Aggregate `logs/trade_status_history.csv` into monthly performance metrics and plots.
Saves: logs/monthly_summary_<YYYYMM>.csv and logs/monthly_summary_<YYYYMM>.png
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

LOGS_DIR = Path('logs')
CSV_FILE = LOGS_DIR / 'trade_status_history.csv'
# Fallback for older installations that used trade_history.csv
FALLBACK_CSV = LOGS_DIR / 'trade_history.csv'


def load_trades(csv_path: Path) -> pd.DataFrame:
    # Accept either the requested CSV, or fallback to the legacy trade_history.csv
    if not csv_path.exists():
        if FALLBACK_CSV.exists():
            csv_path = FALLBACK_CSV
        else:
            raise FileNotFoundError(f"CSV not found: {csv_path}")
    # Try reading with header; many legacy logs do not include a header and are simple rows.
    # If pandas mistakenly uses the first data row as header (common with headerless logs),
    # detect that and re-read with header=None.
    df = pd.read_csv(csv_path)
    # Detect if first column name looks like a datetime (i.e., pandas used first row as header)
    first_col = str(df.columns[0])
    # crude datetime detection: starts with 4-digit year and '-'
    if len(first_col) >= 4 and first_col[:4].isdigit() and '-' in first_col:
        # Re-read as headerless
        df = pd.read_csv(csv_path, header=None)
    # Detect format: if expected columns exist (PnL etc), coerce directly
    if 'PnL' in df.columns or 'Entry' in df.columns:
        # Try to coerce common numeric columns
        for col in ['Entry', 'LTP', 'SL', 'Trailing SL', 'Target', 'PnL', 'MaxUp (\u20b9)', 'MaxUp (%)', 'MaxDown (\u20b9)']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        # Ensure Time column as datetime
        if 'Time' in df.columns:
            df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
        return df

    # At this point assume legacy format (no header): Time,Symbol,Side,Price,Qty,Reason
    if df.shape[1] >= 6 and df.columns.tolist() == [0,1,2,3,4,5]:
        df = df.iloc[:, :6]
        df.columns = ['Time', 'Symbol', 'Side', 'Price', 'Qty', 'Reason']
        df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce')
        return df

    # If unknown format, try best-effort parse
    if 'Time' in df.columns:
        df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
    return df


def pair_entry_exit_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Convert row-level logs (entry/exit) into trade-level rows with PnL.
    Expected input for legacy logs: columns ['Time','Symbol','Side','Price','Qty','Reason']
    Returns DataFrame with columns: ['EntryTime','ExitTime','Symbol','EntryPrice','ExitPrice','Qty','PnL','ExitReason']
    """
    records = []
    if 'Time' not in df.columns or 'Symbol' not in df.columns:
        return pd.DataFrame(records)
    df_sorted = df.sort_values('Time').reset_index(drop=True)
    open_trades = {}  # symbol -> list of open trade dicts
    for _, row in df_sorted.iterrows():
        sym = row['Symbol']
        side = str(row.get('Side', '')).upper()
        reason = str(row.get('Reason', '')).upper()
        price = float(row.get('Price', np.nan)) if not pd.isna(row.get('Price')) else None
        qty = int(row.get('Qty', 0)) if not pd.isna(row.get('Qty')) else 0
        t = row['Time']

        # Treat these as opens
        open_reasons = {'BREAKOUT', 'ENTRY'}
        exit_reasons = {'TARGET', 'STOPLOSS', 'MAX_HOLDING', 'TIME_EXIT', 'SELL', 'EXIT'}

        if reason in open_reasons or (side == 'BUY' and reason == ''):
            open_trades.setdefault(sym, []).append({'EntryTime': t, 'EntryPrice': price, 'Qty': qty, 'Side': side})
            continue

        # If this row looks like an exit, match to last open
        if reason in exit_reasons or side == 'SELL':
            opens = open_trades.get(sym, [])
            if not opens:
                # No open trade to match; skip
                continue
            open_rec = opens.pop()  # LIFO
            entry_price = open_rec['EntryPrice']
            entry_time = open_rec['EntryTime']
            entry_qty = open_rec['Qty'] or qty
            # Compute PnL assuming entry was BUY and exit is SELL
            pnl = None
            if entry_price is not None and price is not None:
                if open_rec.get('Side', 'BUY') == 'BUY':
                    pnl = (price - entry_price) * entry_qty
                else:
                    pnl = (entry_price - price) * entry_qty
            records.append({'EntryTime': entry_time, 'ExitTime': t, 'Symbol': sym, 'EntryPrice': entry_price, 'ExitPrice': price, 'Qty': entry_qty, 'PnL': pnl, 'ExitReason': reason})

    return pd.DataFrame(records)


def monthly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df['PnL'].notna()]
    df['YearMonth'] = df['Time'].dt.to_period('M')
    grouped = df.groupby('YearMonth')
    rows = []
    for ym, g in grouped:
        total_pnl = g['PnL'].sum()
        trades = len(g)
        wins = len(g[g['PnL'] > 0])
        win_rate = wins / trades if trades > 0 else 0
        avg_pnl = g['PnL'].mean()
        max_drawdown = g['PnL'].cumsum().min()
        rows.append({'YearMonth': str(ym), 'Trades': trades, 'TotalPnL': total_pnl, 'WinRate': win_rate, 'AvgPnL': avg_pnl, 'MaxDrawdown': max_drawdown})
    return pd.DataFrame(rows)


def plot_metrics(df: pd.DataFrame, out_png: Path):
    # df expected with Time and PnL
    df = df.sort_values('Time')
    df['Equity'] = df['PnL'].cumsum()
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [2, 1]})
    # Equity curve
    axes[0].plot(df['Time'], df['Equity'], label='Equity', color='tab:blue')
    axes[0].set_ylabel('Cumulative PnL')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    # Monthly PnL bar
    df['YearMonth'] = df['Time'].dt.to_period('M')
    monthly = df.groupby('YearMonth')['PnL'].sum()
    monthly.index = monthly.index.astype(str)
    axes[1].bar(monthly.index, monthly.values, color='tab:green')
    axes[1].set_ylabel('Monthly PnL')
    axes[1].set_xticklabels(monthly.index, rotation=45)
    axes[1].grid(True, alpha=0.3)
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)


def save_summary_csv(metrics_df: pd.DataFrame, out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(out_csv, index=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate monthly performance summary from trade_status_history.csv')
    parser.add_argument('--csv', type=str, default=str(CSV_FILE), help='Path to trade_status_history.csv')
    parser.add_argument('--out', type=str, default='logs', help='Output directory')
    args = parser.parse_args()

    df = load_trades(Path(args.csv))
    if df.empty:
        print('No trades found in CSV.')
        exit(0)

    # If the loaded dataframe doesn't include PnL (legacy row-level logs), try to pair entry/exit rows
    if 'PnL' not in df.columns:
        paired = pair_entry_exit_trades(df)
        if paired.empty:
            print('No paired trades found in CSV.')
            exit(0)
        # Use ExitTime as the canonical Time for the trade row
        paired = paired.rename(columns={'ExitTime': 'Time', 'EntryPrice': 'Entry', 'ExitPrice': 'LTP'})
        # Ensure Time is datetime
        paired['Time'] = pd.to_datetime(paired['Time'], errors='coerce')
        df_trades = paired[['Time', 'Symbol', 'Entry', 'LTP', 'Qty', 'PnL', 'ExitReason']].copy()
    else:
        df_trades = df.copy()

    metrics = monthly_metrics(df_trades)
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = Path(args.out)
    out_csv = out_dir / f'monthly_summary_{now}.csv'
    out_png = out_dir / f'monthly_summary_{now}.png'
    save_summary_csv(metrics, out_csv)
    plot_metrics(df_trades, out_png)
    print(f'Saved summary CSV: {out_csv}\nSaved summary PNG: {out_png}')
