"""
Base Robot class for the Multi-Robot Trading System

All robot implementations should inherit from this base class.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RobotState(Enum):
    """Robot state enumeration"""
    INITIALIZING = "initializing"
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RobotInfo:
    """Robot metadata"""
    id: str
    name: str
    swarm: str
    version: str = "1.0.0"
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class Robot(ABC):
    """
    Base class for all robots in the trading system.
    
    Robots are autonomous agents that perform specific tasks in the trading ecosystem.
    They communicate via a message bus and can be controlled by the MasterController.
    """
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any] = None):
        """
        Initialize the robot.
        
        Args:
            robot_info: Robot metadata
            config: Robot-specific configuration
        """
        self.info = robot_info
        self.config = config or {}
        self.state = RobotState.INITIALIZING
        self.logger = logging.getLogger(f"robot.{robot_info.id}")
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._message_bus: Optional['MessageBus'] = None
        
    @property
    def id(self) -> str:
        """Robot ID"""
        return self.info.id
        
    @property
    def name(self) -> str:
        """Robot name"""
        return self.info.name
        
    @property
    def swarm(self) -> str:
        """Robot swarm name"""
        return self.info.swarm
        
    @property
    def is_running(self) -> bool:
        """Check if robot is running"""
        return self._running
        
    @property
    def current_state(self) -> RobotState:
        """Get current robot state"""
        return self.state
        
    def set_message_bus(self, bus: 'MessageBus') -> None:
        """Set the message bus for communication"""
        self._message_bus = bus
        self.logger.debug(f"Message bus connected: {bus}")
        
    async def start(self) -> None:
        """Start the robot"""
        self.logger.info(f"Starting robot: {self.id}")
        self.state = RobotState.RUNNING
        self._running = True
        
        try:
            await self.initialize()
            self._task = asyncio.create_task(self._run_loop())
            self.logger.info(f"Robot started: {self.id}")
        except Exception as e:
            self.state = RobotState.ERROR
            self.logger.error(f"Failed to start robot: {e}")
            raise
            
    async def stop(self) -> None:
        """Stop the robot"""
        self.logger.info(f"Stopping robot: {self.id}")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
        await self.cleanup()
        self.state = RobotState.IDLE
        self.logger.info(f"Robot stopped: {self.id}")
        
    async def pause(self) -> None:
        """Pause the robot"""
        self.logger.info(f"Pausing robot: {self.id}")
        self.state = RobotState.PAUSED
        
    async def resume(self) -> None:
        """Resume the robot"""
        self.logger.info(f"Resuming robot: {self.id}")
        self.state = RobotState.RUNNING
        
    async def send_message(self, event: str, data: Any = None) -> None:
        """Send a message via the message bus"""
        if self._message_bus:
            await self._message_bus.publish(event, data)
            
    async def receive_message(self, event: str, timeout: float = 5.0) -> Any:
        """Receive a message from the message bus"""
        if self._message_bus:
            return await self._message_bus.subscribe(event, timeout)
        return None
        
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize robot resources.
        
        Override this method to set up:
        - Database connections
        - API connections
        - AI models
        - Other resources
        """
        pass
        
    @abstractmethod
    async def process(self, data: Any = None) -> Any:
        """
        Process data and perform robot's main function.
        
        Args:
            data: Input data for processing
            
        Returns:
            Processing result
        """
        pass
        
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Clean up robot resources.
        
        Override this method to release:
        - Database connections
        - API connections
        - File handles
        - Other resources
        """
        pass
        
    async def _run_loop(self) -> None:
        """Main run loop"""
        self.logger.info(f"Starting run loop for: {self.id}")
        
        while self._running:
            try:
                if self.state == RobotState.RUNNING:
                    await self._process_cycle()
                elif self.state == RobotState.PAUSED:
                    await asyncio.sleep(1.0)
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in run loop: {e}")
                self.state = RobotState.ERROR
                await asyncio.sleep(1.0)
                
        self.logger.info(f"Run loop ended for: {self.id}")
        
    async def _process_cycle(self) -> None:
        """Execute one processing cycle"""
        try:
            result = await self.process()
            self.logger.debug(f"Processed cycle for {self.id}: {result}")
        except Exception as e:
            self.logger.error(f"Error in process cycle: {e}")
            raise
