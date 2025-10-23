# Enhanced 5-Minute Breakout Strategy

A sophisticated algorithmic trading system designed for trading NIFTY and BANKNIFTY options on the Indian stock market. The strategy leverages the first 5-minute candle pattern to identify potential breakout opportunities with comprehensive risk management.

## 🚀 Features

- **Advanced Breakout Detection**: Uses first 5-minute candle analysis
- **Multiple Confirmation Filters**: Volume and momentum confirmations
- **Sophisticated Risk Management**: ATR-based adaptive stop loss, trailing stops
- **Partial Exit Strategy**: Progressive profit booking
- **Real-time Monitoring**: WebSocket-based live price tracking
- **Comprehensive Analytics**: Performance analysis and reporting
- **Web Dashboard**: Real-time monitoring interface

## 📋 Prerequisites

- Python 3.8 or higher
- Valid Fyers trading account and API credentials
- Internet connection for real-time data

## 🛠️ Installation

1. **Clone or download** this repository to your local machine

2. **Navigate to the project directory**:
   ```bash
   cd "d:\5min banknifty"
   ```

3. **Create and activate virtual environment** (already done):
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

4. **Install required packages** (already done):
   ```bash
   pip install pandas numpy matplotlib seaborn yfinance requests websocket-client python-dateutil fyers-apiv3 pytz pyyaml
   ```

## ⚙️ Configuration

1. **Update API Credentials**: Edit `config.yaml` and replace the placeholder values:
   ```yaml
   api:
     client_id: "YOUR_FYERS_CLIENT_ID"
     secret_key: "YOUR_FYERS_SECRET_KEY"
   ```

2. **Customize Strategy Parameters**: Modify other settings in `config.yaml` as needed:
   - Trading quantities
   - Risk management parameters
   - Partial exit settings
   - Market timing

## 🔐 Authentication

Before running the strategy, you need to authenticate with Fyers API:

```bash
python authenticate.py
```

This will:
1. Open your browser for Fyers login
2. Generate and save your access token
3. Verify the authentication

## 🎯 Usage

### Running the Strategy

```bash
python breakout_strategy.py
```

The strategy will:
1. Wait for market open (9:15 AM IST)
2. Capture the first 5-minute candle (9:15-9:20 AM)
3. Calculate breakout levels for both NIFTY and BANKNIFTY options
4. Monitor for breakout conditions with multiple confirmations
5. Execute trades automatically with risk management

### Monitoring Performance

**Real-time Dashboard**:
```bash
python dashboard.py
```
Open http://localhost:8080 in your browser for live monitoring.

**Performance Analysis**:
```bash
python strategy_analysis.py
```
Generates detailed performance reports and charts.

## 📊 Strategy Logic

### 1. First Candle Analysis (9:15-9:20 AM)
- Captures OHLC data of the first 5-minute candle
- Identifies ATM (At-The-Money) CE and PE options
- Calculates breakout levels with configurable buffer

### 2. Entry Conditions
- **Price Breakout**: Option price exceeds breakout level
- **Volume Confirmation**: Current volume > 120% of average volume
- **Momentum Confirmation**: Price shows directional consistency
- **Risk Limits**: Daily loss and trade count limits

### 3. Risk Management
- **Adaptive Stop Loss**: ATR-based calculation (0.5 × ATR)
- **Fixed Stop Loss**: Configurable points-based fallback
- **Target Setting**: 2:1 risk-reward ratio by default
- **Maximum Holding**: 120 minutes default limit

### 4. Exit Strategy
- **Partial Exits**: Progressive profit booking at time intervals
- **Trailing Stop**: Activates at 50% of target, trails by 25%
- **Time Exit**: Automatic exit after maximum holding period
- **Stop Loss/Target**: Primary exit conditions

## 📈 Key Configuration Parameters

