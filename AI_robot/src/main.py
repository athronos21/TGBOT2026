#!/usr/bin/env python3
"""
Main entry point for AI Robot application

Starts the Multi-Robot Trading System with all configured robots.
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigurationManager
from src.core.master_controller import MasterController
from src.robots.data_collection.price_bot import PriceBot


def setup_logging(config: ConfigurationManager = None, level: str = "INFO") -> None:
    """Setup logging configuration"""
    if config:
        # Use the new logging system with MongoDB integration
        from src.utils.logger import setup_logging as setup_new_logging
        setup_new_logging(config.get_config())
    else:
        # Fallback to basic logging
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def load_config(config_path: str) -> ConfigurationManager:
    """Load configuration from file"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
    return ConfigurationManager(str(config_file))


def create_robots(config: ConfigurationManager) -> list:
    """Create robot instances based on configuration"""
    robots = []
    
    # Get enabled robots from config
    enabled_robots = config.get('robots.enabled', [])
    robot_configs = config.get('robots', {})
    
    for robot_id in enabled_robots:
        robot_config = robot_configs.get(robot_id, {})
        
        # Create robot based on ID
        if robot_id == 'price_bot':
            robots.append(PriceBot(robot_config))
            
        # Add more robots here as they're implemented
        # elif robot_id == 'structure_bot':
        #     robots.append(StructureBot(robot_config))
            
    return robots


async def run_system(config: ConfigurationManager, mode: str = "live") -> None:
    """
    Run the trading system.
    
    Args:
        config: Configuration manager
        mode: Execution mode (live, paper, backtest)
    """
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting AI Robot System in {mode} mode...")
    
    # Create master controller
    controller = MasterController(config)
    
    # Create and register robots
    robots = create_robots(config)
    for robot in robots:
        controller.register_robot(robot)
        
    logger.info(f"Registered {len(robots)} robots")
    
    # Run the system
    try:
        await controller.run()
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"System error: {e}")
        await controller.kill_switch()
        raise


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='AI Robot Trading System')
    parser.add_argument('--config', '-c', default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--mode', '-m', default='live',
                        choices=['live', 'paper', 'backtest'],
                        help='Execution mode')
    parser.add_argument('--log-level', '-l', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
    parser.add_argument('--swarm', '-s', default=None,
                        help='Run only robots from specified swarm')
                        
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Validate configuration
        config.validate()
        
        # Setup logging with configuration
        setup_logging(config)
        logger = logging.getLogger(__name__)
        
        # Run the system
        asyncio.run(run_system(config, args.mode))
        
    except FileNotFoundError as e:
        logger.error(str(e))
        exit(1)
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        exit(1)


if __name__ == "__main__":
    main()
