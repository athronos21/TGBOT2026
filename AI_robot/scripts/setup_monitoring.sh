#!/bin/bash

# Multi-Robot Trading System - Monitoring Setup Script
# This script sets up system monitoring

set -e

echo "=========================================="
echo "Multi-Robot Trading System - Monitoring Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
LOG_DIR="/opt/trading-system/logs"
MONITORING_DIR="/opt/trading-system/monitoring"

# Create directories
mkdir -p "$LOG_DIR"
mkdir -p "$MONITORING_DIR"

# Create log rotation configuration
echo -e "${YELLOW}Setting up log rotation...${NC}"
cat > /etc/logrotate.d/trading-system <<EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 trading trading
    sharedscripts
    postrotate
        /bin/kill -USR1 $(cat /var/run/trading-system.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF

echo -e "${GREEN}Log rotation configured${NC}"

# Create monitoring script
echo -e "${YELLOW}Creating monitoring script...${NC}"
cat > "$MONITORING_DIR/health_check.sh" <<'MONITORING_SCRIPT'
#!/bin/bash

# Health check script for trading system

LOG_DIR="/opt/trading-system/logs"
PID_FILE="/var/run/trading-system.pid"
STATUS_FILE="/opt/trading-system/monitoring/status.json"

# Check if service is running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        STATUS="running"
    else
        STATUS="stopped"
    fi
else
    STATUS="stopped"
fi

# Get system stats
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' 2>/dev/null || echo "0")
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100}')
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}')

# Get trading stats
TOTAL_TRADES=$(psql -U "${DB_USER:-trading_user}" -h "${DB_HOST:-localhost}" -t -c "SELECT COUNT(*) FROM trades WHERE status = 'closed';" 2>/dev/null || echo "0")
TODAYS_TRADES=$(psql -U "${DB_USER:-trading_user}" -h "${DB_HOST:-localhost}" -t -c "SELECT COUNT(*) FROM trades WHERE status = 'closed' AND close_time >= CURRENT_DATE;" 2>/dev/null || echo "0")
TODAYS_PROFIT=$(psql -U "${DB_USER:-trading_user}" -h "${DB_HOST:-localhost}" -t -c "SELECT COALESCE(SUM(profit), 0) FROM trades WHERE status = 'closed' AND close_time >= CURRENT_DATE;" 2>/dev/null || echo "0")

# Generate status JSON
cat > "$STATUS_FILE" <<EOF
{
    "timestamp": "$(date -Iseconds)",
    "status": "$STATUS",
    "system": {
        "cpu_usage": "$CPU_USAGE",
        "memory_usage": "$MEMORY_USAGE",
        "disk_usage": "$DISK_USAGE"
    },
    "trading": {
        "total_trades": $TOTAL_TRADES,
        "todays_trades": $TODAYS_TRADES,
        "todays_profit": $TODAYS_PROFIT
    }
}
EOF

echo "Health check completed: $STATUS_FILE"
MONITORING_SCRIPT

chmod +x "$MONITORING_DIR/health_check.sh"

# Create cron job for health checks
echo -e "${YELLOW}Setting up cron jobs...${NC}"
(crontab -l 2>/dev/null | grep -v "health_check"; echo "*/5 * * * * $MONITORING_DIR/health_check.sh >> $LOG_DIR/health.log 2>&1") | crontab -

echo -e "${GREEN}Cron job configured for health checks every 5 minutes${NC}"

# Create monitoring dashboard (simple HTML)
echo -e "${YELLOW}Creating monitoring dashboard...${NC}"
cat > "$MONITORING_DIR/dashboard.html" <<'DASHBOARD'
<!DOCTYPE html>
<html>
<head>
    <title>Trading System Monitor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { text-align: center; color: #00d4ff; }
        .status { text-align: center; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .status.running { background: #00b894; }
        .status.stopped { background: #d63031; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: #2d3436; padding: 20px; border-radius: 10px; text-align: center; }
        .stat-card h3 { margin: 0 0 10px 0; color: #00d4ff; }
        .stat-card .value { font-size: 2em; font-weight: bold; }
        .system-stats { background: #2d3436; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .system-stats h3 { color: #00d4ff; margin-top: 0; }
        .system-stats div { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #636e72; }
        .system-stats div:last-child { border-bottom: none; }
        .refresh { text-align: center; margin: 20px 0; }
        .refresh button { padding: 10px 20px; font-size: 1em; cursor: pointer; background: #0984e3; color: white; border: none; border-radius: 5px; }
        .refresh button:hover { background: #74b9ff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Trading System Monitor</h1>
        <div id="status" class="status">Loading...</div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Total Trades</h3>
                <div class="value" id="total-trades">0</div>
            </div>
            <div class="stat-card">
                <h3>Today's Trades</h3>
                <div class="value" id="todays-trades">0</div>
            </div>
            <div class="stat-card">
                <h3>Today's Profit</h3>
                <div class="value" id="todays-profit">$0</div>
            </div>
        </div>
        
        <div class="system-stats">
            <h3>🖥️ System Status</h3>
            <div><span>CPU Usage</span><span id="cpu-usage">0%</span></div>
            <div><span>Memory Usage</span><span id="memory-usage">0%</span></div>
            <div><span>Disk Usage</span><span id="disk-usage">0%</span></div>
        </div>
        
        <div class="refresh">
            <button onclick="fetchStatus()">🔄 Refresh Status</button>
            <span id="last-updated">Last updated: Never</span>
        </div>
    </div>
    
    <script>
        async function fetchStatus() {
            try {
                const response = await fetch('/status.json');
                const data = await response.json();
                
                // Update status
                const statusEl = document.getElementById('status');
                statusEl.textContent = `Status: ${data.status.toUpperCase()}`;
                statusEl.className = `status ${data.status}`;
                
                // Update stats
                document.getElementById('total-trades').textContent = data.trading.total_trades;
                document.getElementById('todays-trades').textContent = data.trading.todays_trades;
                document.getElementById('todays-profit').textContent = `$${parseFloat(data.trading.todays_profit).toFixed(2)}`;
                
                // Update system stats
                document.getElementById('cpu-usage').textContent = data.system.cpu_usage;
                document.getElementById('memory-usage').textContent = data.system.memory_usage;
                document.getElementById('disk-usage').textContent = data.system.disk_usage;
                
                // Update timestamp
                document.getElementById('last-updated').textContent = `Last updated: ${new Date().toLocaleString()}`;
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }
        
        // Auto-refresh every 30 seconds
        fetchStatus();
        setInterval(fetchStatus, 30000);
    </script>
</body>
</html>
DASHBOARD

echo -e "${GREEN}Monitoring dashboard created: $MONITORING_DIR/dashboard.html${NC}"

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}Monitoring setup completed!${NC}"
echo -e "${GREEN}==========================================${NC}"

echo ""
echo "Monitoring files created:"
echo "  - Health check: $MONITORING_DIR/health_check.sh"
echo "  - Dashboard: $MONITORING_DIR/dashboard.html"
echo "  - Status file: $MONITORING_DIR/status.json"
echo ""
echo "Cron job: Health checks every 5 minutes"
echo ""