### Risk Management
```yaml
risk_management:
  stop_loss_points: 30      # Points for stop loss
  target_points: 60         # Points for target (2:1 RR)
  breakout_buffer: 2        # Buffer above breakout level
  max_holding_period_minutes: 120
  use_atr_stop_loss: true   # Adaptive stop loss
  atr_multiplier: 0.5       # ATR multiplier
```

### Trading Quantities
```yaml
symbols:
  nifty:
    quantity: 25            # Lots per trade
  banknifty:
    quantity: 15            # Lots per trade
```

### Partial Exits
```yaml
partial_exits:
  enabled: true
  exits:
    - time_minutes: 30      # First exit at 30 min
      min_profit_percentage: 25
      exit_percentage: 30   # Exit 30% of position
    - time_minutes: 60      # Second exit at 60 min
      min_profit_percentage: 40
      exit_percentage: 40   # Exit 40% of remaining
```

## 📁 File Structure

```
d:\5min banknifty\
│
├── config.yaml              # Strategy configuration
├── breakout_strategy.py     # Main strategy implementation
├── authenticate.py          # Fyers API authentication
├── strategy_analysis.py     # Performance analysis tools
├── dashboard.py            # Real-time monitoring dashboard
├── trade_history.json      # Trade records (generated)
├── trades.log              # Strategy logs (generated)
└── README.md               # This file
```

## 🔧 Customization

### Adding New Symbols
Add symbols to `config.yaml`:
```yaml
symbols:
  your_symbol:
    index_symbol: "NSE:YOUR_INDEX-INDEX"
    step_size: 50
    enabled: true
    quantity: 25
```

### Modifying Entry Filters
Adjust confirmation requirements:
```yaml
entry_filters:
  volume_confirmation: true
  volume_threshold: 1.2      # 120% of average
  momentum_confirmation: true
  momentum_periods: 3
```

### Risk Parameters
Tune risk management:
```yaml
risk_management:
  stop_loss_points: 30       # Adjust stop loss
  target_points: 60          # Adjust target
  breakout_buffer: 2         # Breakout sensitivity
```

## 📊 Performance Monitoring

### Trade Logs
All trades are logged to:
- `trade_history.json`: Structured trade data
- `trades.log`: Detailed execution logs

### Analysis Reports
Run `python strategy_analysis.py` to get:
- Win rate and P&L statistics
- Risk metrics (drawdown, profit factor)
- Time pattern analysis
- Holding period analysis
- Performance charts

### Real-time Dashboard
Access `http://localhost:8080` for:
- Live P&L tracking
- Trade statistics
- Last trade details
- Auto-refreshing display

## ⚠️ Risk Disclaimer

**IMPORTANT**: This is a sophisticated trading algorithm that involves substantial financial risk. 

- **Paper Trading**: Test thoroughly in simulation mode first
- **Risk Management**: Never risk more than you can afford to lose
- **Market Conditions**: Past performance doesn't guarantee future results
- **Supervision**: Monitor the strategy during trading hours
- **Compliance**: Ensure compliance with your broker's terms and local regulations

## 🐛 Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Re-run `python authenticate.py`
   - Check API credentials in `config.yaml`
   - Verify Fyers account status

2. **Data Issues**:
   - Check internet connection
   - Verify symbol formats
   - Review Fyers API status

3. **No Trades Executed**:
   - Check market hours
   - Verify breakout conditions
   - Review entry filters
   - Check daily limits

4. **Performance Issues**:
   - Reduce API call frequency
   - Check system resources
   - Optimize configuration

### Debug Mode
Enable detailed logging:
```yaml
logging:
  level: "DEBUG"
  console_output: true
```

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review configuration settings
3. Examine log files for errors
4. Test in simulation mode first

## 📝 License

This software is provided for educational and research purposes. Use at your own risk. The authors are not responsible for any financial losses incurred while using this software.

---

**Happy Trading!** 📈🚀

*Remember: The best strategy is one that you understand completely and have tested thoroughly.*