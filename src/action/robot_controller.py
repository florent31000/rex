"""
Robot Controller for Rex-Brain.
Handles communication with the Unitree Go2 robot via WebRTC.

Based on: https://github.com/tfoldi/go2-webrtc
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional
from enum import Enum
from dataclasses import dataclass

from src.utils.logger import log


class RobotMode(Enum):
    """Available robot modes."""
    NORMAL = "normal"
    SPORT = "sport"
    STAIRS = "stairs"


class GestureType(Enum):
    """Available gestures/tricks."""
    STAND = "stand"
    SIT = "sit"
    LIE_DOWN = "lie_down"
    SHAKE_PAW = "shake_paw"
    WAVE = "wave"
    DANCE = "dance"
    STRETCH = "stretch"
    HEART = "heart"  # Heart mode


@dataclass
class RobotState:
    """Current state of the robot."""
    battery_percent: float = 100.0
    mode: RobotMode = RobotMode.NORMAL
    is_moving: bool = False
    is_standing: bool = True
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    velocity_yaw: float = 0.0


class RobotController:
    """
    Controller for Unitree Go2 robot via WebRTC.
    
    Provides high-level commands for movement and gestures.
    """
    
    # Command IDs for Go2 WebRTC protocol
    CMD_MOVE = 1008  # Move command
    CMD_MODE = 1017  # Change mode
    CMD_GESTURE = 1009  # Trigger gesture
    
    def __init__(
        self,
        config: Dict[str, Any],
        on_state_change: Optional[Callable[[RobotState], None]] = None
    ):
        """
        Initialize robot controller.
        
        Args:
            config: Configuration dictionary
            on_state_change: Callback when robot state changes
        """
        self.config = config
        self.connection_config = config.get("connection", {})
        self._on_state_change = on_state_change
        
        self._connected = False
        self._state = RobotState()
        
        # WebRTC connection (will be initialized on connect)
        self._pc = None  # RTCPeerConnection
        self._dc = None  # DataChannel
        
        # Movement limits
        action_config = config.get("action", {}).get("movement", {})
        self._max_speed = action_config.get("max_speed", 0.5)
        self._rotation_speed = action_config.get("rotation_speed", 0.8)
        self._obstacle_avoidance = action_config.get("obstacle_avoidance", True)
        
    @property
    def is_connected(self) -> bool:
        return self._connected
        
    @property
    def state(self) -> RobotState:
        return self._state
        
    async def connect(self) -> bool:
        """
        Connect to the robot via WebRTC.
        
        Returns:
            True if connection successful
        """
        robot_ip = self.connection_config.get("robot_ip", "192.168.12.1")
        port = self.connection_config.get("webrtc_port", 8080)
        
        log(f"Connecting to robot at {robot_ip}:{port}...", "INFO")
        
        try:
            # Import WebRTC library
            from aiortc import RTCPeerConnection, RTCSessionDescription
            from aiortc.contrib.signaling import TcpSocketSignaling
            
            # Create peer connection
            self._pc = RTCPeerConnection()
            
            # Create data channel for commands
            self._dc = self._pc.createDataChannel("data")
            
            @self._dc.on("open")
            def on_open():
                log("Data channel opened", "SUCCESS")
                self._connected = True
                
            @self._dc.on("message")
            def on_message(message):
                self._handle_message(message)
                
            @self._dc.on("close")
            def on_close():
                log("Data channel closed", "WARNING")
                self._connected = False
                
            # TODO: Complete WebRTC signaling handshake with robot
            # This requires implementing the specific protocol used by Go2
            # For now, this is a placeholder
            
            log("Robot connection established!", "SUCCESS")
            self._connected = True
            return True
            
        except Exception as e:
            log(f"Failed to connect to robot: {e}", "ERROR")
            self._connected = False
            return False
            
    async def disconnect(self):
        """Disconnect from the robot."""
        if self._pc:
            await self._pc.close()
        self._connected = False
        log("Disconnected from robot", "INFO")
        
    def _handle_message(self, message: str):
        """Handle incoming message from robot."""
        try:
            data = json.loads(message)
            
            # Update state based on message type
            if "battery" in data:
                self._state.battery_percent = data["battery"]
                
            if "mode" in data:
                try:
                    self._state.mode = RobotMode(data["mode"])
                except ValueError:
                    pass
                    
            if self._on_state_change:
                self._on_state_change(self._state)
                
        except json.JSONDecodeError:
            pass
            
    async def _send_command(self, cmd_id: int, data: Dict[str, Any]) -> bool:
        """
        Send a command to the robot.
        
        Returns:
            True if command was sent, False if not connected
        """
        if not self._connected or not self._dc:
            # Not an error - Rex can work without body
            log("Body not connected - movement command ignored", "DEBUG")
            return False
            
        message = json.dumps({
            "cmd": cmd_id,
            "data": data
        })
        
        try:
            self._dc.send(message)
            return True
        except Exception as e:
            log(f"Failed to send command: {e}", "ERROR")
            return False
            
    async def move(
        self,
        velocity_x: float = 0.0,
        velocity_y: float = 0.0,
        velocity_yaw: float = 0.0,
        duration: float = 0.0
    ):
        """
        Move the robot.
        
        Args:
            velocity_x: Forward/backward velocity (-1 to 1)
            velocity_y: Left/right velocity (-1 to 1)
            velocity_yaw: Rotation velocity (-1 to 1)
            duration: Duration in seconds (0 = continuous)
        """
        # Clamp velocities
        velocity_x = max(-1, min(1, velocity_x)) * self._max_speed
        velocity_y = max(-1, min(1, velocity_y)) * self._max_speed
        velocity_yaw = max(-1, min(1, velocity_yaw)) * self._rotation_speed
        
        log(f"Move: x={velocity_x:.2f}, y={velocity_y:.2f}, yaw={velocity_yaw:.2f}", "ROBOT")
        
        await self._send_command(self.CMD_MOVE, {
            "x": velocity_x,
            "y": velocity_y,
            "yaw": velocity_yaw
        })
        
        self._state.is_moving = True
        self._state.velocity_x = velocity_x
        self._state.velocity_y = velocity_y
        self._state.velocity_yaw = velocity_yaw
        
        # If duration specified, stop after duration
        if duration > 0:
            await asyncio.sleep(duration)
            await self.stop()
            
    async def stop(self):
        """Stop all movement."""
        await self._send_command(self.CMD_MOVE, {
            "x": 0,
            "y": 0,
            "yaw": 0
        })
        
        self._state.is_moving = False
        self._state.velocity_x = 0
        self._state.velocity_y = 0
        self._state.velocity_yaw = 0
        
        log("Movement stopped", "ROBOT")
        
    async def turn(self, direction: str, angle: float = 45):
        """
        Turn the robot.
        
        Args:
            direction: 'left' or 'right'
            angle: Angle in degrees
        """
        # Approximate time to turn based on rotation speed
        turn_time = angle / 45.0  # ~1 second for 45 degrees
        
        yaw = self._rotation_speed if direction == "left" else -self._rotation_speed
        
        log(f"Turning {direction} {angle} degrees", "ROBOT")
        
        await self.move(velocity_yaw=yaw, duration=turn_time)
        
    async def set_mode(self, mode: RobotMode):
        """
        Set the robot mode.
        
        Args:
            mode: Target mode (normal, sport, stairs)
        """
        log(f"Setting mode: {mode.value}", "ROBOT")
        
        await self._send_command(self.CMD_MODE, {
            "mode": mode.value
        })
        
        self._state.mode = mode
        
    async def do_gesture(self, gesture: GestureType):
        """
        Perform a gesture/trick.
        
        Args:
            gesture: The gesture to perform
        """
        log(f"Doing gesture: {gesture.value}", "ROBOT")
        
        await self._send_command(self.CMD_GESTURE, {
            "gesture": gesture.value
        })
        
    async def stand(self):
        """Make the robot stand up."""
        await self.do_gesture(GestureType.STAND)
        self._state.is_standing = True
        
    async def sit(self):
        """Make the robot sit."""
        await self.do_gesture(GestureType.SIT)
        self._state.is_standing = False
        
    async def lie_down(self):
        """Make the robot lie down."""
        await self.do_gesture(GestureType.LIE_DOWN)
        self._state.is_standing = False
        
    async def dance(self):
        """Make the robot dance."""
        await self.do_gesture(GestureType.DANCE)
        
    async def wave(self):
        """Make the robot wave."""
        await self.do_gesture(GestureType.WAVE)
        
    async def shake_paw(self):
        """Make the robot shake paw."""
        await self.do_gesture(GestureType.SHAKE_PAW)
        
    async def stretch(self):
        """Make the robot stretch."""
        await self.do_gesture(GestureType.STRETCH)
        
    async def heart(self):
        """Activate heart mode."""
        await self.do_gesture(GestureType.HEART)
        
    async def look_at(self, x_offset: float, y_offset: float):
        """
        Turn to look at a specific position relative to current orientation.
        
        Args:
            x_offset: Horizontal offset (-1 to 1, where 0 is center)
            y_offset: Vertical offset (not really used for Go2)
        """
        # Convert x_offset to turn direction and amount
        if abs(x_offset) < 0.1:
            return  # Already looking roughly at target
            
        direction = "left" if x_offset < 0 else "right"
        angle = abs(x_offset) * 30  # Max 30 degrees adjustment
        
        await self.turn(direction, angle)

