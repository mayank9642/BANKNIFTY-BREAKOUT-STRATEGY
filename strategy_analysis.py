"""
Strategy Analysis and Backtesting Utilities
Tools for analyzing strategy performance and backtesting
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
import logging

class StrategyAnalyzer:
    """Class for analyzing strategy performance"""
    
    def __init__(self, trade_history_file: str = "trade_history.json"):
        """Initialize analyzer with trade history file"""
        self.trade_history_file = trade_history_file
        self.trades_df = self.load_trade_history()
        self.ist_tz = pytz.timezone('Asia/Kolkata')
    
    def load_trade_history(self) -> pd.DataFrame:
        """Load trade history from JSON file"""
        try:
            trades = []
            with open(self.trade_history_file, 'r') as f:
                for line in f:
                    if line.strip():
                        trades.append(json.loads(line))
            
            if not trades:
                print("No trade history found.")
                return pd.DataFrame()
            
            df = pd.DataFrame(trades)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            df['entry_time'] = df['timestamp'].dt.time
            
            return df
            
        except FileNotFoundError:
            print(f"Trade history file {self.trade_history_file} not found.")
            return pd.DataFrame()
        except Exception as e:
            print(f"Error loading trade history: {e}")
            return pd.DataFrame()
    
    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive strategy metrics"""
        if self.trades_df.empty:
            return {}
        
        df = self.trades_df
        
        # Basic metrics
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0])
        losing_trades = len(df[df['pnl'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl = df['pnl'].sum()
        avg_pnl = df['pnl'].mean()
        avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df[df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        # Risk metrics
        max_win = df['pnl'].max()
        max_loss = df['pnl'].min()
        
        # Calculate drawdown
        cumulative_pnl = df['pnl'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        max_drawdown = drawdown.min()
        
        # Profit factor
        gross_profit = df[df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Risk-reward ratio
        risk_reward_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Daily metrics
        daily_pnl = df.groupby('date')['pnl'].sum()
        profitable_days = len(daily_pnl[daily_pnl > 0])
        total_days = len(daily_pnl)
        daily_win_rate = (profitable_days / total_days) * 100 if total_days > 0 else 0
        
        # Exit reason analysis
        exit_reasons = df['exit_reason'].value_counts()
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_win': max_win,
            'max_loss': max_loss,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'risk_reward_ratio': risk_reward_ratio,
            'daily_win_rate': daily_win_rate,
            'profitable_days': profitable_days,
            'total_trading_days': total_days,
            'exit_reasons': exit_reasons.to_dict(),
            'daily_pnl': daily_pnl
        }
    
    def print_performance_report(self):
        """Print detailed performance report"""
        metrics = self.calculate_metrics()
        
        if not metrics:
            print("No trade data available for analysis.")
            return
        
        print("=" * 60)
        print("ENHANCED 5-MINUTE BREAKOUT STRATEGY - PERFORMANCE REPORT")
        print("=" * 60)
        
        print(f"\n📊 TRADE STATISTICS")
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Winning Trades: {metrics['winning_trades']}")
        print(f"Losing Trades: {metrics['losing_trades']}")
        print(f"Win Rate: {metrics['win_rate']:.2f}%")
        
        print(f"\n💰 P&L ANALYSIS")
        print(f"Total P&L: ₹{metrics['total_pnl']:.2f}")
        print(f"Average P&L per Trade: ₹{metrics['avg_pnl']:.2f}")
        print(f"Average Win: ₹{metrics['avg_win']:.2f}")
        print(f"Average Loss: ₹{metrics['avg_loss']:.2f}")
        print(f"Largest Win: ₹{metrics['max_win']:.2f}")
        print(f"Largest Loss: ₹{metrics['max_loss']:.2f}")
        
        print(f"\n📈 RISK METRICS")
        print(f"Maximum Drawdown: ₹{metrics['max_drawdown']:.2f}")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"Risk-Reward Ratio: {metrics['risk_reward_ratio']:.2f}")
        
        print(f"\n📅 DAILY PERFORMANCE")
        print(f"Total Trading Days: {metrics['total_trading_days']}")
        print(f"Profitable Days: {metrics['profitable_days']}")
        print(f"Daily Win Rate: {metrics['daily_win_rate']:.2f}%")
        
        print(f"\n🚪 EXIT ANALYSIS")
        for reason, count in metrics['exit_reasons'].items():
            percentage = (count / metrics['total_trades']) * 100
            print(f"{reason}: {count} trades ({percentage:.1f}%)")
        
        print("=" * 60)
    
    def plot_performance_charts(self):
        """Generate performance visualization charts"""
        if self.trades_df.empty:
            print("No data available for plotting.")
            return
        
        # Set up the plotting style
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Enhanced 5-Minute Breakout Strategy - Performance Analysis', fontsize=16)
        
        # 1. Cumulative P&L Chart
        cumulative_pnl = self.trades_df['pnl'].cumsum()
        axes[0, 0].plot(range(len(cumulative_pnl)), cumulative_pnl, 'b-', linewidth=2)
        axes[0, 0].set_title('Cumulative P&L')
        axes[0, 0].set_xlabel('Trade Number')
        axes[0, 0].set_ylabel('Cumulative P&L (₹)')
        axes[0, 0].grid(True, alpha=0.3)
        
        # Add zero line
        axes[0, 0].axhline(y=0, color='r', linestyle='--', alpha=0.5)
        
        # 2. Daily P&L Distribution
        daily_pnl = self.trades_df.groupby('date')['pnl'].sum()
        axes[0, 1].hist(daily_pnl, bins=20, alpha=0.7, color='green', edgecolor='black')
        axes[0, 1].set_title('Daily P&L Distribution')
        axes[0, 1].set_xlabel('Daily P&L (₹)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].axvline(x=0, color='r', linestyle='--', alpha=0.5)
        
        # 3. Win/Loss Analysis
        win_loss_data = ['Win' if pnl > 0 else 'Loss' for pnl in self.trades_df['pnl']]
        win_loss_counts = pd.Series(win_loss_data).value_counts()
        
        colors = ['green', 'red']
        wedges, texts, autotexts = axes[1, 0].pie(win_loss_counts.values, 
                                                  labels=win_loss_counts.index,
                                                  autopct='%1.1f%%',
                                                  colors=colors,
                                                  startangle=90)
        axes[1, 0].set_title('Win/Loss Distribution')
        
        # 4. Exit Reason Analysis
        exit_reasons = self.trades_df['exit_reason'].value_counts()
        axes[1, 1].bar(range(len(exit_reasons)), exit_reasons.values)
        axes[1, 1].set_title('Exit Reasons')
        axes[1, 1].set_xlabel('Exit Reason')
        axes[1, 1].set_ylabel('Number of Trades')
        axes[1, 1].set_xticks(range(len(exit_reasons)))
        axes[1, 1].set_xticklabels(exit_reasons.index, rotation=45)
        
        plt.tight_layout()
        plt.show()
    
    def analyze_time_patterns(self):
        """Analyze performance patterns by time"""
        if self.trades_df.empty:
            return
        
        print("\n⏰ TIME PATTERN ANALYSIS")
        print("-" * 40)
        
        # Convert entry_time to hour for analysis
        self.trades_df['entry_hour'] = pd.to_datetime(self.trades_df['entry_time'], format='%H:%M:%S').dt.hour
        
        # Hourly performance
        hourly_stats = self.trades_df.groupby('entry_hour').agg({
            'pnl': ['count', 'mean', 'sum'],
            'symbol': 'count'
        }).round(2)
        
        print("Hourly Performance:")
        print(hourly_stats)
        
        # Best and worst hours
        hourly_pnl = self.trades_df.groupby('entry_hour')['pnl'].sum()
        best_hour = hourly_pnl.idxmax()
        worst_hour = hourly_pnl.idxmin()
        
        print(f"\nBest Trading Hour: {best_hour}:00 (₹{hourly_pnl[best_hour]:.2f})")
        print(f"Worst Trading Hour: {worst_hour}:00 (₹{hourly_pnl[worst_hour]:.2f})")
    
    def analyze_holding_periods(self):
        """Analyze performance by holding period"""
        if self.trades_df.empty:
            return
        
        print("\n⏱️ HOLDING PERIOD ANALYSIS")
        print("-" * 40)
        
        # Create holding period buckets
        holding_periods = self.trades_df['holding_time_minutes']
        
        # Define buckets
        bins = [0, 30, 60, 90, 120, float('inf')]
        labels = ['0-30 min', '30-60 min', '60-90 min', '90-120 min', '120+ min']
        
        self.trades_df['holding_bucket'] = pd.cut(holding_periods, bins=bins, labels=labels, right=False)
        
        bucket_stats = self.trades_df.groupby('holding_bucket').agg({
            'pnl': ['count', 'mean', 'sum'],
            'symbol': 'count'
        }).round(2)
        
        print("Performance by Holding Period:")
        print(bucket_stats)
        
        # Average holding time for wins vs losses
        avg_hold_wins = self.trades_df[self.trades_df['pnl'] > 0]['holding_time_minutes'].mean()
        avg_hold_losses = self.trades_df[self.trades_df['pnl'] < 0]['holding_time_minutes'].mean()
        
        print(f"\nAverage Holding Time:")
        print(f"Winning Trades: {avg_hold_wins:.1f} minutes")
        print(f"Losing Trades: {avg_hold_losses:.1f} minutes")

class BacktestEngine:
    """Simple backtesting engine for the strategy"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize backtesting engine"""
        pass  # Implementation for historical backtesting would go here
    
    def run_backtest(self, start_date: str, end_date: str):
        """Run backtest for specified date range"""
        print("Backtesting functionality to be implemented...")
        print("This would require historical options data which is typically expensive.")
        print("Consider using paper trading or forward testing instead.")

def main():
    """Main analysis function"""
    print("Strategy Analysis Tool")
    print("=" * 30)
    
    analyzer = StrategyAnalyzer()
    
    if analyzer.trades_df.empty:
        print("No trade history found. Run the strategy first to generate trade data.")
        return
    
    # Generate performance report
    analyzer.print_performance_report()
    
    # Analyze time patterns
    analyzer.analyze_time_patterns()
    
    # Analyze holding periods
    analyzer.analyze_holding_periods()
    
    # Generate charts
    try:
        analyzer.plot_performance_charts()
    except Exception as e:
        print(f"Could not generate charts: {e}")
        print("Install matplotlib and seaborn for chart generation.")

if __name__ == "__main__":
    main()