"""
Initial Database Schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import json


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trades table
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('trade_type', sa.String(length=8), nullable=False),
        sa.Column('entry_price', sa.DECIMAL(precision=12, scale=5), nullable=False),
        sa.Column('current_price', sa.DECIMAL(precision=12, scale=5), nullable=True),
        sa.Column('exit_price', sa.DECIMAL(precision=12, scale=5), nullable=True),
        sa.Column('lot_size', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('profit_loss', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('open_time', sa.TIMESTAMP(), nullable=False),
        sa.Column('close_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('robot_id', sa.String(length=64), nullable=True),
        sa.Column('signal_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
        sa.CheckConstraint("trade_type IN ('BUY', 'SELL')", name='chk_trades_trade_type'),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED', 'PENDING', 'CANCELLED')", name='chk_trades_status')
    )
    
    # Create signals table
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('signal_type', sa.String(length=16), nullable=False),
        sa.Column('confidence', sa.DECIMAL(precision=5, scale=4), nullable=False),
        sa.Column('strength', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('factors', sa.JSON(), nullable=True),
        sa.Column('robot_id', sa.String(length=64), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('executed', sa.Boolean(), nullable=True),
        sa.Column('trade_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("signal_type IN ('BUY', 'SELL', 'NEUTRAL')", name='chk_signals_signal_type'),
        sa.ForeignKeyConstraint(['trade_id'], ['trades.id'], )
    )
    
    # Create market_data table
    op.create_table(
        'market_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('timeframe', sa.String(length=8), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('open', sa.DECIMAL(precision=12, scale=5), nullable=False),
        sa.Column('high', sa.DECIMAL(precision=12, scale=5), nullable=False),
        sa.Column('low', sa.DECIMAL(precision=12, scale=5), nullable=False),
        sa.Column('close', sa.DECIMAL(precision=12, scale=5), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'timeframe', 'timestamp', name='uq_market_data_symbol_timeframe_timestamp')
    )
    
    # Create analysis_results table
    op.create_table(
        'analysis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('analysis_type', sa.String(length=32), nullable=False),
        sa.Column('result_data', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('robot_id', sa.String(length=64), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create performance_metrics table
    op.create_table(
        'performance_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('robot_id', sa.String(length=64), nullable=False),
        sa.Column('metric_name', sa.String(length=64), nullable=False),
        sa.Column('metric_value', sa.DECIMAL(precision=15, scale=6), nullable=False),
        sa.Column('metric_type', sa.String(length=16), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('period_start', sa.TIMESTAMP(), nullable=True),
        sa.Column('period_end', sa.TIMESTAMP(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("metric_type IN ('ratio', 'count', 'percentage', 'currency')", name='chk_metrics_metric_type')
    )
    
    # Create robot_health table
    op.create_table(
        'robot_health',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('robot_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('cpu_usage', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('memory_usage', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('last_heartbeat', sa.TIMESTAMP(), nullable=False),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('uptime_seconds', sa.BigInteger(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('robot_id', 'timestamp', name='uq_robot_health_robot_timestamp'),
        sa.CheckConstraint("status IN ('healthy', 'degraded', 'unhealthy', 'unknown')", name='chk_robot_health_status')
    )
    
    # Create indexes for market_data
    op.create_index('idx_market_data_symbol_time', 'market_data', ['symbol', 'timeframe', 'timestamp'], unique=False)
    op.create_index('idx_market_data_timestamp', 'market_data', ['timestamp'], unique=False)
    
    # Create indexes for trades
    op.create_index('idx_trades_account', 'trades', ['robot_id'], unique=False)
    op.create_index('idx_trades_symbol', 'trades', ['symbol'], unique=False)
    op.create_index('idx_trades_status', 'trades', ['status'], unique=False)
    op.create_index('idx_trades_entry_time', 'trades', ['open_time'], unique=False)
    op.create_index('idx_trades_signal', 'trades', ['signal_id'], unique=False)
    op.create_index('idx_trades_symbol_status', 'trades', ['symbol', 'status'], unique=False)
    op.create_index('idx_trades_symbol_time', 'trades', ['symbol', 'open_time'], unique=False)
    
    # Create indexes for signals
    op.create_index('idx_signals_symbol', 'signals', ['symbol'], unique=False)
    op.create_index('idx_signals_executed', 'signals', ['executed'], unique=False)
    op.create_index('idx_signals_created', 'signals', ['timestamp'], unique=False)
    op.create_index('idx_signals_robot', 'signals', ['robot_id'], unique=False)
    
    # Create indexes for analysis_results
    op.create_index('idx_analysis_symbol_time', 'analysis_results', ['symbol', 'timestamp'], unique=False)
    op.create_index('idx_analysis_type', 'analysis_results', ['analysis_type'], unique=False)
    op.create_index('idx_analysis_robot', 'analysis_results', ['robot_id'], unique=False)
    
    # Create indexes for performance_metrics
    op.create_index('idx_metrics_robot', 'performance_metrics', ['robot_id'], unique=False)
    op.create_index('idx_metrics_name', 'performance_metrics', ['metric_name'], unique=False)
    op.create_index('idx_metrics_timestamp', 'performance_metrics', ['timestamp'], unique=False)
    
    # Create indexes for robot_health
    op.create_index('idx_robot_health_id', 'robot_health', ['robot_id'], unique=False)
    op.create_index('idx_robot_health_status', 'robot_health', ['status'], unique=False)
    op.create_index('idx_robot_health_heartbeat', 'robot_health', ['last_heartbeat'], unique=False)


def downgrade() -> None:
    # Drop indexes for robot_health
    op.drop_index('idx_robot_health_heartbeat', table_name='robot_health')
    op.drop_index('idx_robot_health_status', table_name='robot_health')
    op.drop_index('idx_robot_health_id', table_name='robot_health')
    
    # Drop indexes for performance_metrics
    op.drop_index('idx_metrics_timestamp', table_name='performance_metrics')
    op.drop_index('idx_metrics_name', table_name='performance_metrics')
    op.drop_index('idx_metrics_robot', table_name='performance_metrics')
    
    # Drop indexes for analysis_results
    op.drop_index('idx_analysis_robot', table_name='analysis_results')
    op.drop_index('idx_analysis_type', table_name='analysis_results')
    op.drop_index('idx_analysis_symbol_time', table_name='analysis_results')
    
    # Drop indexes for signals
    op.drop_index('idx_signals_robot', table_name='signals')
    op.drop_index('idx_signals_created', table_name='signals')
    op.drop_index('idx_signals_executed', table_name='signals')
    op.drop_index('idx_signals_symbol', table_name='signals')
    
    # Drop indexes for trades
    op.drop_index('idx_trades_symbol_time', table_name='trades')
    op.drop_index('idx_trades_symbol_status', table_name='trades')
    op.drop_index('idx_trades_signal', table_name='trades')
    op.drop_index('idx_trades_entry_time', table_name='trades')
    op.drop_index('idx_trades_status', table_name='trades')
    op.drop_index('idx_trades_symbol', table_name='trades')
    op.drop_index('idx_trades_account', table_name='trades')
    
    # Drop indexes for market_data
    op.drop_index('idx_market_data_timestamp', table_name='market_data')
    op.drop_index('idx_market_data_symbol_time', table_name='market_data')
    
    # Drop tables
    op.drop_table('robot_health')
    op.drop_table('performance_metrics')
    op.drop_table('analysis_results')
    op.drop_table('market_data')
    op.drop_table('signals')
    op.drop_table('trades')
