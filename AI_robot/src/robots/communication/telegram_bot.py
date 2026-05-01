"""
Telegram Bot - Telegram Communication

Telegram bot for trading system including:
- Bot setup with BotFather
- Command handling
- Trade notifications
- Status updates
- Performance stats
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from src.core.robot import Robot, RobotInfo, RobotState
from src.core.message_bus import MessageBus
from src.database.postgresql_manager import PostgreSQLManager
from src.database.mongodb_manager import MongoDBManager


class TelegramBot(Robot):
    """
    Telegram bot for trading system communication.
    
    Features:
    - Bot setup with BotFather
    - Command handling (/start, /status, /stats, /trades, etc.)
    - Trade entry/exit notifications
    - Daily summary notifications
    - Error notifications
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.bot_token = config.get('bot_token', '')
        self.chat_id = config.get('chat_id', '')
        self.verbosity = config.get('verbosity', 'normal')
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        self._bot = None
        self._update_id = 0
        
    async def initialize(self):
        """Initialize the Telegram Bot"""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        # Import telegram library
        try:
            import telegram
            self._bot = telegram.Bot(token=self.bot_token)
        except ImportError:
            self.logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return
            
        self.postgres = PostgreSQLManager(self.config.get('database', {}).get('postgresql', {}))
        self.mongodb = MongoDBManager(self.config.get('database', {}).get('mongodb', {}))
        
        await self.postgres.connect()
        self.mongodb.connect()
        
        self.mongodb.create_system_logs_collection()
        self.mongodb.create_configurations_collection()
        
        # Send startup message
        await self.send_notification("🤖 AI Trading Bot started!")
        
        self.logger.info(f"{self.robot_id} initialized successfully")
        
    async def process(self, data: Any) -> Any:
        """Process messages and handle commands"""
        if data is None:
            return None
            
        # Handle incoming messages
        if data.get('type') == 'message':
            await self._handle_message(data)
            
        # Handle trade notifications
        if data.get('type') == 'trade_signal':
            await self._notify_trade_signal(data)
            
        if data.get('type') == 'trade_executed':
            await self._notify_trade_executed(data)
            
        if data.get('type') == 'risk_rejected':
            await self._notify_risk_rejected(data)
            
        return None
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.postgres:
            await self.postgres.disconnect()
        if self.mongodb:
            self.mongodb.disconnect()
        self.logger.info(f"{self.robot_id} cleaned up")
        
    async def send_notification(self, message: str, parse_mode='Markdown'):
        """Send notification to user"""
        if not self._bot or not self.chat_id:
            return
            
        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            
    async def _handle_message(self, data: Dict):
        """Handle incoming Telegram messages"""
        text = data.get('text', '')
        command = text.split()[0].lower()
        
        if command == '/start':
            await self._handle_start(data)
        elif command == '/status':
            await self._handle_status(data)
        elif command == '/stats':
            await self._handle_stats(data)
        elif command == '/trades':
            await self._handle_trades(data)
        elif command == '/pause':
            await self._handle_pause(data)
        elif command == '/resume':
            await self._handle_resume(data)
        elif command == '/killswitch':
            await self._handle_killswitch(data)
        elif command == '/help':
            await self._handle_help(data)
            
    async def _handle_start(self, data: Dict):
        """Handle /start command"""
        message = """
🤖 *AI Trading Bot*

Welcome to your AI Trading Bot!

Available commands:
/start - Show this menu
/status - Show system status
/stats - Show performance statistics
/trades - Show open trades
/pause - Pause trading
/resume - Resume trading
/killswitch - Emergency stop
/help - Show help
        """
        await self.send_notification(message)
        
    async def _handle_status(self, data: Dict):
        """Handle /status command"""
        status = await self.get_system_status()
        message = f"""
📊 *System Status*

Status: {status.get('status', 'unknown')}
Active Robots: {status.get('active_robots', 0)}
Open Trades: {status.get('open_trades', 0)}
Account Balance: ${status.get('account_balance', 0):.2f}
Daily PnL: ${status.get('daily_pnl', 0):.2f}
        """
        await self.send_notification(message)
        
    async def _handle_stats(self, data: Dict):
        """Handle /stats command"""
        stats = await self.get_performance_stats()
        message = f"""
📈 *Performance Statistics*

Win Rate: {stats.get('win_rate', 0)*100:.1f}%
Profit Factor: {stats.get('profit_factor', 0):.2f}
Total Trades: {stats.get('total_trades', 0)}
Net Profit: ${stats.get('net_profit', 0):.2f}
Max Drawdown: {stats.get('max_drawdown', 0)*100:.1f}%
Sharpe Ratio: {stats.get('sharpe_ratio', 0):.2f}
        """
        await self.send_notification(message)
        
    async def _handle_trades(self, data: Dict):
        """Handle /trades command"""
        trades = await self.get_open_trades()
        
        if not trades:
            await self.send_notification("No open trades.")
            return
            
        message = "📊 *Open Trades*\n\n"
        for trade in trades:
            message += f"""
Symbol: {trade.get('symbol', 'N/A')}
Type: {trade.get('direction', 'N/A')}
Entry: {trade.get('entry_price', 0):.5f}
Current: {trade.get('current_price', 0):.5f}
PnL: ${trade.get('pnl', 0):.2f}
Status: {trade.get('status', 'N/A')}
            """
            
        await self.send_notification(message)
        
    async def _handle_pause(self, data: Dict):
        """Handle /pause command"""
        await self.send_message('pause_trading', {})
        await self.send_notification("⏸️ Trading paused.")
        
    async def _handle_resume(self, data: Dict):
        """Handle /resume command"""
        await self.send_message('resume_trading', {})
        await self.send_notification("▶️ Trading resumed.")
        
    async def _handle_killswitch(self, data: Dict):
        """Handle /killswitch command"""
        await self.send_message('kill_switch_activated', {})
        await self.send_notification("🚨 *KILL SWITCH ACTIVATED* - All trading stopped!")
        
    async def _handle_help(self, data: Dict):
        """Handle /help command"""
        message = """
❓ *Help*

Available commands:
/start - Show main menu
/status - Show system status
/stats - Show performance statistics
/trades - Show open trades
/close_all - Close all trades
/close_trade <id> - Close specific trade
/pause - Pause trading
/resume - Resume trading
/killswitch - Emergency stop
/help - Show this help
        """
        await self.send_notification(message)
        
    async def _notify_trade_signal(self, data: Dict):
        """Notify about trade signal"""
        signal = data.get('signal', data)
        
        if self.verbosity == 'quiet':
            return
            
        message = f"""
🔔 *New Trade Signal*

Symbol: {signal.get('symbol', 'N/A')}
Type: *{signal.get('signal_type', 'N/A')}*
Confidence: {signal.get('confidence', 0)*100:.1f}%
Entry Zone: {signal.get('entry_zone', {}).get('mid', 0):.5f}
SL: {signal.get('stop_loss', 0):.5f}
TP: {signal.get('take_profit', 0):.5f}
        """
        await self.send_notification(message)
        
    async def _notify_trade_executed(self, data: Dict):
        """Notify about trade execution"""
        trade = data.get('trade', data)
        
        message = f"""
✅ *Trade Executed*

Trade ID: {trade.get('trade_id', 'N/A')}
Symbol: {trade.get('symbol', 'N/A')}
Type: {trade.get('direction', 'N/A')}
Entry: {trade.get('execution_price', 0):.5f}
Slippage: {trade.get('slippage', 0):.2f}
        """
        await self.send_notification(message)
        
    async def _notify_risk_rejected(self, data: Dict):
        """Notify about risk rejection"""
        reason = data.get('reason', 'Unknown')
        
        message = f"""
⚠️ *Risk Rejected*

Reason: {reason}
        """
        await self.send_notification(message)
        
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            'status': 'running',
            'active_robots': 10,
            'open_trades': 2,
            'account_balance': 1050.00,
            'daily_pnl': 50.00
        }
        
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            'win_rate': 0.56,
            'profit_factor': 1.9,
            'total_trades': 100,
            'net_profit': 500.00,
            'max_drawdown': 0.075,
            'sharpe_ratio': 1.25
        }
        
    async def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get open trades"""
        return [
            {
                'symbol': 'XAUUSD',
                'direction': 'BUY',
                'entry_price': 2011.50,
                'current_price': 2015.00,
                'pnl': 35.00,
                'status': 'OPEN'
            }
        ]
