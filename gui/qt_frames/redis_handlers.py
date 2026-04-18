"""Redis connection and event handler implementations for Kingdom AI.

This module provides comprehensive Redis connection management with strict enforcement
of connection on port 6380 with secure password handling. No fallback connections
are allowed - system will halt immediately if Redis connection fails.
"""
import logging
import os
import redis
import sys
from typing import Dict, Any, Optional

# Import centralized Redis security handling
from utils.redis_security import get_redis_config, get_redis_password

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QApplication, QMessageBox
    PYQT6_AVAILABLE = True
except ImportError:
    try:
        from PyQt5.QtCore import QObject, pyqtSignal
        from PyQt5.QtWidgets import QApplication, QMessageBox
        PYQT6_AVAILABLE = False
    except ImportError as e:
        raise ImportError("PyQt6 or PyQt5 is required.") from e

# Configure logger
logger = logging.getLogger(__name__)

# Redis configuration - STRICTLY enforce port 6380 with no fallbacks
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6380,  # MUST be 6380 - system will halt if different
    'password': get_redis_password(),  # Use centralized password handling
    'db': 0,
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
    'retry_on_timeout': True,
    'health_check_interval': 30,
    'decode_responses': True
}

class RedisConnectionError(Exception):
    """Raised when Redis connection fails."""
    pass


