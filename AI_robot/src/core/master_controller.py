"""
Master Controller for the Multi-Robot Trading System

Coordinates all robots, manages their lifecycle, and handles system-wide events.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from src.core.robot import Robot, RobotInfo, RobotState
from src.core.message_bus import MessageBus
from src.config.config_manager import ConfigurationManager


class MasterController:
    """
    Central controller that manages all robots in the trading system.
    
    Responsibilities:
    - Robot lifecycle management (start, stop, pause, resume)
    - Message bus coordination
    - System health monitoring
    - Configuration management
    - Emergency shutdown (kill switch)
    """
    
    def __init__(self, config: ConfigurationManager):
        """
        Initialize the master controller.
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.message_bus = MessageBus()
        self._robots: Dict[str, Robot] = {}
        self._running = False
        self._start_time: Optional[datetime] = None
        self._shutdown_requested = False
        
    @property
    def is_running(self) -> bool:
        """Check if controller is running"""
        return self._running
        
    @property
    def robot_count(self) -> int:
        """Get total number of registered robots"""
        return len(self._robots)
        
    def register_robot(self, robot: Robot) -> None:
        """
        Register a robot with the controller.
        
        Args:
            robot: Robot instance to register
        """
        robot.set_message_bus(self.message_bus)
        self._robots[robot.id] = robot
        self.logger.info(f"Registered robot: {robot.id} ({robot.name})")
        
    def get_robot(self, robot_id: str) -> Optional[Robot]:
        """
        Get a robot by ID.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            Robot instance or None if not found
        """
        return self._robots.get(robot_id)
        
    def get_robots_by_swarm(self, swarm: str) -> List[Robot]:
        """
        Get all robots in a specific swarm.
        
        Args:
            swarm: Swarm name
            
        Returns:
            List of robots in the swarm
        """
        return [r for r in self._robots.values() if r.swarm == swarm]
        
    def get_all_robots(self) -> List[Robot]:
        """Get all registered robots"""
        return list(self._robots.values())
        
    async def start(self) -> None:
        """Start all registered robots"""
        self.logger.info("Starting Master Controller...")
        self._running = True
        self._start_time = datetime.now()
        
        # Start message bus
        await self.message_bus.start()
        
        # Start all robots
        for robot_id, robot in self._robots.items():
            try:
                await robot.start()
            except Exception as e:
                self.logger.error(f"Failed to start robot {robot_id}: {e}")
                
        self.logger.info("Master Controller started successfully")
        
    async def stop(self) -> None:
        """Stop all robots and shutdown"""
        self.logger.info("Stopping Master Controller...")
        self._shutdown_requested = True
        
        # Stop all robots
        for robot_id, robot in self._robots.items():
            try:
                await robot.stop()
            except Exception as e:
                self.logger.error(f"Failed to stop robot {robot_id}: {e}")
                
        # Stop message bus
        await self.message_bus.stop()
        
        self._running = False
        self.logger.info("Master Controller stopped")
        
    async def pause_all(self) -> None:
        """Pause all robots"""
        self.logger.info("Pausing all robots...")
        for robot in self._robots.values():
            try:
                await robot.pause()
            except Exception as e:
                self.logger.error(f"Failed to pause robot {robot.id}: {e}")
                
    async def resume_all(self) -> None:
        """Resume all robots"""
        self.logger.info("Resuming all robots...")
        for robot in self._robots.values():
            try:
                await robot.resume()
            except Exception as e:
                self.logger.error(f"Failed to resume robot {robot.id}: {e}")
                
    async def restart_robot(self, robot_id: str) -> bool:
        """
        Restart a specific robot.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            True if successful
        """
        robot = self._robots.get(robot_id)
        if not robot:
            self.logger.error(f"Robot not found: {robot_id}")
            return False
            
        self.logger.info(f"Restarting robot: {robot_id}")
        await robot.stop()
        await robot.start()
        return True
        
    async def kill_switch(self) -> None:
        """
        Emergency shutdown - stop all trading and close all positions.
        
        This is the most severe action and should only be used in emergencies.
        """
        self.logger.critical("KILL SWITCH ACTIVATED!")
        self._shutdown_requested = True
        
        # Pause all robots first
        await self.pause_all()
        
        # Then stop completely
        await self.stop()
        
        self.logger.critical("All systems stopped due to kill switch")
        
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all robots.
        
        Returns:
            Health status dictionary
        """
        health = {
            "timestamp": datetime.now().isoformat(),
            "running": self._running,
            "robot_count": self.robot_count,
            "robots": {}
        }
        
        for robot_id, robot in self._robots.items():
            health["robots"][robot_id] = {
                "name": robot.name,
                "swarm": robot.swarm,
                "state": robot.current_state.value,
                "is_running": robot.is_running
            }
            
        return health
        
    async def run(self) -> None:
        """
        Run the master controller (blocking call).
        
        This method starts all robots and waits for shutdown signal.
        """
        await self.start()
        
        try:
            while self._running and not self._shutdown_requested:
                # Periodic health check
                if self.config.get('safety.enabled', True):
                    health = await self.health_check()
                    self._check_safety_limits(health)
                    
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
            
    def _check_safety_limits(self, health: Dict[str, Any]) -> None:
        """
        Check if safety limits are exceeded.
        
        Args:
            health: Health status dictionary
        """
        # Check for too many errors
        error_count = sum(
            1 for r in health["robots"].values()
            if r["state"] == RobotState.ERROR.value
        )
        
        if error_count > self.config.get('safety.max_errors', 3):
            self.logger.warning(f"Too many errors ({error_count}), triggering kill switch")
            asyncio.create_task(self.kill_switch())
