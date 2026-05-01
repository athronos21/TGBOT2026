"""
Database Migration System

Manages database schema migrations using Alembic.
Provides commands for creating, applying, and managing migrations.
"""

import os
import sys
import subprocess
from typing import Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Manages database migrations using Alembic.
    
    Provides high-level commands for:
    - Creating new migrations
    - Upgrading database schema
    - Downgrading database schema
    - Checking migration status
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize migration manager.
        
        Args:
            config_path: Path to alembic.ini (defaults to src/database/alembic.ini)
        """
        self.base_dir = Path(__file__).parent.parent
        self.config_path = config_path or str(self.base_dir / 'database' / 'alembic.ini')
        self.migrations_dir = self.base_dir / 'database' / 'migrations'
        
    def _run_alembic(self, command: str, *args) -> tuple[bool, str]:
        """
        Run an alembic command.
        
        Args:
            command: Alembic command (upgrade, downgrade, etc.)
            *args: Additional arguments
            
        Returns:
            Tuple of (success, output)
        """
        try:
            cmd = ['alembic', command] + list(args)
            result = subprocess.run(
                cmd,
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"Alembic {command}: Success")
                return True, result.stdout
            else:
                logger.error(f"Alembic {command}: Failed")
                logger.error(result.stderr)
                return False, result.stderr
                
        except FileNotFoundError:
            logger.error("Alembic not found. Please install: pip install alembic")
            return False, "Alembic not installed"
        except Exception as e:
            logger.error(f"Error running alembic {command}: {e}")
            return False, str(e)
    
    def upgrade(self, revision: str = "head") -> bool:
        """
        Upgrade database to specified revision.
        
        Args:
            revision: Target revision (default: head)
            
        Returns:
            True if successful
        """
        success, output = self._run_alembic('upgrade', revision)
        if success:
            logger.info(f"Database upgraded to {revision}")
        return success
    
    def downgrade(self, revision: str = "base") -> bool:
        """
        Downgrade database to specified revision.
        
        Args:
            revision: Target revision (default: base - full downgrade)
            
        Returns:
            True if successful
        """
        success, output = self._run_alembic('downgrade', revision)
        if success:
            logger.info(f"Database downgraded to {revision}")
        return success
    
    def status(self, verbose: bool = False) -> tuple[bool, str]:
        """
        Check migration status.
        
        Args:
            verbose: Show detailed status
            
        Returns:
            Tuple of (success, status_output)
        """
        args = ['-v'] if verbose else []
        success, output = self._run_alembic('current', *args)
        return success, output
    
    def create(self, name: str, autogenerate: bool = False) -> bool:
        """
        Create a new migration.
        
        Args:
            name: Migration name
            autogenerate: Auto-generate from model changes
            
        Returns:
            True if successful
        """
        args = []
        if autogenerate:
            args.extend(['--autogenerate', '-m', name])
        else:
            args.append('-m', name)
        
        success, output = self._run_alembic('revision', *args)
        if success:
            logger.info(f"Migration created: {name}")
        return success
    
    def heads(self) -> tuple[bool, str]:
        """
        Show current heads (latest migrations).
        
        Returns:
            Tuple of (success, output)
        """
        success, output = self._run_alembic('heads')
        return success, output
    
    def history(self, rev_range: str = None) -> tuple[bool, str]:
        """
        Show migration history.
        
        Args:
            rev_range: Revision range (e.g., 'base:head')
            
        Returns:
            Tuple of (success, output)
        """
        args = [rev_range] if rev_range else []
        success, output = self._run_alembic('history', *args)
        return success, output


def get_migration_manager() -> MigrationManager:
    """
    Get a configured migration manager instance.
    
    Returns:
        MigrationManager instance
    """
    return MigrationManager()


# Command-line interface
def main():
    """Main entry point for migration commands."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Migration Manager')
    parser.add_argument('command', choices=['upgrade', 'downgrade', 'status', 'create', 'heads', 'history'],
                       help='Migration command to run')
    parser.add_argument('revision', nargs='?', default='head',
                       help='Target revision (default: head)')
    parser.add_argument('--name', '-n', help='Migration name (for create command)')
    parser.add_argument('--autogenerate', '-a', action='store_true',
                       help='Auto-generate migration from model changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    manager = get_migration_manager()
    
    if args.command == 'upgrade':
        success = manager.upgrade(args.revision)
    elif args.command == 'downgrade':
        success = manager.downgrade(args.revision)
    elif args.command == 'status':
        success, output = manager.status(args.verbose)
        print(output)
        return 0 if success else 1
    elif args.command == 'create':
        if not args.name:
            print("Error: --name is required for create command")
            return 1
        success = manager.create(args.name, args.autogenerate)
    elif args.command == 'heads':
        success, output = manager.heads()
        print(output)
        return 0 if success else 1
    elif args.command == 'history':
        success, output = manager.history(args.revision)
        print(output)
        return 0 if success else 1
    else:
        print(f"Unknown command: {args.command}")
        return 1
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