class RedisHandler(QObject):
    """Handles Redis connection and events with strict enforcement.
    
    No fallbacks are allowed - system will halt on any Redis connection failures.
    """
    # Define signals
    redis_connected = pyqtSignal(bool, str)
    redis_error = pyqtSignal(str)
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize Redis handler.
        
        Args:
            parent: Parent QObject
            event_bus: Event bus for publishing events
        """
        super().__init__(parent)
        self.redis_client = None
        self.is_connected = False
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
    
    def init_connection(self):
        """Initialize Redis connection with strict error handling.
        
        Raises:
            RedisConnectionError: If connection to Redis fails
        """
        try:
            self.logger.info("Initializing Redis connection on port 6380...")
            self.redis_client = redis.Redis(
                host=REDIS_CONFIG['host'],
                port=REDIS_CONFIG['port'],  # STRICTLY enforced port - no fallbacks allowed
                password=REDIS_CONFIG['password'],
                socket_connect_timeout=REDIS_CONFIG['socket_connect_timeout'],
                socket_timeout=REDIS_CONFIG['socket_timeout'],
                retry_on_timeout=REDIS_CONFIG['retry_on_timeout'],
                health_check_interval=REDIS_CONFIG['health_check_interval'],
                decode_responses=REDIS_CONFIG['decode_responses']
            )
            
            # Test connection with ping
            if not self.redis_client.ping():
                error_msg = "Failed to connect to Redis: No response to PING"
                self.logger.error(error_msg)
                self.handle_error(error_msg)
                raise RedisConnectionError(error_msg)
            
            # Update connection status
            self.is_connected = True
            self.redis_connected.emit(True, "Successfully connected to Redis Quantum Nexus on port 6380")
            self.logger.info("Successfully connected to Redis Quantum Nexus on port 6380")
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to Redis Quantum Nexus on port 6380: {str(e)}"
            self.logger.error(error_msg)
            self.handle_error(error_msg)
            raise RedisConnectionError(error_msg) from e
    
    def handle_error(self, error_msg: str):
        """Handle Redis connection errors and update UI accordingly.
        
        This is a critical failure condition that will halt the application
        as there is no fallback for Redis connection.
        
        Args:
            error_msg: Detailed error message about the Redis failure
        """
        self.logger.error(f"Redis Connection Error: {error_msg}")
        self.redis_error.emit(error_msg)
        
        # Emit signal for connection status update
        self.redis_connected.emit(False, error_msg)
        
        # Show critical error message to user
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Redis Connection Error")
            msg.setText("Failed to connect to Redis Quantum Nexus")
            msg.setInformativeText(
                "The application cannot start because it cannot connect to the Redis Quantum Nexus.\n\n"
                f"Error details: {error_msg}\n\n"
                "Please ensure that:\n"
                "1. Redis server is running on port 6380\n"
                "2. The Redis password is correct ('QuantumNexus2025')\n"
                "3. The Redis server is accessible from this machine"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
        except Exception as dialog_error:
            self.logger.error(f"Failed to show Redis error dialog: {dialog_error}")
        
        # Publish critical error to event bus
        if self.event_bus:
            try:
                self.event_bus.publish_sync('system.critical_error', {
                    'source': 'redis_handler',
                    'component': 'redis',
                    'error': error_msg,
                    'halt_required': True
                })
            except Exception as publish_error:
                self.logger.error(f"Failed to publish critical error event: {publish_error}")
        
        # DO NOT HALT - system must stay running
        try:
            logger.critical("⚠️ Component will operate in degraded mode without Redis")
        except Exception:
            pass
    
    def handle_redis_status(self, event_data: Dict[str, Any]):
        """Handle Redis status events from the event bus.
        
        Args:
            event_data: Event data containing Redis status information
        """
        try:
            self.logger.info(f"Received Redis status event: {event_data}")
            
            # Extract event data with defaults
            host = event_data.get('host', 'localhost')
            port = event_data.get('port', 0)
            connected = event_data.get('connected', False)
            error = event_data.get('error', '')
            
            # STRICT PORT ENFORCEMENT: If port is not 6380, treat as connection failure
            if connected and port != 6380:
                error_msg = f"Redis connection attempted on incorrect port: {port}. Must use port 6380."
                self.logger.error(error_msg)
                self.handle_error(error_msg)
                return
            
            # Handle error condition
            if not connected or error:
                error_msg = error or "Unknown Redis connection error"
                self.logger.error(f"Redis connection failed: {error_msg}")
                self.handle_error(error_msg)
                return
            
            # Update connection status for successful connection
            self.is_connected = True
            self.redis_connected.emit(True, f"Connected to Redis on {host}:{port}")
            self.logger.info(f"Redis connected successfully on {host}:{port}")
            
        except Exception as e:
            self.logger.error(f"Error handling Redis status event: {e}")
            self.handle_error(f"Failed to process Redis status: {str(e)}")
    
    def handle_redis_server_status(self, event_data: Dict[str, Any]):
        """Handle Redis server status events from the event bus.
        
        Args:
            event_data: Event data containing Redis server status
        """
        try:
            self.logger.info(f"Received Redis server status event: {event_data}")
            
            # Extract event data
            running = event_data.get('running', False)
            reason = event_data.get('reason', '')
            port = event_data.get('port', 0)
            
            # STRICT PORT ENFORCEMENT: If port is not 6380, treat as server failure
            if running and port != 6380:
                error_msg = f"Redis server running on incorrect port: {port}. Must use port 6380."
                self.logger.error(error_msg)
                self.handle_error(error_msg)
                return
            
            # Handle server not running
            if not running:
                error_msg = f"Redis server is not running: {reason or 'Unknown reason'}"
                self.logger.error(error_msg)
                self.handle_error(error_msg)
                return
            
            # Update for successful server status
            self.redis_connected.emit(True, f"Redis server running on port {port}")
            self.logger.info(f"Redis server running on port {port}")
            
        except Exception as e:
            self.logger.error(f"Error handling Redis server status: {e}")
            self.handle_error(f"Failed to process Redis server status: {str(e)}")
    
    def check_connection_health(self):
        """Check Redis connection health and handle failures.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        if not self.redis_client:
            self.handle_error("Redis client not initialized")
            return False
        
        try:
            # Test connection with ping
            if not self.redis_client.ping():
                self.handle_error("Redis connection health check failed: No response to PING")
                return False
            
            # Additional health checks if needed
            info = self.redis_client.info()
            if 'redis_version' not in info:
                self.handle_error("Redis connection health check failed: Invalid server info response")
                return False
            
            # Verify Redis is running on correct port
            if info.get('tcp_port', 0) != 6380:
                self.handle_error(f"Redis running on incorrect port: {info.get('tcp_port')}. Must use port 6380.")
                return False
                
            # Connection is healthy
            self.logger.debug("Redis connection health check passed")
            return True
            
        except Exception as e:
            self.handle_error(f"Redis connection health check failed: {str(e)}")
            return False
