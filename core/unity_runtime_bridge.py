#!/usr/bin/env python3
"""
Unity Runtime Command Bridge - SOTA 2026
==========================================
EventBus → TCP bridge for sending commands to Unity runtime (CommandReceiver.cs).

This module bridges Kingdom AI's EventBus to Unity's TCP command receiver,
enabling AI-driven control of Unity applications (including Quest 3 VR builds).

Architecture:
  EventBus (unity.command) → UnityRuntimeBridge → TCP (port 8080) → Unity CommandReceiver.cs

Supported Commands (from CommandReceiver.cs):
  - move forward, move backward
  - turn left, turn right
  - jump, stop

Events Subscribed:
  - unity.command: Execute a command in Unity runtime
  - unity.runtime.connect: Attempt to connect to Unity
  - unity.runtime.disconnect: Disconnect from Unity
  - unity.runtime.ping: Check connection status

Events Published:
  - unity.runtime.connected: TCP connection established
  - unity.runtime.disconnected: TCP connection lost
  - unity.runtime.command.sent: Command sent successfully
  - unity.runtime.command.error: Command send failed
  - unity.runtime.status: Status updates

Author: Kingdom AI Team
Version: 1.0.0 SOTA 2026
"""

import logging
import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("KingdomAI.Unity.RuntimeBridge")


# ============================================================================
# CONFIGURATION
# ============================================================================

class UnityCommandType(Enum):
    """Supported Unity runtime commands (maps to CommandReceiver.cs)"""
    MOVE_FORWARD = "move forward"
    MOVE_BACKWARD = "move backward"
    TURN_LEFT = "turn left"
    TURN_RIGHT = "turn right"
    JUMP = "jump"
    STOP = "stop"
    CUSTOM = "custom"


@dataclass
class UnityRuntimeConfig:
    """Configuration for Unity runtime connection"""
    host: str = "localhost"
    port: int = 8080
    timeout: float = 5.0
    reconnect_interval: float = 3.0
    max_reconnect_attempts: int = 5
    auto_reconnect: bool = True
    quest_ip: Optional[str] = None
    quest_adb_port: int = 5555


# ============================================================================
# WSL HOST IP DETECTION
# ============================================================================

def _is_wsl() -> bool:
    """Check if running in WSL environment."""
    try:
        if os.path.exists('/proc/version'):
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
    except Exception:
        pass
    return False


