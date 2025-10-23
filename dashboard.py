"""
Real-time Strategy Monitoring Dashboard
Simple web-based dashboard to monitor strategy performance
"""

import json
import threading
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import pytz
import logging

class StrategyMonitor:
    """Monitor strategy performance in real-time"""
    
    def __init__(self, trade_history_file: str = "trade_history.json"):
        """Initialize monitor"""
        self.trade_history_file = trade_history_file
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.current_stats = {}
        self.update_stats()
    
    def update_stats(self):
        """Update current statistics"""
        try:
            trades = []
            with open(self.trade_history_file, 'r') as f:
                for line in f:
                    if line.strip():
                        trades.append(json.loads(line))
            
            if not trades:
                self.current_stats = self.get_empty_stats()
                return
            
            # Calculate basic stats
            total_trades = len(trades)
            total_pnl = sum(trade['pnl'] for trade in trades)
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
            
            # Today's stats
            today = datetime.now(self.ist_tz).date().isoformat()
            today_trades = [t for t in trades if t['timestamp'].startswith(today)]
            today_pnl = sum(trade['pnl'] for trade in today_trades)
            today_count = len(today_trades)
            
            # Last trade
            last_trade = trades[-1] if trades else None
            
            self.current_stats = {
                'total_trades': total_trades,
                'total_pnl': round(total_pnl, 2),
                'win_rate': round(win_rate, 2),
                'today_trades': today_count,
                'today_pnl': round(today_pnl, 2),
                'last_trade': last_trade,
                'last_updated': datetime.now(self.ist_tz).strftime('%Y-%m-%d %H:%M:%S IST')
            }
            
        except FileNotFoundError:
            self.current_stats = self.get_empty_stats()
        except Exception as e:
            logging.error(f"Error updating stats: {e}")
            self.current_stats = self.get_empty_stats()
    
    def get_empty_stats(self):
        """Return empty stats structure"""
        return {
            'total_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'today_trades': 0,
            'today_pnl': 0.0,
            'last_trade': None,
            'last_updated': datetime.now(self.ist_tz).strftime('%Y-%m-%d %H:%M:%S IST')
        }
    
    def get_stats_json(self):
        """Get current stats as JSON"""
        return json.dumps(self.current_stats, indent=2)

class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for dashboard"""
    
    def __init__(self, *args, monitor=None, **kwargs):
        self.monitor = monitor
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/stats':
            # Return JSON stats
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Update stats before sending
            self.monitor.update_stats()
            self.wfile.write(self.monitor.get_stats_json().encode())
            
        elif parsed_path.path == '/' or parsed_path.path == '/dashboard':
            # Serve dashboard HTML
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html_content = self.get_dashboard_html()
            self.wfile.write(html_content.encode())
            
        else:
            # Default behavior for other paths
            super().do_GET()
    
    def get_dashboard_html(self):
        """Generate dashboard HTML"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced 5-Min Breakout Strategy Dashboard</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            padding: 30px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #eee;
        }
        .header h1 {
            color: #333;
            margin: 0;
            font-size: 2.5em;
        }
        .header p {
            color: #666;
            margin: 10px 0 0 0;
            font-size: 1.1em;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .stat-card.positive {
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        }
        .stat-card.negative {
            background: linear-gradient(135deg, #f44336 0%, #da190b 100%);
        }
        .stat-card h3 {
            margin: 0 0 10px 0;
            font-size: 1.2em;
            opacity: 0.9;
        }
        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 0;
        }
        .last-trade {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .last-trade h3 {
            margin-top: 0;
            color: #333;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .trade-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .trade-detail {
            background: white;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .trade-detail strong {
            display: block;
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 0.9em;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
        }
        .refresh-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            margin: 10px;
        }
        .refresh-btn:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Enhanced 5-Min Breakout Strategy</h1>
            <p>Real-time Performance Dashboard</p>
            <button class="refresh-btn" onclick="loadStats()">🔄 Refresh</button>
        </div>
        
        <div id="content" class="loading">
            Loading strategy data...
        </div>
    </div>

    <script>
        function loadStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    updateDashboard(data);
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('content').innerHTML = 
                        '<p style="color: red; text-align: center;">Error loading data. Please check if the strategy is running.</p>';
                });
        }
        
        function updateDashboard(stats) {
            const pnlClass = stats.total_pnl >= 0 ? 'positive' : 'negative';
            const todayPnlClass = stats.today_pnl >= 0 ? 'positive' : 'negative';
            
            let html = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>Total Trades</h3>
                        <div class="value">${stats.total_trades}</div>
                    </div>
                    <div class="stat-card ${pnlClass}">
                        <h3>Total P&L</h3>
                        <div class="value">₹${stats.total_pnl}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Win Rate</h3>
                        <div class="value">${stats.win_rate}%</div>
                    </div>
                    <div class="stat-card">
                        <h3>Today's Trades</h3>
                        <div class="value">${stats.today_trades}</div>
                    </div>
                    <div class="stat-card ${todayPnlClass}">
                        <h3>Today's P&L</h3>
                        <div class="value">₹${stats.today_pnl}</div>
                    </div>
                </div>
            `;
            
            if (stats.last_trade) {
                const trade = stats.last_trade;
                const tradeClass = trade.pnl >= 0 ? 'positive' : 'negative';
                
                html += `
                    <div class="last-trade">
                        <h3>📊 Last Trade</h3>
                        <div class="trade-details">
                            <div class="trade-detail">
                                <strong>Symbol</strong>
                                ${trade.symbol}
                            </div>
                            <div class="trade-detail">
                                <strong>Direction</strong>
                                ${trade.direction}
                            </div>
                            <div class="trade-detail">
                                <strong>Entry Price</strong>
                                ₹${trade.entry_price}
                            </div>
                            <div class="trade-detail">
                                <strong>Exit Price</strong>
                                ₹${trade.exit_price}
                            </div>
                            <div class="trade-detail">
                                <strong>P&L</strong>
                                <span style="color: ${trade.pnl >= 0 ? 'green' : 'red'}; font-weight: bold;">
                                    ₹${trade.pnl}
                                </span>
                            </div>
                            <div class="trade-detail">
                                <strong>Exit Reason</strong>
                                ${trade.exit_reason}
                            </div>
                            <div class="trade-detail">
                                <strong>Holding Time</strong>
                                ${Math.round(trade.holding_time_minutes)} min
                            </div>
                        </div>
                    </div>
                `;
            }
            
            html += `
                <div class="footer">
                    Last updated: ${stats.last_updated}<br>
                    <small>Dashboard auto-refreshes every 30 seconds</small>
                </div>
            `;
            
            document.getElementById('content').innerHTML = html;
        }
        
        // Auto-refresh every 30 seconds
        setInterval(loadStats, 30000);
        
        // Load stats on page load
        loadStats();
    </script>
</body>
</html>
        """

def start_dashboard(port: int = 8080):
    """Start the dashboard server"""
    monitor = StrategyMonitor()
    
    def handler(*args, **kwargs):
        DashboardHandler(*args, monitor=monitor, **kwargs)
    
    httpd = HTTPServer(('localhost', port), handler)
    
    print(f"🚀 Strategy Dashboard started!")
    print(f"📊 Open your browser and go to: http://localhost:{port}")
    print(f"📈 Dashboard will show real-time strategy performance")
    print(f"🔄 Press Ctrl+C to stop the dashboard")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n📴 Dashboard stopped by user")
        httpd.shutdown()

if __name__ == "__main__":
    start_dashboard()