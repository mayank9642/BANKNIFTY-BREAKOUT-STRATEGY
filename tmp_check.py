from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('ms', 'd:/5min banknifty/monthly_summary.py')
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)
# load raw
csvp = Path('logs/trade_status_history.csv')
if not csvp.exists():
    csvp = Path('logs/trade_history.csv')
df = ms.load_trades(csvp)
print('Loaded columns:', df.columns.tolist())
if 'PnL' not in df.columns:
    paired = ms.pair_entry_exit_trades(df)
    print('Paired columns:', paired.columns.tolist())
    print(paired.head().to_string())
else:
    print('PnL exists, first rows:')
    print(df.head().to_string())
