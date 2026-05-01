"""
Database Migrations Package

Provides migration management for the PostgreSQL database schema.
"""

from .migrations import MigrationManager, get_migration_manager

__all__ = ['MigrationManager', 'get_migration_manager']
