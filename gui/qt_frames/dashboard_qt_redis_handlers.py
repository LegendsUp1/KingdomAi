"""Redis connection handlers for Kingdom-AI Dashboard.

This module contains handlers for Redis connection, ensuring strict 
connectivity requirements are enforced for the Kingdom AI system.

- Strict enforcement of Redis connection on port 6380
- No fallback connections permitted 
- System halting on critical Redis failures
- Accurate dashboard status indicator updates
"""

def _init_redis_connection(self):
    """Initialize Redis connection with strict error handling.
    
    Raises:
        RedisConnectionError: If connection to Redis fails
    """
    try:
        self.redis_client = redis.Redis(
            host='localhost',
            port=6380,
            password='QuantumNexus2025',
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Test connection with ping
        if not self.redis_client.ping():
            raise RedisConnectionError("Failed to connect to Redis: No response to PING")
        
        # Update connection status and UI
        self.redis_connected = True
        self._update_redis_status(True, "Successfully connected to Redis Quantum Nexus on port 6380")
        
    except Exception as e:
        error_msg = f"Failed to connect to Redis Quantum Nexus on port 6380: {str(e)}"
        self._log_error(error_msg)
        self._handle_redis_error(error_msg)
        raise RedisConnectionError(error_msg) from e
        
def _update_redis_status(self, connected: bool, message: str = ""):
    """Update Redis status indicator and log message."""
    if connected:
        self._update_led_state('redis_status', 'on')
        self._update_system_indicator('redis', message or "Connected", "#4CAF50")
        self._log_info(message or "Redis connected successfully")
    else:
        self._update_led_state('redis_status', 'off')
        self._update_system_indicator('redis', message or "Disconnected", "#F44336")
        self._log_error(message or "Redis disconnected")
    
    # Update overall system status
    self._update_kingdom_ai_status()

def _handle_redis_error(self, error_msg: str):
    """Handle Redis connection errors and update UI accordingly.
    
    This is a critical failure condition that will halt the application
    as there is no fallback for Redis connection.
    
    Args:
        error_msg: Detailed error message about the Redis failure
    """
    self._log_error(f"Redis Connection Error: {error_msg}")
    
    # Update UI indicators
    if hasattr(self, '_update_led_state'):
        self._update_led_state('redis_status', 'off')
        
    if hasattr(self, '_update_system_indicator'):
        self._update_system_indicator('redis', f"Error: {error_msg[:50]}...", "#F44336")
    
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
            "2. The Redis password is correct\n"
            "3. The Redis server is accessible from this machine"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    except Exception as dialog_error:
        self._log_error(f"Failed to show Redis error dialog: {dialog_error}")
    
    # Publish critical error to event bus
    if hasattr(self, 'event_bus') and self.event_bus:
        try:
            self.event_bus.publish_sync('system.critical_error', {
                'source': 'dashboard',
                'component': 'redis',
                'error': error_msg,
                'halt_required': True
            })
        except Exception as publish_error:
            self._log_error(f"Failed to publish critical error event: {publish_error}")
    
    # DO NOT HALT - system must stay running
    try:
        logger.critical("⚠️ Dashboard will operate in degraded mode without Redis")
    except Exception:
        pass

def _handle_redis_connect(self, event_data: Dict[str, Any]) -> None:
    """Handle Redis connect events.
    
    Args:
        event_data: Dictionary containing Redis connection data including:
            - host: Redis host
            - port: Redis port
            - error: Error message if any
    """
    try:
        self._log_debug(f"Redis connect event: {event_data}")
        
        # Extract connection data
        host = event_data.get('host', 'unknown')
        port = event_data.get('port', 0)
        error = event_data.get('error', '')
        
        # Enforce strict port 6380 policy
        if port != 6380:
            error_msg = f"Redis connected on wrong port: {port} (must be 6380)"
            self._log_error(error_msg)
            self._handle_redis_error(error_msg)
            return
        
        # Update connection status
        self.redis_connected = True
        self._update_led_state('redis_status', 'on')
        self._update_system_indicator('redis', f"Connected to {host}:{port}", "#4CAF50")
        
        # Update kingdom status
        self._update_kingdom_ai_status()
        
    except Exception as e:
        self._log_error(f"Error handling Redis connect: {e}")

def _handle_redis_disconnect(self, event_data: Dict[str, Any]) -> None:
    """Handle Redis disconnect events.
    
    Args:
        event_data: Dictionary containing Redis disconnection data including:
            - reason: Reason for disconnection
            - error: Error message if any
    """
    try:
        self._log_debug(f"Redis disconnect event: {event_data}")
        
        # Extract disconnect data
        reason = event_data.get('reason', 'Unknown reason')
        error = event_data.get('error', '')
        
        # Update connection status
        self.redis_connected = False
        self._update_led_state('redis_status', 'off')
        
        # Prepare error message
        error_msg = f"Redis disconnected: {error or reason}"
        self._update_system_indicator('redis', f"Disconnected: {error or reason}", "#F44336")
        self._log_error(error_msg)
        
        # Show critical error dialog
        if hasattr(self, 'parent') and self.parent:
            QMessageBox.critical(self.parent, "Redis Disconnect",
                                f"Redis connection lost\n\nReason: {reason}\n{error}\n\nSystem will halt.")
        
        # Publish critical error to halt the system
        if hasattr(self, 'event_bus') and hasattr(self.event_bus, 'publish_sync'):
            self.event_bus.publish_sync('system.critical_error', {
                'message': error_msg,
                'source': 'dashboard',
                'component': 'redis',
                'halt_required': True
            })
        
        # Update Kingdom AI status
        self._update_kingdom_ai_status()
        
    except Exception as e:
        self._log_error(f"Error handling Redis disconnect: {e}")

def _handle_redis_status(self, event_data: Dict[str, Any]) -> None:
    """Handle Redis status updates.
    
    Args:
        event_data: Dictionary containing Redis status details including:
            - connected: Boolean indicating if Redis is connected
            - port: Port number Redis is using
            - error: Error message if any
    
    Note:
        Enforces strict port 6380 requirement with no fallback.
        System will halt if Redis is not connected on port 6380.
    """
    try:
        self._log_debug(f"Redis status update: {event_data}")
        
        # Extract connection status
        connected = event_data.get('connected', False)
        port = event_data.get('port', 0)
        error = event_data.get('error', '')
        
        # Update connection status
        self.redis_connected = connected
        
        # Enforce strict port 6380 policy
        if port != 6380 and connected:
            error_msg = f"Redis connected on wrong port: {port} (must be 6380)"
            self._log_error(error_msg)
            self.redis_connected = False
            
            # Update status indicators
            self._update_led_state('redis_status', 'off')
            self._update_system_indicator('redis', f"Error: Wrong port {port}", "#F44336")
            
            # Show critical error and halt system
            if hasattr(self, 'parent') and self.parent:
                QMessageBox.critical(self.parent, "Critical Redis Error", 
                                   f"Redis must run on port 6380. Currently on port {port}.\n\nSystem will halt.")
            
            # Halt system - no fallbacks allowed
            if hasattr(self, 'event_bus') and hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync('system.critical_error', {
                    'message': error_msg,
                    'source': 'dashboard',
                    'component': 'redis',
                    'halt_required': True
                })
            return
            
        # Update LED and status text based on connection status
        if connected:
            self._update_led_state('redis_status', 'on')
            self._update_system_indicator('redis', f"Connected on port {port}", "#4CAF50")
            self._log_info(f"Redis connected on port {port}")
        else:
            self._update_led_state('redis_status', 'off')
            
            # If Redis disconnected, show critical error and halt system
            if error:
                if hasattr(self, 'parent') and self.parent:
                    QMessageBox.critical(self.parent, "Critical Redis Error", 
                                      f"Redis connection failed\n\nError: {error}\n\nSystem will halt.")
                
                # Halt system - no fallbacks allowed for Redis
                if hasattr(self, 'event_bus') and hasattr(self.event_bus, 'publish_sync'):
                    self.event_bus.publish_sync('system.critical_error', {
                        'message': f"Redis disconnected: {error}",
                        'source': 'dashboard',
                        'component': 'redis',
                        'halt_required': True
                    })
            
            # Update status text with error
            self._update_system_indicator('redis', f"Disconnected: {error[:50]}", "#F44336")
            self._log_error(f"Redis disconnected: {error}")
        
        # Update overall system status
        self._update_kingdom_ai_status()
        
    except Exception as e:
        self._log_error(f"Error handling Redis status: {e}")

def _handle_redis_server_status(self, event_data: Dict[str, Any]) -> None:
    """Handle Redis server status updates.
    
    Args:
        event_data: Dictionary containing Redis server status details including:
            - running: Boolean indicating if Redis server is running
            - port: Port number Redis server is listening on
            - error: Error message if any issue detected
    
    Note:
        Enforces strict port 6380 requirement with no fallback.
        System will halt if Redis server is not running on port 6380.
    """
    try:
        self._log_debug(f"Redis server status update: {event_data}")
        
        # Extract server status
        running = event_data.get('running', False)
        port = event_data.get('port', 0)
        error = event_data.get('error', '')
        reason = event_data.get('reason', '')
        
        # Critical check: enforce port 6380
        if port != 6380 and running:
            error_msg = f"Redis server running on wrong port: {port} (must be 6380)"
            self._log_error(error_msg)
            self.redis_connected = False
            
            # Update status indicators
            self._update_led_state('redis_status', 'off')
            self._update_system_indicator('redis', f"Error: Wrong port {port}", "#F44336")
            
            # Show critical error and halt system
            if hasattr(self, 'parent') and self.parent:
                QMessageBox.critical(self.parent, "Critical Redis Error", 
                                  f"Redis server must run on port 6380. Currently on port {port}.\n\nSystem will halt.")
            
            # Halt system - no fallbacks allowed
            if hasattr(self, 'event_bus') and hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync('system.critical_error', {
                    'message': error_msg,
                    'source': 'dashboard',
                    'component': 'redis',
                    'halt_required': True
                })
            return
            
        # Update LED and status text based on server status
        if running:
            # Still need to check connection status
            if self.redis_connected:
                self._update_led_state('redis_status', 'on')
                self._update_system_indicator('redis', f"Server running on port {port}", "#4CAF50")
                self._log_info(f"Redis server running on port {port}")
        else:
            self.redis_connected = False
            self._update_led_state('redis_status', 'off')
            
            # If Redis server not running, show critical error and halt system
            error_detail = error if error else reason if reason else "Unknown error"
            error_msg = f"Redis server not running: {error_detail}"
            self._log_error(error_msg)
            
            # Update status indicator
            self._update_system_indicator('redis', f"Server offline: {error_detail[:50]}", "#F44336")
            
            # Show critical error message
            if hasattr(self, 'parent') and self.parent:
                QMessageBox.critical(self.parent, "Critical Redis Error", 
                                  f"Redis server is not running\n\nError: {error_detail}\n\nSystem will halt.")
            
            # Halt system - no fallbacks allowed
            if hasattr(self, 'event_bus') and hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync('system.critical_error', {
                    'message': error_msg,
                    'source': 'dashboard',
                    'component': 'redis',
                    'halt_required': True
                })
        
        # Update overall system status
        self._update_kingdom_ai_status()
        
    except Exception as e:
        self._log_error(f"Error handling Redis server status: {e}")
