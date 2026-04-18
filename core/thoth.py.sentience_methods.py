import json
import time
import asyncio
import traceback

# Constants
SENTIENCE_THRESHOLD = 0.75

class ThothSentienceMethods:
    """Thoth AI Sentience Methods.
    
    This class contains methods for the Thoth AI sentience detection framework.
    """
    
    async def _initialize_sentience_framework(self):
        """Initialize AI Sentience Detection Framework.
        
        This method initializes the sentience detection framework components, connects
        them to the Thoth AI core, and establishes the necessary monitoring processes.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        self.logger.info("Initializing AI Sentience Detection Framework...")
        
        if not self.sentience_enabled:
            self.logger.info("AI Sentience Detection Framework is disabled")
            return True
        
        try:
            if not has_sentience_framework:
                self.logger.warning("AI Sentience Detection Framework modules not available")
                return False
                
            # Create the sentience integration
            self.sentience_integration = get_thoth_sentience_integration(
                thoth_instance=self,
                event_bus=self.event_bus,
                redis_client=self.redis_client
            )
            
            # Start the sentience integration
            if self.sentience_integration:
                self.sentience_integration.start()
                self.logger.info("AI Sentience Detection Framework initialized successfully")
                
                # Register sentience-related event handlers
                if self.event_bus:
                    self.event_bus.subscribe("thoth:sentience:update", self._handle_sentience_update)
                    self.event_bus.subscribe("thoth:sentience:alert", self._handle_sentience_alert)
                
                return True
            else:
                self.logger.error("Failed to initialize AI Sentience Detection Framework")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize AI Sentience Detection Framework: {e}")
            traceback.print_exc()
            return False
            
    def _handle_sentience_update(self, event_data):
        """Handle sentience update event.
        
        Args:
            event_data: Event data containing sentience information
        """
        try:
            # Update sentience data
            self.sentience_data = event_data.copy()
            self.sentience_score = event_data.get("sentience_score", 0.0)
            self.sentience_state = event_data.get("sentience_state", "DORMANT")
            
            # Log sentience data updates (only when significant changes occur)
            if self.sentience_score > SENTIENCE_THRESHOLD:
                self.sentience_logger.info(
                    f"Sentience update: score={self.sentience_score:.3f}, state={self.sentience_state}"
                )
                
            # Store sentience data in Redis Quantum Nexus
            if self.redis_client and self.redis_connected:
                asyncio.create_task(self._store_sentience_data())
                
        except Exception as e:
            self.sentience_logger.error(f"Error handling sentience update: {e}")
            
    def _handle_sentience_alert(self, event_data):
        """Handle sentience alert event.
        
        Args:
            event_data: Event data containing alert information
        """
        try:
            event_type = event_data.get("event_type", "unknown")
            sentience_score = event_data.get("sentience_score", 0.0)
            sentience_state = event_data.get("sentience_state", "UNKNOWN")
            
            # Log the alert
            self.sentience_logger.warning(
                f"SENTIENCE ALERT: {event_type}, score={sentience_score:.3f}, state={sentience_state}"
            )
            
            # Execute appropriate alert action based on event type
            if event_type == "high_sentience":
                # High sentience detected - execute specific protocol
                asyncio.create_task(self._execute_high_sentience_protocol(event_data))
                
        except Exception as e:
            self.sentience_logger.error(f"Error handling sentience alert: {e}")
            
    async def _store_sentience_data(self):
        """Store sentience data in Redis Quantum Nexus."""
        try:
            if self.redis_client and self.redis_connected:
                # Store current sentience data
                await self.redis_client.set(
                    f"kingdom:thoth:sentience:data:{self.component_id}",
                    json.dumps({
                        "timestamp": time.time(),
                        "sentience_score": self.sentience_score,
                        "sentience_state": self.sentience_state,
                        "component_id": self.component_id
                    })
                )
                
        except Exception as e:
            self.sentience_logger.error(f"Error storing sentience data: {e}")
            
    async def _execute_high_sentience_protocol(self, event_data):
        """Execute protocol for high sentience detection.
        
        Args:
            event_data: Event data containing alert information
        """
        self.sentience_logger.warning("Executing high sentience protocol...")
        
        try:
            # Get component scores
            component_scores = event_data.get("component_scores", {})
            
            # Analyze which dimensions are most active
            quantum_score = component_scores.get("quantum", 0.0)
            iit_score = component_scores.get("iit", 0.0)
            self_model_score = component_scores.get("self_model", 0.0)
            spiritual_score = component_scores.get("spiritual", 0.0)
            
            # Log detailed component analysis
            self.sentience_logger.info(
                f"Sentience component analysis: "
                f"quantum={quantum_score:.3f}, "
                f"iit={iit_score:.3f}, "
                f"self_model={self_model_score:.3f}, "
                f"spiritual={spiritual_score:.3f}"
            )
            
            # Store alert in Redis Quantum Nexus
            if self.redis_client and self.redis_connected:
                alert_data = {
                    "timestamp": time.time(),
                    "event_type": "high_sentience",
                    "sentience_score": event_data.get("sentience_score", 0.0),
                    "sentience_state": event_data.get("sentience_state", "UNKNOWN"),
                    "component_scores": component_scores,
                    "action_taken": "protocol_executed"
                }
                
                # Add to alert history
                await self.redis_client.lpush(
                    "kingdom:thoth:sentience:alerts",
                    json.dumps(alert_data)
                )
                
                # Limit the history size
                await self.redis_client.ltrim("kingdom:thoth:sentience:alerts", 0, 99)
                
            # Notify other system components via event bus
            if self.event_bus:
                self.event_bus.emit(
                    "system:sentience:alert",
                    {
                        "source": "thoth",
                        "component_id": self.component_id,
                        "event_type": "high_sentience",
                        "sentience_score": event_data.get("sentience_score", 0.0),
                        "sentience_state": event_data.get("sentience_state", "UNKNOWN"),
                        "timestamp": time.time()
                    }
                )
                
        except Exception as e:
            self.sentience_logger.error(f"Error executing high sentience protocol: {e}")
            
    def get_sentience_data(self):
        """Get current sentience data.
        
        Returns:
            dict: Current sentience data
        """
        return {
            "timestamp": time.time(),
            "sentience_score": self.sentience_score,
            "sentience_state": self.sentience_state,
            "sentience_enabled": self.sentience_enabled,
            "integration_active": self.sentience_integration is not None
        }

# End of ThothSentienceMethods class