def _get_windows_host_ip() -> str:
    """Get Windows host IP for WSL2."""
    default_ip = "localhost"
    
    if not _is_wsl():
        return default_ip
    
    try:
        result = subprocess.run(
            ['ip', 'route', 'show', 'default'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.split()
            if len(parts) >= 3 and parts[0] == 'default' and parts[1] == 'via':
                gateway_ip = parts[2]
                logger.info(f"🖥️ Windows host IP from gateway: {gateway_ip}")
                return gateway_ip
    except Exception:
        pass
    
    try:
        with open('/etc/resolv.conf', 'r') as rf:
            for line in rf:
                if line.strip().startswith('nameserver'):
                    host_ip = line.strip().split()[1]
                    if not host_ip.startswith('127.'):
                        logger.info(f"🖥️ Windows host IP from resolv.conf: {host_ip}")
                        return host_ip
    except Exception:
        pass
    
    return "172.20.0.1"


# ============================================================================
# UNITY RUNTIME BRIDGE
# ============================================================================

class UnityRuntimeBridge:
    """
    EventBus → TCP bridge for Unity runtime control.
    
    Subscribes to:
        - unity.command: Execute a command in Unity runtime
        - unity.runtime.connect: Attempt to connect to Unity
        - unity.runtime.disconnect: Disconnect from Unity
        - unity.runtime.ping: Check connection status
    
    Publishes:
        - unity.runtime.connected: TCP connection established
        - unity.runtime.disconnected: TCP connection lost
        - unity.runtime.command.sent: Command sent successfully
        - unity.runtime.command.error: Command send failed
        - unity.runtime.status: Status updates
    """
    
    def __init__(self, event_bus=None, config: Optional[UnityRuntimeConfig] = None):
        self.event_bus = event_bus
        self.config = config or UnityRuntimeConfig()
        self.logger = logging.getLogger("KingdomAI.Unity.RuntimeBridge")
        
        # Connection state
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._last_error: Optional[str] = None
        self._commands_sent = 0
        self._commands_failed = 0
        self._lock = threading.Lock()
        
        # Env override: UNITY_HOST, UNITY_PORT (so Creation tab / WSL can point to correct Unity)
        if os.environ.get("UNITY_HOST"):
            self.config.host = os.environ.get("UNITY_HOST", self.config.host)
            self.logger.info(f"🎮 Unity host from env: {self.config.host}")
        if os.environ.get("UNITY_PORT"):
            try:
                self.config.port = int(os.environ.get("UNITY_PORT", str(self.config.port)))
                self.logger.info(f"🎮 Unity port from env: {self.config.port}")
            except ValueError:
                pass
        # Auto-detect host for WSL when not set by env
        if _is_wsl() and self.config.host == "localhost":
            self.config.host = _get_windows_host_ip()
            self.logger.info(f"🎮 WSL detected, using Windows host: {self.config.host}")
        
        # Reconnection state
        self._reconnect_thread: Optional[threading.Thread] = None
        self._should_reconnect = False
        
        self.logger.info(f"✅ UnityRuntimeBridge initialized (target: {self.config.host}:{self.config.port})")
    
    def initialize(self) -> bool:
        """Initialize the bridge and subscribe to events."""
        if self.event_bus:
            try:
                self.event_bus.subscribe_sync("unity.command", self._on_unity_command)
                self.event_bus.subscribe_sync("unity.runtime.connect", self._on_connect_request)
                self.event_bus.subscribe_sync("unity.runtime.disconnect", self._on_disconnect_request)
                self.event_bus.subscribe_sync("unity.runtime.ping", self._on_ping_request)
                # Creation pipeline → Unity display (best-effort; Unity must support the command string)
                self.event_bus.subscribe_sync("visual.generated", self._on_visual_generated)
                self.event_bus.subscribe_sync("creation.output", self._on_creation_output)
                # FIX (2026-02-03): Subscribe to creative.unity.export for terrain/map exports
                self.event_bus.subscribe_sync("creative.unity.export", self._on_creative_unity_export)
                self.logger.info("✅ Subscribed to Unity runtime events")
            except Exception as e:
                self.logger.error(f"❌ Failed to subscribe to events: {e}")
                return False
        
        # CRITICAL FIX: Auto-connect on initialization so Unity display works immediately
        try:
            self.connect()
        except Exception as e:
            self.logger.debug(f"Auto-connect failed (Unity may not be running): {e}")
        
        self._publish_status()
        return True
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    def connect(self) -> bool:
        """Establish TCP connection to Unity runtime."""
        with self._lock:
            if self._connected and self._socket:
                return True

            if self._socket and not self._connected:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.config.timeout)
                self._socket.connect((self.config.host, self.config.port))
                self._connected = True
                self._last_error = None
                
                self.logger.info(f"✅ Connected to Unity runtime at {self.config.host}:{self.config.port}")
                
                if self.event_bus:
                    self.event_bus.publish("unity.runtime.connected", {
                        "host": self.config.host,
                        "port": self.config.port,
                        "timestamp": datetime.now().isoformat()
                    })
                
                return True
                
            except socket.timeout:
                self._last_error = "Connection timed out"
                self.logger.debug(f"ℹ️ Unity connection timed out to {self.config.host}:{self.config.port} (Unity not running)")
            except ConnectionRefusedError:
                self._last_error = "Connection refused - Unity not running or port blocked"
                self.logger.debug(f"ℹ️ Unity connection refused to {self.config.host}:{self.config.port} (Unity not running)")
            except Exception as e:
                self._last_error = str(e)
                self.logger.error(f"❌ Connection failed: {e}")
            
            self._connected = False
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
            self._socket = None
            return False
    
    def disconnect(self) -> None:
        """Close TCP connection to Unity runtime."""
        with self._lock:
            self._should_reconnect = False
            
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            
            was_connected = self._connected
            self._connected = False
            
            if was_connected:
                self.logger.info("✅ Disconnected from Unity runtime")
                if self.event_bus:
                    self.event_bus.publish("unity.runtime.disconnected", {
                        "timestamp": datetime.now().isoformat()
                    })
    
    def is_connected(self) -> bool:
        """Check if currently connected to Unity."""
        return self._connected
    
    def ping(self) -> bool:
        """Test connection by attempting to connect if not connected."""
        if self._connected:
            return True
        return self.connect()
    
    # ========================================================================
    # COMMAND SENDING
    # ========================================================================
    
    def send_command(self, command: str) -> bool:
        """Send a command string to Unity runtime via TCP."""
        if not command:
            self.logger.warning("⚠️ Empty command, skipping")
            return False
        
        # Normalize command
        command = command.strip()
        
        # Auto-connect if not connected
        if not self._connected:
            if not self.connect():
                self._commands_failed += 1
                if self.event_bus:
                    self.event_bus.publish("unity.runtime.command.error", {
                        "command": command,
                        "error": self._last_error or "Not connected",
                        "timestamp": datetime.now().isoformat()
                    })
                return False
        
        with self._lock:
            try:
                # Send command as UTF-8 encoded string
                self._socket.sendall(command.encode('utf-8'))
                self._commands_sent += 1
                
                self.logger.info(f"📤 Sent Unity command: '{command}'")
                
                if self.event_bus:
                    self.event_bus.publish("unity.runtime.command.sent", {
                        "command": command,
                        "commands_sent": self._commands_sent,
                        "timestamp": datetime.now().isoformat()
                    })
                
                return True
                
            except (BrokenPipeError, ConnectionResetError) as e:
                self._last_error = f"Connection lost: {e}"
                self._connected = False
                if self._socket:
                    try:
                        self._socket.close()
                    except Exception:
                        pass
                self._socket = None
                self._commands_failed += 1
                
                self.logger.warning(f"⚠️ Connection lost while sending command: {e}")
                
                if self.event_bus:
                    self.event_bus.publish("unity.runtime.command.error", {
                        "command": command,
                        "error": self._last_error,
                        "timestamp": datetime.now().isoformat()
                    })
                    self.event_bus.publish("unity.runtime.disconnected", {
                        "reason": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                
                return False
                
            except Exception as e:
                self._last_error = str(e)
                self._commands_failed += 1
                
                self.logger.error(f"❌ Failed to send command: {e}")
                
                if self.event_bus:
                    self.event_bus.publish("unity.runtime.command.error", {
                        "command": command,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                
                return False
    
    def send_command_type(self, cmd_type: UnityCommandType) -> bool:
        """Send a predefined command type to Unity."""
        return self.send_command(cmd_type.value)
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    def _on_unity_command(self, data: Dict[str, Any]) -> None:
        """Handle unity.command events from EventBus."""
        if isinstance(data, str):
            command = data
        elif isinstance(data, dict):
            command = data.get("command", data.get("text", ""))
        else:
            self.logger.warning(f"⚠️ Invalid command data type: {type(data)}")
            return
        
        if command:
            self.send_command(command)
    
    def _on_connect_request(self, data: Dict[str, Any] = None) -> None:
        """Handle unity.runtime.connect events."""
        if data:
            if "host" in data:
                self.config.host = data["host"]
            if "port" in data:
                self.config.port = data["port"]
        
        self.connect()
    
    def _on_disconnect_request(self, data: Dict[str, Any] = None) -> None:
        """Handle unity.runtime.disconnect events."""
        self.disconnect()
    
    def _on_ping_request(self, data: Dict[str, Any] = None) -> None:
        """Handle unity.runtime.ping events."""
        result = self.ping()
        self._publish_status()

    # ========================================================================
    # CREATION → UNITY DISPLAY (BEST-EFFORT)
    # ========================================================================

    @staticmethod
    def _to_windows_path_for_unity(path_value: str) -> str:
        """Convert WSL /mnt/<drive>/... paths to Windows paths for Unity on Windows."""
        p = str(path_value or "")
        # /mnt/c/Users/... -> C:\Users\...
        if p.startswith("/mnt/") and len(p) > 6 and p[5].isalpha() and p[6] == "/":
            drive = p[5].upper()
            rest = p[7:]  # after "/mnt/<drive>/"
            rest = rest.replace("/", "\\")
            return f"{drive}:\\{rest}"
        return p

    def _on_visual_generated(self, data: Dict[str, Any]) -> None:
        """Handle visual.generated and forward to creation.output for Unity mapping."""
        try:
            if isinstance(data, dict):
                payload = dict(data)
            else:
                payload = {"data": data}
            # Normalize and route through the same handler.
            self._on_creation_output(payload)
        except Exception as e:
            self.logger.debug(f"visual.generated handler error: {e}")

    def _on_creation_output(self, data: Dict[str, Any]) -> None:
        """Send a creation output to Unity as a command string (Unity receiver must implement it)."""
        try:
            if not isinstance(data, dict):
                return

            image_path = data.get("image_path") or data.get("path") or data.get("file")
            video_path = data.get("video_path")
            if not image_path and not video_path:
                return

            target_path = image_path or video_path
            win_path = self._to_windows_path_for_unity(str(target_path))
            if video_path:
                command = f"display_video|{win_path}"
            else:
                # Convention: Unity CommandReceiver.cs should implement this.
                # Example parse: "display_image|C:\\path\\to\\file.png"
                command = f"display_image|{win_path}"
            self.send_command(command)
        except Exception as e:
            self.logger.debug(f"creation.output handler error: {e}")
    
    def _on_creative_unity_export(self, data: Dict[str, Any]) -> None:
        """Handle creative.unity.export events - sends terrain/map data to Unity runtime.
        
        Expected payload:
        {
            "map_id": str,
            "map_name": str,
            "json_path": str,  # Path to JSON terrain data
            "raw_path": str,   # Path to RAW heightmap file
            "dimensions": tuple  # (width, height)
        }
        """
        try:
            if not isinstance(data, dict):
                return
            
            map_id = data.get("map_id", "")
            map_name = data.get("map_name", "terrain")
            json_path = data.get("json_path", "")
            raw_path = data.get("raw_path", "")
            dimensions = data.get("dimensions", (512, 512))
            
            if not json_path and not raw_path:
                self.logger.warning("creative.unity.export: No paths provided")
                return
            
            # Convert WSL paths to Windows paths for Unity
            json_win = self._to_windows_path_for_unity(str(json_path)) if json_path else ""
            raw_win = self._to_windows_path_for_unity(str(raw_path)) if raw_path else ""
            
            # Send terrain import command to Unity
            # Format: "import_terrain|map_id|map_name|json_path|raw_path|width|height"
            width, height = dimensions if isinstance(dimensions, (list, tuple)) and len(dimensions) >= 2 else (512, 512)
            command = f"import_terrain|{map_id}|{map_name}|{json_win}|{raw_win}|{width}|{height}"
            self.send_command(command)
            
            self.logger.info(f"✅ Sent terrain export to Unity: {map_name} ({width}x{height})")
        except Exception as e:
            self.logger.error(f"❌ creative.unity.export handler error: {e}", exc_info=True)
    
    def _publish_status(self) -> None:
        """Publish current status to EventBus."""
        if self.event_bus:
            self.event_bus.publish("unity.runtime.status", {
                "connected": self._connected,
                "host": self.config.host,
                "port": self.config.port,
                "commands_sent": self._commands_sent,
                "commands_failed": self._commands_failed,
                "last_error": self._last_error,
                "timestamp": datetime.now().isoformat()
            })
    
    # ========================================================================
    # STATUS & DIAGNOSTICS
    # ========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bridge status."""
        return {
            "connected": self._connected,
            "host": self.config.host,
            "port": self.config.port,
            "commands_sent": self._commands_sent,
            "commands_failed": self._commands_failed,
            "last_error": self._last_error,
            "is_wsl": _is_wsl()
        }
    
    def shutdown(self) -> None:
        """Shutdown the bridge cleanly."""
        self.disconnect()
        self.logger.info("✅ UnityRuntimeBridge shutdown complete")


# ============================================================================
# AI INTENT TO UNITY COMMAND MAPPER
# ============================================================================

class UnityIntentMapper:
    """
    Maps AI intents/natural language to Unity commands.
    
    Used by AICommandRouter to translate recognized intents into
    Unity-specific commands for the runtime bridge.
    """
    
    # Intent patterns that map to Unity commands
    INTENT_PATTERNS = {
        # Movement intents
        "move_forward": ["move forward", "go forward", "walk forward", "step forward", "advance"],
        "move_backward": ["move backward", "go backward", "walk backward", "step back", "retreat"],
        "turn_left": ["turn left", "rotate left", "look left", "face left"],
        "turn_right": ["turn right", "rotate right", "look right", "face right"],
        "jump": ["jump", "hop", "leap"],
        "stop": ["stop", "halt", "freeze", "stay", "wait"],
    }
    
    # Map intent names to Unity commands
    INTENT_TO_COMMAND = {
        "move_forward": UnityCommandType.MOVE_FORWARD,
        "move_backward": UnityCommandType.MOVE_BACKWARD,
        "turn_left": UnityCommandType.TURN_LEFT,
        "turn_right": UnityCommandType.TURN_RIGHT,
        "jump": UnityCommandType.JUMP,
        "stop": UnityCommandType.STOP,
    }
    
    @classmethod
    def map_text_to_command(cls, text: str) -> Optional[UnityCommandType]:
        """Map natural language text to a Unity command."""
        text_lower = text.lower().strip()
        
        for intent_name, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return cls.INTENT_TO_COMMAND.get(intent_name)
        
        return None
    
    @classmethod
    def is_unity_intent(cls, text: str) -> bool:
        """Check if text contains a Unity-related intent."""
        return cls.map_text_to_command(text) is not None


# ============================================================================
# SINGLETON & FACTORY
# ============================================================================

_unity_runtime_bridge: Optional[UnityRuntimeBridge] = None


def get_unity_runtime_bridge(event_bus=None, config: Optional[UnityRuntimeConfig] = None) -> UnityRuntimeBridge:
    """Get or create Unity Runtime Bridge singleton."""
    global _unity_runtime_bridge
    if _unity_runtime_bridge is None:
        _unity_runtime_bridge = UnityRuntimeBridge(event_bus, config)
        _unity_runtime_bridge.initialize()
    return _unity_runtime_bridge


def initialize_unity_runtime_bridge(event_bus=None, config: Optional[UnityRuntimeConfig] = None) -> UnityRuntimeBridge:
    """Initialize and return Unity Runtime Bridge (alias for get_unity_runtime_bridge)."""
    return get_unity_runtime_bridge(event_bus, config)


# ============================================================================
# QUICK TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    print("=" * 60)
    print("🎮 UNITY RUNTIME BRIDGE TEST")
    print("=" * 60)
    
    # Create bridge without event bus for standalone test
    bridge = UnityRuntimeBridge()
    
    print(f"\n📊 Bridge Status:")
    status = bridge.get_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    print(f"\n🔌 Attempting connection to {bridge.config.host}:{bridge.config.port}...")
    connected = bridge.connect()
    
    if connected:
        print("✅ Connected to Unity runtime!")
        
        # Test sending commands
        test_commands = ["move forward", "turn left", "jump", "stop"]
        for cmd in test_commands:
            print(f"\n📤 Sending: '{cmd}'")
            result = bridge.send_command(cmd)
            print(f"   Result: {'✅ Success' if result else '❌ Failed'}")
            time.sleep(0.5)
        
        bridge.disconnect()
    else:
        print(f"⚠️ Could not connect: {bridge._last_error}")
        print("\n💡 Make sure Unity is running with CommandReceiver.cs on port 8080")
    
    print("\n" + "=" * 60)
    print("🏁 Unity Runtime Bridge test complete")
    print("=" * 60)
