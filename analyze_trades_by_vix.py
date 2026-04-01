import pandas as pd
from datetime import datetime

# Load trade history and VIX data
trades = pd.read_csv('logs/trade_history.csv', header=None, names=[
    'datetime', 'symbol', 'side', 'entry', 'qty', 'exit_reason'
])
vix = pd.read_csv('logs/vix_levels.csv')

# Parse datetime columns
trades['datetime'] = pd.to_datetime(trades['datetime'], errors='coerce')
vix['datetime'] = pd.to_datetime(vix['Date'] + ' ' + vix['Time'], errors='coerce')

# Merge VIX with trades by closest previous VIX record
trades = trades.sort_values('datetime')
vix = vix.sort_values('datetime')
trades['vix'] = trades['datetime'].apply(
    lambda x: vix[vix['datetime'] <= x]['VIX'].iloc[-1] if not vix[vix['datetime'] <= x].empty else None
)

# Bin VIX into ranges
bins = [0, 10, 12, 15, 100]
labels = ['<10', '10-12', '12-15', '>15']
trades['vix_range'] = pd.cut(trades['vix'].astype(float), bins=bins, labels=labels, right=False)

def win_rate_func(x):
    return (x == 'TARGET').sum() / len(x) if len(x) > 0 else 0

def sl_rate_func(x):
    return (x.str.contains('SL|STOPLOSS')).sum() / len(x) if len(x) > 0 else 0

# Analyze win rate and risk/reward by VIX range
summary = trades.groupby('vix_range').agg(
    total_trades=('exit_reason', 'count'),
    win_rate=('exit_reason', win_rate_func),
    sl_rate=('exit_reason', sl_rate_func),
    avg_entry=('entry', 'mean')
)

print('Trade outcome summary by VIX range:')
print(summary)

# Suggest optimal VIX range
best_range = summary['win_rate'].idxmax()
print(f'\nBest VIX range for hitting targets: {best_range}')

# Optional: Save detailed analysis
trades.to_csv('logs/trade_vix_analysis.csv', index=False)
print('\nDetailed analysis saved to logs/trade_vix_analysis.csv')
