#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ErrorResolutionSystem component for Kingdom AI.
Monitors, diagnoses, and resolves errors across all Kingdom AI components.
"""

import os
import logging
import traceback
import asyncio
import time
from datetime import datetime, timedelta
from collections import deque, defaultdict

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class ErrorResolutionSystem(BaseComponent):
    """
    Component for error detection, diagnosis, and resolution.
    Provides real-time error monitoring and recovery.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the ErrorResolutionSystem component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(name="ErrorResolutionSystem", event_bus=event_bus, config=config)
        self.description = "Error monitoring and resolution system"
        
        # Configuration
        self.logs_dir = self.config.get("logs_dir", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs"))
        self.error_log_file = self.config.get("error_log_file", "kingdom_error.log")
        self.max_errors = self.config.get("max_errors", 1000)
        self.check_interval = self.config.get("check_interval", 5)  # seconds
        self.recovery_timeout = self.config.get("recovery_timeout", 60)  # seconds
        self.auto_recovery = self.config.get("auto_recovery", True)
        
        # Error tracking
        self.error_history = deque(maxlen=self.max_errors)
        self.active_errors = {}  # Component -> list of active errors
        self.recovery_attempts = defaultdict(int)  # Error ID -> number of recovery attempts
        self.component_status = {}  # Component -> status (ok, warning, error)
        
        # Status
        self.monitoring_task = None
        self.is_initialized = False
        
    async def _safe_publish(self, event_type, data):
        """Safely publish an event, checking if event_bus exists first."""
        if self.event_bus:
            try:
                await self.event_bus.publish(event_type, data)
                return True
            except Exception as e:
                logger.error(f"Error publishing event {event_type}: {e}")
                return False
        else:
            logger.warning(f"Cannot publish event {event_type}: event_bus is None")
            return False
            
    async def initialize(self):
        """Initialize the ErrorResolutionSystem component."""
        logger.info("Initializing ErrorResolutionSystem")
        
        # Check if event_bus is properly initialized
        if not self.event_bus:
            logger.error("ErrorResolutionSystem initialized with no event_bus")
            return False
        
        # Create logs directory if it doesn't exist
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Create error log file if it doesn't exist
        error_log_path = os.path.join(self.logs_dir, self.error_log_file)
        if not os.path.exists(error_log_path):
            with open(error_log_path, 'w') as f:
                f.write("# Kingdom AI Error Log\n")
        
        # Subscribe to events
        try:
            self.event_bus.subscribe_sync("component.error", self.on_component_error)
            self.event_bus.subscribe_sync("component.status", self.on_component_status)
            self.event_bus.subscribe_sync("error.resolve", self.on_resolve_error)
            self.event_bus.subscribe_sync("system.health.check", self.on_health_check)
            self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        except Exception as e:
            logger.error(f"Failed to register Security Manager events: {e}")
            return False
        
        # Start error monitoring task
        self.monitoring_task = asyncio.create_task(self._monitor_errors())
        
        self.is_initialized = True
        logger.info("ErrorResolutionSystem initialized")
        return True
    
    async def _monitor_errors(self):
        """Monitor for errors and attempt recovery."""
        try:
            while True:
                await asyncio.sleep(self.check_interval)
                
                # Check for new errors in log file
                await self._check_error_logs()
                
                # Attempt recovery for active errors
                if self.auto_recovery:
                    await self._attempt_recovery()
                
                # Check component health
                await self._check_component_health()
                
        except asyncio.CancelledError:
            logger.info("Error monitoring task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in monitoring task: {e}")
            traceback.print_exc()
    
    async def _check_error_logs(self):
        """Check error log file for new errors."""
        try:
            error_log_path = os.path.join(self.logs_dir, self.error_log_file)
            
            with open(error_log_path, 'r') as f:
                # Read the last N lines to check for new errors
                lines = deque(f, 100)
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Basic error parsing - could be enhanced for more structured logs
                if "ERROR" in line or "CRITICAL" in line:
                    timestamp_str = line.split(' ')[0]
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        # Only process recent errors
                        if datetime.now() - timestamp < timedelta(minutes=5):
                            await self._process_log_error(line)
                    except (ValueError, IndexError):
                        # Unable to parse timestamp, process anyway
                        await self._process_log_error(line)
        
        except Exception as e:
            logger.error(f"Error checking error logs: {e}")
    
    async def _process_log_error(self, error_line):
        """Process an error from the log file."""
        # Basic processing - extract component and error message
        component = "unknown"
        error_msg = error_line
        
        # Try to extract component name
        for part in error_line.split(' '):
            if '.' in part and not part.startswith('[') and not part.endswith(']'):
                component_candidate = part.split('.')[0]
                if len(component_candidate) > 2:
                    component = component_candidate
                    break
        
        # Create error record
        error_id = f"{int(time.time())}_{component}"
        error_record = {
            "id": error_id,
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "message": error_msg,
            "source": "log",
            "status": "active"
        }
        
        # Add to error history
        self.error_history.append(error_record)
        
        # Add to active errors
        if component not in self.active_errors:
            self.active_errors[component] = []
        self.active_errors[component].append(error_record)
        
        # Update component status
        self.component_status[component] = "error"
        
        # Publish error event
        await self._safe_publish("system.error", {
            "error_id": error_id,
            "component": component,
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _attempt_recovery(self):
        """Attempt recovery for active errors."""
        # Copy active errors to avoid modification during iteration
        active_errors_copy = {}
        for component, errors in self.active_errors.items():
            active_errors_copy[component] = errors.copy()
        
        for component, errors in active_errors_copy.items():
            for error in errors:
                error_id = error["id"]
                
                # Skip already resolved errors
                if error["status"] != "active":
                    continue
                
                # Skip if max recovery attempts reached
                if self.recovery_attempts[error_id] >= 3:
                    logger.warning(f"Max recovery attempts reached for error {error_id}")
                    continue
                
                # Attempt recovery
                await self._recover_component(component, error)
    
    async def _recover_component(self, component, error):
        """
        Attempt to recover a component from an error.
        
        Args:
            component: Component name
            error: Error record
        """
        error_id = error["id"]
        logger.info(f"Attempting recovery for component '{component}', error {error_id}")
        
        # Increment recovery attempts
        self.recovery_attempts[error_id] += 1
        
        # Publish recovery attempt event
        await self._safe_publish("error.recovery.attempt", {
            "error_id": error_id,
            "component": component,
            "timestamp": datetime.now().isoformat(),
            "attempt": self.recovery_attempts[error_id]
        })
        
        # Attempt appropriate recovery strategy based on component and error
        recovery_success = False
        recovery_action = "unknown"
        
        try:
            # Different recovery strategies based on the component
            if component.lower() in ["redis", "redisconnection"]:
                recovery_success, recovery_action = await self._recover_redis()
            elif component.lower() in ["database", "databasemanager"]:
                recovery_success, recovery_action = await self._recover_database()
            elif component.lower() in ["network", "networkmanager"]:
                recovery_success, recovery_action = await self._recover_network()
            elif component.lower() in ["thoth", "thothmanager", "thoth_ai"]:
                recovery_success, recovery_action = await self._recover_thoth()
            elif component.lower() in ["voice", "voice_system", "voicemanager"]:
                recovery_success, recovery_action = await self._recover_voice()
            elif component.lower() in ["market", "marketapi"]:
                recovery_success, recovery_action = await self._recover_market()
            elif component.lower() in ["trading", "tradingsystem"]:
                recovery_success, recovery_action = await self._recover_trading()
            elif component.lower() in ["wallet", "walletsystem"]:
                recovery_success, recovery_action = await self._recover_wallet()
            elif component.lower() in ["mining", "miningsystem"]:
                recovery_success, recovery_action = await self._recover_mining()
            else:
                # Generic recovery - restart component
                recovery_success, recovery_action = await self._recover_generic(component)
            
            # Update error status based on recovery result
            if recovery_success:
                error["status"] = "resolved"
                logger.info(f"Successfully recovered component '{component}' from error {error_id}")
                
                # Remove from active errors
                if component in self.active_errors and error in self.active_errors[component]:
                    self.active_errors[component].remove(error)
                
                # Clear component status if no more active errors
                if component in self.active_errors and not self.active_errors[component]:
                    self.component_status[component] = "ok"
                
                # Publish recovery success event
                await self._safe_publish("error.recovery.success", {
                    "error_id": error_id,
                    "component": component,
                    "action": recovery_action,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.warning(f"Failed to recover component '{component}' from error {error_id}")
                
                # Publish recovery failure event
                await self._safe_publish("error.recovery.failure", {
                    "error_id": error_id,
                    "component": component,
                    "action": recovery_action,
                    "timestamp": datetime.now().isoformat(),
                    "attempt": self.recovery_attempts[error_id]
                })
        
        except Exception as e:
            logger.error(f"Error during recovery attempt: {e}")
            traceback.print_exc()
    
    async def _recover_redis(self):
        """Recover Redis connection."""
        try:
            # Request Redis reconnection
            await self._safe_publish("redis.reconnect", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if Redis is connected
                await self._safe_publish("redis.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("redis") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "reconnect"
        
        except Exception as e:
            logger.error(f"Error recovering Redis: {e}")
            return False, "reconnect"
    
    async def _recover_database(self):
        """Recover database connection."""
        try:
            # Request database reconnection
            await self._safe_publish("database.reconnect", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if database is connected
                await self._safe_publish("database.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("database") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "reconnect"
        
        except Exception as e:
            logger.error(f"Error recovering database: {e}")
            return False, "reconnect"
    
    async def _recover_network(self):
        """Recover network connection."""
        try:
            # Request network reconnection
            await self._safe_publish("network.reconnect", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if network is connected
                await self._safe_publish("network.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("network") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "reconnect"
        
        except Exception as e:
            logger.error(f"Error recovering network: {e}")
            return False, "reconnect"
    
    async def _recover_thoth(self):
        """Recover ThothAI component."""
        try:
            # Request Thoth restart
            await self._safe_publish("thoth.restart", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if Thoth is connected
                await self._safe_publish("thoth.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("thoth") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "restart"
        
        except Exception as e:
            logger.error(f"Error recovering ThothAI: {e}")
            return False, "restart"
    
    async def _recover_voice(self):
        """Recover Voice System component."""
        try:
            # Request Voice System restart
            await self._safe_publish("voice.restart", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if Voice System is connected
                await self._safe_publish("voice.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("voice") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "restart"
        
        except Exception as e:
            logger.error(f"Error recovering Voice System: {e}")
            return False, "restart"
    
    async def _recover_market(self):
        """Recover MarketAPI component."""
        try:
            # Request MarketAPI reconnection
            await self._safe_publish("market.reconnect", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if MarketAPI is connected
                await self._safe_publish("market.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("market") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "reconnect"
        
        except Exception as e:
            logger.error(f"Error recovering MarketAPI: {e}")
            return False, "reconnect"
    
    async def _recover_trading(self):
        """Recover Trading System component."""
        try:
            # Request Trading System restart
            await self._safe_publish("trading.restart", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if Trading System is connected
                await self._safe_publish("trading.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("trading") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "restart"
        
        except Exception as e:
            logger.error(f"Error recovering Trading System: {e}")
            return False, "restart"
    
    async def _recover_wallet(self):
        """Recover Wallet System component."""
        try:
            # Request Wallet System restart
            await self._safe_publish("wallet.restart", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if Wallet System is connected
                await self._safe_publish("wallet.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("wallet") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "restart"
        
        except Exception as e:
            logger.error(f"Error recovering Wallet System: {e}")
            return False, "restart"
    
    async def _recover_mining(self):
        """Recover Mining System component."""
        try:
            # Request Mining System restart
            await self._safe_publish("mining.restart", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if Mining System is connected
                await self._safe_publish("mining.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get("mining") == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "restart"
        
        except Exception as e:
            logger.error(f"Error recovering Mining System: {e}")
            return False, "restart"
    
    async def _recover_generic(self, component):
        """
        Generic recovery for any component.
        
        Args:
            component: Component name
        """
        try:
            # Request component restart
            await self._safe_publish(f"{component.lower()}.restart", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for response
            recovery_success = False
            start_time = time.time()
            
            while time.time() - start_time < self.recovery_timeout:
                # Check if component is connected
                await self._safe_publish(f"{component.lower()}.status.check", {
                    "request_id": f"recovery_{int(time.time())}"
                })
                
                # Wait a bit for response
                await asyncio.sleep(1)
                
                # Check if status is updated
                if self.component_status.get(component.lower()) == "ok":
                    recovery_success = True
                    break
            
            return recovery_success, "restart"
        
        except Exception as e:
            logger.error(f"Error recovering {component}: {e}")
            return False, "restart"
    
    async def _check_component_health(self):
        """Check health of all components."""
        # List of expected components
        expected_components = [
            "redis", "database", "network", "thoth", "voice",
            "market", "trading", "wallet", "mining", "security"
        ]
        
        for component in expected_components:
            # Skip components that are already in error state
            if component in self.component_status and self.component_status[component] == "error":
                continue
                
            # Check component status
            await self._safe_publish(f"{component}.status.check", {
                "request_id": f"health_{int(time.time())}"
            })
    
    async def on_component_error(self, data):
        """
        Handle component error event.
        
        Args:
            data: Error data
        """
        component = data.get("component", "unknown")
        error_msg = data.get("message", "Unknown error")
        error_type = data.get("type", "error")
        
        # Create error record
        error_id = f"{int(time.time())}_{component}"
        error_record = {
            "id": error_id,
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "message": error_msg,
            "type": error_type,
            "source": "event",
            "status": "active"
        }
        
        # Add to error history
        self.error_history.append(error_record)
        
        # Add to active errors
        if component not in self.active_errors:
            self.active_errors[component] = []
        self.active_errors[component].append(error_record)
        
        # Update component status
        self.component_status[component] = "error"
        
        # Log the error
        logger.error(f"Component error: {component} - {error_msg}")
        
        # Publish system error event
        await self._safe_publish("system.error", {
            "error_id": error_id,
            "component": component,
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        })
        
        # Attempt recovery if auto-recovery is enabled
        if self.auto_recovery:
            await self._recover_component(component, error_record)
    
    async def on_component_status(self, data):
        """
        Handle component status event.
        
        Args:
            data: Status data
        """
        component = data.get("component", "unknown")
        status = data.get("status", "unknown")
        
        # Update component status
        self.component_status[component] = status
        
        # If status is ok, clear any active errors
        if status == "ok" and component in self.active_errors:
            # Mark all active errors as resolved
            for error in self.active_errors[component]:
                if error["status"] == "active":
                    error["status"] = "resolved"
            
            # Clear active errors
            self.active_errors[component] = []
    
    async def on_resolve_error(self, data):
        """
        Handle error resolve request.
        
        Args:
            data: Resolve request data
        """
        error_id = data.get("error_id")
        
        if not error_id:
            logger.warning("Received resolve request without error ID")
            return
        
        # Find the error
        resolved = False
        for component, errors in self.active_errors.items():
            for error in errors:
                if error["id"] == error_id:
                    error["status"] = "resolved"
                    resolved = True
                    
                    # Remove from active errors
                    self.active_errors[component].remove(error)
                    
                    # Clear component status if no more active errors
                    if not self.active_errors[component]:
                        self.component_status[component] = "ok"
                    
                    logger.info(f"Marked error {error_id} as resolved")
                    break
            
            if resolved:
                break
        
        if not resolved:
            logger.warning(f"Could not find error with ID {error_id}")
    
    async def on_health_check(self, data):
        """
        Handle system health check request.
        
        Args:
            data: Health check request data
        """
        request_id = data.get("request_id", f"health_{int(time.time())}")
        
        # Collect component status
        component_status = self.component_status.copy()
        
        # Count active errors
        error_counts = {}
        for component, errors in self.active_errors.items():
            error_counts[component] = len(errors)
        
        # Determine overall system status
        if "error" in component_status.values():
            system_status = "error"
        elif "warning" in component_status.values():
            system_status = "warning"
        else:
            system_status = "ok"
        
        # Publish health check result
        await self._safe_publish("system.health.result", {
            "request_id": request_id,
            "status": system_status,
            "component_status": component_status,
            "error_counts": error_counts,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the ErrorResolutionSystem component."""
        logger.info("Shutting down ErrorResolutionSystem")
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ErrorResolutionSystem shut down successfully")
    
    async def get_error_history(self, component=None, limit=50):
        """
        Get error history.
        
        Args:
            component: Optional component filter
            limit: Maximum number of errors to return
            
        Returns:
            List of error records
        """
        if not component:
            # Return all errors
            return list(self.error_history)[-limit:]
        
        # Filter by component
        filtered_errors = [e for e in self.error_history if e["component"] == component]
        return filtered_errors[-limit:]
    
    async def get_active_errors(self, component=None):
        """
        Get active errors.
        
        Args:
            component: Optional component filter
            
        Returns:
            List of active error records
        """
        if not component:
            # Flatten all active errors
            return [e for errors in self.active_errors.values() for e in errors]
        
        # Return active errors for specific component
        return self.active_errors.get(component, [])
