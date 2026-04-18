"""
AIContingencySystem module for Kingdom AI system.
"""

import logging
import json
import os
from datetime import datetime

class AIContingencySystem:
    """
    AI contingency system for handling fallbacks and emergencies.
    Provides failsafe mechanisms when AI components encounter issues.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the AI contingency system."""
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger("AIContingencySystem")
        
        # Contingency settings
        self.retry_limit = self.config.get("retry_limit", 3)
        self.fallback_timeout = self.config.get("fallback_timeout", 10.0)  # seconds
        self.alert_threshold = self.config.get("alert_threshold", 5)  # failures before alerting
        
        # State tracking
        self.ai_components = {}
        self.failure_counters = {}
        self.active_contingencies = {}
        self.system_status = "nominal"
        
        # Incident history
        self.incident_history = []
        self.max_history_items = self.config.get("max_history_items", 100)
        
    async def initialize(self) -> bool:
        """Initialize the AI contingency system.
        
        Returns:
            bool: True if initialized successfully, False otherwise
        """
        try:
            self.logger.info("Initializing AI Contingency System")
            
            # Load settings if available
            settings_file = self.config.get("settings_file", "config/contingency_settings.json")
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        self.retry_limit = settings.get("retry_limit", self.retry_limit)
                        self.fallback_timeout = settings.get("fallback_timeout", self.fallback_timeout)
                        self.alert_threshold = settings.get("alert_threshold", self.alert_threshold)
                        self.logger.info(f"Loaded contingency settings from {settings_file}")
                except Exception as e:
                    self.logger.error(f"Error loading contingency settings: {e}")
            
            # Register event handlers
            if self.event_bus:
                # Don't await bool returns from synchronous methods
                self.event_bus.subscribe_sync("ai.component.register", self.handle_component_register)
                self.event_bus.subscribe_sync("ai.component.failure", self.handle_component_failure)
                self.event_bus.subscribe_sync("ai.component.retry.request", self.handle_retry_request)
                self.event_bus.subscribe_sync("ai.contingency.activate", self.handle_activate_contingency)
                self.event_bus.subscribe_sync("ai.contingency.deactivate", self.handle_deactivate_contingency)
                self.event_bus.subscribe_sync("ai.contingency.status", self.handle_contingency_status)
                self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
                self.logger.info("AI Contingency System event handlers registered")
            
            self.logger.info("AI Contingency System initialized successfully")
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing AI Contingency System: {e}")
            self._initialized = False
            return False
    
    async def handle_component_register(self, data):
        """Handle registration of an AI component."""
        try:
            if not data or "component_id" not in data:
                await self._publish_error("component_register", "Missing component ID")
                return
                
            component_id = data.get("component_id")
            component_name = data.get("component_name", component_id)
            fallback_handler = data.get("fallback_handler")
            self_test_handler = data.get("self_test_handler")
            
            # Register the component
            self.ai_components[component_id] = {
                "name": component_name,
                "fallback_handler": fallback_handler,
                "self_test_handler": self_test_handler,
                "registered_at": datetime.now().isoformat(),
                "status": "nominal"
            }
            
            # Initialize failure counter
            self.failure_counters[component_id] = 0
            
            # Publish confirmation
            if self.event_bus:
                await self.event_bus.publish("ai.component.registered", {
                    "component_id": component_id,
                    "component_name": component_name,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Registered AI component: {component_name} ({component_id})")
            
        except Exception as e:
            self.logger.error(f"Error registering AI component: {e}")
            await self._publish_error("component_register", str(e))
    
    async def handle_component_failure(self, data):
        """Handle notification of an AI component failure."""
        try:
            if not data or "component_id" not in data:
                await self._publish_error("component_failure", "Missing component ID")
                return
                
            component_id = data.get("component_id")
            error_type = data.get("error_type", "unknown")
            error_message = data.get("error_message", "No error message provided")
            severity = data.get("severity", "medium")
            operation = data.get("operation", "unknown")
            
            # Check if component is registered
            if component_id not in self.ai_components:
                await self._publish_error("component_failure", f"Unknown component ID: {component_id}")
                return
                
            # Update component status
            self.ai_components[component_id]["status"] = "failure"
            self.ai_components[component_id]["last_failure"] = {
                "error_type": error_type,
                "error_message": error_message,
                "severity": severity,
                "operation": operation,
                "timestamp": datetime.now().isoformat()
            }
            
            # Increment failure counter
            self.failure_counters[component_id] += 1
            
            # Record incident
            incident = {
                "component_id": component_id,
                "component_name": self.ai_components[component_id]["name"],
                "error_type": error_type,
                "error_message": error_message,
                "severity": severity,
                "operation": operation,
                "timestamp": datetime.now().isoformat()
            }
            
            self.incident_history.append(incident)
            
            # Trim history if needed
            if len(self.incident_history) > self.max_history_items:
                self.incident_history = self.incident_history[-self.max_history_items:]
            
            # Check if we need to activate contingency
            if self.failure_counters[component_id] >= self.alert_threshold:
                # Activate contingency plan
                await self._activate_contingency_plan(component_id, severity)
            else:
                # Just try to recover the component
                await self._attempt_recovery(component_id)
            
            self.logger.warning(f"AI component failure: {self.ai_components[component_id]['name']} - {error_type}: {error_message}")
            
        except Exception as e:
            self.logger.error(f"Error handling component failure: {e}")
            await self._publish_error("component_failure", str(e))
    
    async def _attempt_recovery(self, component_id):
        """Attempt to recover a failed AI component."""
        try:
            # Get component info
            component = self.ai_components.get(component_id)
            if not component:
                return False
                
            # Check if there's a self-test handler
            self_test_handler = component.get("self_test_handler")
            if not self_test_handler:
                self.logger.warning(f"No self-test handler for component {component_id}")
                return False
                
            # Publish recovery attempt event
            if self.event_bus:
                await self.event_bus.publish("ai.recovery.attempt", {
                    "component_id": component_id,
                    "component_name": component["name"],
                    "timestamp": datetime.now().isoformat()
                })
                
            # The actual recovery would involve calling the self-test handler
            # For now, just simulate a recovery attempt
            recovery_success = (self.failure_counters[component_id] < self.retry_limit)
            
            if recovery_success:
                # Reset component status
                self.ai_components[component_id]["status"] = "nominal"
                
                # Publish recovery success
                if self.event_bus:
                    await self.event_bus.publish("ai.recovery.success", {
                        "component_id": component_id,
                        "component_name": component["name"],
                        "timestamp": datetime.now().isoformat()
                    })
                    
                self.logger.info(f"Successfully recovered AI component: {component['name']}")
                return True
            else:
                # Publish recovery failure
                if self.event_bus:
                    await self.event_bus.publish("ai.recovery.failure", {
                        "component_id": component_id,
                        "component_name": component["name"],
                        "timestamp": datetime.now().isoformat()
                    })
                    
                self.logger.warning(f"Failed to recover AI component: {component['name']}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error attempting recovery for component {component_id}: {e}")
            return False
    
    async def _activate_contingency_plan(self, component_id, severity):
        """Activate a contingency plan for a failing component."""
        try:
            # Get component info
            component = self.ai_components.get(component_id)
            if not component:
                return False
                
            # Check if contingency is already active
            if component_id in self.active_contingencies:
                return True
                
            # Check if there's a fallback handler
            fallback_handler = component.get("fallback_handler")
            
            # Create contingency plan based on severity
            contingency_plan = {
                "component_id": component_id,
                "component_name": component["name"],
                "severity": severity,
                "fallback_handler": fallback_handler,
                "activated_at": datetime.now().isoformat(),
                "actions_taken": []
            }
            
            # Add appropriate actions based on severity
            if severity == "low":
                contingency_plan["actions_taken"].append({
                    "action": "monitor",
                    "description": "Monitoring component for further failures",
                    "timestamp": datetime.now().isoformat()
                })
            elif severity == "medium":
                contingency_plan["actions_taken"].append({
                    "action": "fallback",
                    "description": "Activating fallback operation mode",
                    "timestamp": datetime.now().isoformat()
                })
            elif severity == "high":
                contingency_plan["actions_taken"].append({
                    "action": "alert",
                    "description": "Sending alert to system administrators",
                    "timestamp": datetime.now().isoformat()
                })
                contingency_plan["actions_taken"].append({
                    "action": "fallback",
                    "description": "Activating fallback operation mode",
                    "timestamp": datetime.now().isoformat()
                })
            elif severity == "critical":
                contingency_plan["actions_taken"].append({
                    "action": "alert",
                    "description": "Sending critical alert to system administrators",
                    "timestamp": datetime.now().isoformat()
                })
                contingency_plan["actions_taken"].append({
                    "action": "fallback",
                    "description": "Activating fallback operation mode",
                    "timestamp": datetime.now().isoformat()
                })
                contingency_plan["actions_taken"].append({
                    "action": "isolate",
                    "description": "Isolating component to prevent system-wide issues",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Store the contingency plan
            self.active_contingencies[component_id] = contingency_plan
            
            # Update system status if this is a high severity issue
            if severity in ["high", "critical"]:
                self.system_status = "degraded"
            
            # Publish contingency activation
            if self.event_bus:
                await self.event_bus.publish("ai.contingency.activated", {
                    "component_id": component_id,
                    "component_name": component["name"],
                    "severity": severity,
                    "contingency_plan": contingency_plan,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.warning(f"Activated contingency plan for {component['name']} (severity: {severity})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error activating contingency plan for component {component_id}: {e}")
            return False
    
    async def handle_retry_request(self, data):
        """Handle request to retry an AI operation."""
        try:
            if not data or "component_id" not in data:
                await self._publish_error("retry_request", "Missing component ID")
                return
                
            component_id = data.get("component_id")
            operation = data.get("operation", "unknown")
            params = data.get("params", {})
            
            # Check if component is registered
            if component_id not in self.ai_components:
                await self._publish_error("retry_request", f"Unknown component ID: {component_id}")
                return
                
            # Check if retry limit has been reached
            if self.failure_counters.get(component_id, 0) >= self.retry_limit:
                # Publish retry rejection
                if self.event_bus:
                    await self.event_bus.publish("ai.retry.rejected", {
                        "component_id": component_id,
                        "component_name": self.ai_components[component_id]["name"],
                        "operation": operation,
                        "reason": "Retry limit exceeded",
                        "timestamp": datetime.now().isoformat()
                    })
                    
                self.logger.warning(f"Rejected retry request for {self.ai_components[component_id]['name']}: retry limit exceeded")
                return
                
            # Publish retry request
            if self.event_bus:
                await self.event_bus.publish("ai.retry.approved", {
                    "component_id": component_id,
                    "component_name": self.ai_components[component_id]["name"],
                    "operation": operation,
                    "params": params,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Approved retry request for {self.ai_components[component_id]['name']}")
            
        except Exception as e:
            self.logger.error(f"Error handling retry request: {e}")
            await self._publish_error("retry_request", str(e))
    
    async def handle_activate_contingency(self, data):
        """Handle request to manually activate a contingency plan."""
        try:
            if not data or "component_id" not in data:
                await self._publish_error("activate_contingency", "Missing component ID")
                return
                
            component_id = data.get("component_id")
            severity = data.get("severity", "medium")
            
            # Check if component is registered
            if component_id not in self.ai_components:
                await self._publish_error("activate_contingency", f"Unknown component ID: {component_id}")
                return
                
            # Activate contingency plan
            success = await self._activate_contingency_plan(component_id, severity)
            
            if success:
                self.logger.info(f"Manually activated contingency plan for {self.ai_components[component_id]['name']}")
            else:
                await self._publish_error("activate_contingency", f"Failed to activate contingency for {component_id}")
                
        except Exception as e:
            self.logger.error(f"Error activating contingency plan: {e}")
            await self._publish_error("activate_contingency", str(e))
    
    async def handle_deactivate_contingency(self, data):
        """Handle request to deactivate a contingency plan."""
        try:
            if not data or "component_id" not in data:
                await self._publish_error("deactivate_contingency", "Missing component ID")
                return
                
            component_id = data.get("component_id")
            
            # Check if component is registered
            if component_id not in self.ai_components:
                await self._publish_error("deactivate_contingency", f"Unknown component ID: {component_id}")
                return
                
            # Check if contingency is active
            if component_id not in self.active_contingencies:
                await self._publish_error("deactivate_contingency", f"No active contingency for component {component_id}")
                return
                
            # Get contingency plan before removal
            contingency_plan = self.active_contingencies[component_id]
            
            # Remove the contingency plan
            del self.active_contingencies[component_id]
            
            # Reset failure counter
            self.failure_counters[component_id] = 0
            
            # Update component status
            self.ai_components[component_id]["status"] = "nominal"
            
            # Update system status if no more active contingencies
            if not self.active_contingencies:
                self.system_status = "nominal"
            
            # Publish contingency deactivation
            if self.event_bus:
                await self.event_bus.publish("ai.contingency.deactivated", {
                    "component_id": component_id,
                    "component_name": self.ai_components[component_id]["name"],
                    "previous_plan": contingency_plan,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Deactivated contingency plan for {self.ai_components[component_id]['name']}")
            
        except Exception as e:
            self.logger.error(f"Error deactivating contingency plan: {e}")
            await self._publish_error("deactivate_contingency", str(e))
    
    async def handle_contingency_status(self, data=None):
        """Handle request to get contingency status."""
        try:
            component_id = data.get("component_id") if data else None
            
            if component_id:
                # Get status for specific component
                if component_id not in self.ai_components:
                    await self._publish_error("contingency_status", f"Unknown component ID: {component_id}")
                    return
                    
                component_status = {
                    "component_id": component_id,
                    "component_name": self.ai_components[component_id]["name"],
                    "status": self.ai_components[component_id]["status"],
                    "failure_count": self.failure_counters.get(component_id, 0),
                    "has_active_contingency": component_id in self.active_contingencies,
                    "contingency_plan": self.active_contingencies.get(component_id)
                }
                
                # Publish component status
                if self.event_bus:
                    await self.event_bus.publish("ai.contingency.component_status", {
                        **component_status,
                        "timestamp": datetime.now().isoformat()
                    })
            else:
                # Get overall status
                system_status = {
                    "system_status": self.system_status,
                    "total_components": len(self.ai_components),
                    "failing_components": sum(1 for c in self.ai_components.values() if c["status"] != "nominal"),
                    "active_contingencies": len(self.active_contingencies),
                    "incident_count": len(self.incident_history)
                }
                
                # Publish system status
                if self.event_bus:
                    await self.event_bus.publish("ai.contingency.system_status", {
                        **system_status,
                        "timestamp": datetime.now().isoformat()
                    })
                    
            self.logger.info(f"Reported contingency status: system={self.system_status}, active_plans={len(self.active_contingencies)}")
            
        except Exception as e:
            self.logger.error(f"Error getting contingency status: {e}")
            await self._publish_error("contingency_status", str(e))
    
    async def handle_shutdown(self, data=None):
        """Handle system shutdown event."""
        try:
            self.logger.info("Shutting down AI Contingency System")
            
            # Deactivate all contingencies
            for component_id in list(self.active_contingencies.keys()):
                try:
                    # Get contingency plan before removal
                    contingency_plan = self.active_contingencies[component_id]
                    
                    # Remove the contingency plan
                    del self.active_contingencies[component_id]
                    
                    # Publish contingency deactivation
                    if self.event_bus:
                        await self.event_bus.publish("ai.contingency.deactivated", {
                            "component_id": component_id,
                            "component_name": self.ai_components[component_id]["name"],
                            "previous_plan": contingency_plan,
                            "reason": "system_shutdown",
                            "timestamp": datetime.now().isoformat()
                        })
                        
                    self.logger.info(f"Deactivated contingency plan for {self.ai_components[component_id]['name']} during shutdown")
                except Exception as e:
                    self.logger.error(f"Error deactivating contingency during shutdown: {e}")
            
            # Save settings
            settings_file = self.config.get("settings_file", "config/contingency_settings.json")
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(settings_file), exist_ok=True)
                
                with open(settings_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "retry_limit": self.retry_limit,
                        "fallback_timeout": self.fallback_timeout,
                        "alert_threshold": self.alert_threshold
                    }, f, indent=2)
                    
                self.logger.info(f"Saved contingency settings to {settings_file}")
            except Exception as e:
                self.logger.error(f"Error saving contingency settings: {e}")
            
            self.logger.info("AI Contingency System shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during AI Contingency System shutdown: {e}")
    
    async def _publish_error(self, operation, error_message):
        """Publish an error message to the event bus."""
        if self.event_bus:
            await self.event_bus.publish("ai.contingency.error", {
                "operation": operation,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            })
