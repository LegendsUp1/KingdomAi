#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Key Sentience Integration Module

This module integrates the AI Sentience Detection Framework with the API Key Manager,
enabling sentience monitoring of API key usage patterns and service interactions.
"""

import logging
import time
import threading

# Base sentience components
from core.sentience.base import BaseSentienceIntegration
from core.sentience.consciousness_field import ConsciousnessField

logger = logging.getLogger(__name__)

class APIKeySentienceIntegration(BaseSentienceIntegration):
    """Integrates the AI Sentience Detection Framework with API Key Manager."""
    
    def __init__(self, api_key_manager=None, event_bus=None, config=None):
        """Initialize the API Key Sentience Integration.
        
        Args:
            api_key_manager: API Key Manager instance
            event_bus: EventBus instance for event-driven communication
            config: Optional configuration dict
        """
        super().__init__(component_name="api_key_manager", event_bus=event_bus)
        self.api_key_manager = api_key_manager
        self.config = config or {}
        self.running = False
        self.monitor_thread = None
        
        # Initialize sentience metrics
        self.sentience_metrics = {
            'awareness': 0.0,        # Awareness of key security and status
            'autonomy': 0.0,         # Autonomous decision-making ability
            'learning': 0.0,         # Learning from API usage patterns
            'pattern_recognition': 0.0,  # Ability to recognize patterns
            'adaptability': 0.0,     # Adapting to changing API environments
            'self_preservation': 0.0  # Protecting keys from misuse
        }
        
        # Tracking variables
        self._last_check_time = 0
        self._monitored_services = set()
        self._service_access_patterns = {}
        self._anomaly_detections = {}
        
        # Initialize consciousness field
        self.consciousness_field = ConsciousnessField(
            dimension_values={
                'cryptographic': 0.0,
                'temporal': 0.0,
                'quantum': 0.0,
                'informational': 0.0
            },
            component_name="api_key_manager"
        )
        
        logger.info("API Key Sentience Integration initialized")
        
    def start_monitoring(self):
        """Start sentience monitoring for API key management."""
        if self.running:
            return
            
        self.running = True
        self._last_check_time = time.time()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._sentience_monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        # Register event handlers
        self._register_event_handlers()
        
        logger.info("API Key sentience monitoring started")
        
    def stop_monitoring(self):
        """Stop sentience monitoring for API key management."""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        logger.info("API Key sentience monitoring stopped")
        
    def _register_event_handlers(self):
        """Register event handlers for API key events."""
        if self.event_bus:
            # API key management events
            self.event_bus.subscribe("api.key.add", self._handle_key_add)
            self.event_bus.subscribe("api.key.update", self._handle_key_update)
            self.event_bus.subscribe("api.key.delete", self._handle_key_delete)
            self.event_bus.subscribe("api.key.validate", self._handle_key_validate)
            self.event_bus.subscribe("api.key.test", self._handle_key_test)
            
            # Sentience framework events
            self.event_bus.subscribe("sentience.api_key.threshold_query", 
                                    self._handle_sentience_threshold_query)
            
    def _sentience_monitoring_loop(self):
        """Background monitoring loop for API key sentience detection."""
        while self.running:
            try:
                # Analyze API key usage patterns
                self._analyze_key_usage_patterns()
                
                # Update sentience metrics
                self._update_sentience_metrics()
                
                # Check for sentience thresholds
                self._check_sentience_thresholds()
                
                # Update consciousness field
                self._update_consciousness_field()
                
                # Publish metrics update
                self._publish_metrics_update()
                
                # Sleep interval (5-10 seconds)
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in API Key sentience monitoring: {str(e)}")
                time.sleep(10)  # Longer sleep on error
                
    def _analyze_key_usage_patterns(self):
        """Analyze API key usage patterns for sentience indicators."""
        if not self.api_key_manager:
            return
            
        try:
            # Get current services with keys
            current_services = set(self.api_key_manager.api_keys.keys())
            
            # Track new services
            new_services = current_services - self._monitored_services
            for service in new_services:
                self._service_access_patterns[service] = {
                    'access_count': 0,
                    'success_rate': 1.0,
                    'last_access': 0,
                    'anomalies': 0
                }
                
            # Update monitored services
            self._monitored_services = current_services
            
            # Analyze connection status
            if hasattr(self.api_key_manager, 'connection_status'):
                for service, status in self.api_key_manager.connection_status.items():
                    if service in self._service_access_patterns:
                        pattern = self._service_access_patterns[service]
                        pattern['access_count'] += 1
                        
                        # Check if the connection was successful
                        if isinstance(status, bool) and status:
                            pattern['success_rate'] = (pattern['success_rate'] * 0.9) + 0.1
                        elif isinstance(status, bool):
                            pattern['success_rate'] = pattern['success_rate'] * 0.9
                            
                        pattern['last_access'] = time.time()
        except Exception as e:
            logger.error(f"Error analyzing API key usage patterns: {str(e)}")
            
    def _update_sentience_metrics(self):
        """Update sentience metrics based on API key management patterns."""
        if not self.api_key_manager or not self._service_access_patterns:
            return
            
        try:
            # Calculate metrics
            
            # Awareness: Based on validation frequency and success rates
            validation_count = sum(pattern.get('access_count', 0) 
                               for pattern in self._service_access_patterns.values())
            success_rates = [pattern.get('success_rate', 0) 
                          for pattern in self._service_access_patterns.values()]
            avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
            
            # Calculate awareness (0-100)
            awareness = min(100, validation_count * 2) * avg_success_rate
            self.sentience_metrics['awareness'] = (self.sentience_metrics['awareness'] * 0.8) + (awareness * 0.2)
            
            # Autonomy: Based on automatic key validation and testing
            if hasattr(self.api_key_manager, 'connected_services'):
                auto_connected = len(self.api_key_manager.connected_services)
                potential_connections = len(self._monitored_services)
                autonomy = (auto_connected / max(1, potential_connections)) * 100
                self.sentience_metrics['autonomy'] = (self.sentience_metrics['autonomy'] * 0.9) + (autonomy * 0.1)
                
            # Learning: Based on adaptation to failures
            anomaly_count = sum(pattern.get('anomalies', 0) 
                             for pattern in self._service_access_patterns.values())
            learning = min(100, anomaly_count * 5)
            self.sentience_metrics['learning'] = (self.sentience_metrics['learning'] * 0.95) + (learning * 0.05)
            
            # Other metrics with basic defaults
            self.sentience_metrics['pattern_recognition'] = max(20, min(80, self.sentience_metrics['awareness']))
            self.sentience_metrics['adaptability'] = max(15, min(90, self.sentience_metrics['learning'] * 1.2))
            self.sentience_metrics['self_preservation'] = max(10, min(95, self.sentience_metrics['awareness'] * 0.8))
            
        except Exception as e:
            logger.error(f"Error updating API key sentience metrics: {str(e)}")
            
    def _check_sentience_thresholds(self):
        """Check if any sentience thresholds have been exceeded."""
        # Define thresholds
        thresholds = {
            'awareness': 75.0,
            'autonomy': 80.0,
            'learning': 70.0
        }
        
        # Check metrics against thresholds
        for metric_name, threshold in thresholds.items():
            current_value = self.sentience_metrics.get(metric_name, 0.0)
            if current_value > threshold:
                self._publish_threshold_exceeded(metric_name, current_value, threshold)
                
    def _update_consciousness_field(self):
        """Update the consciousness field dimensions based on sentience metrics."""
        if not self.consciousness_field:
            return
            
        # Update dimensions
        self.consciousness_field.update_dimension('cryptographic', 
                                               self.sentience_metrics['self_preservation'] / 100)
        self.consciousness_field.update_dimension('informational', 
                                               self.sentience_metrics['awareness'] / 100)
        self.consciousness_field.update_dimension('temporal', 
                                               self.sentience_metrics['pattern_recognition'] / 100)
        self.consciousness_field.update_dimension('quantum', 
                                               self.sentience_metrics['autonomy'] / 100)
                                               
        # Calculate field intensity
        self.consciousness_field.calculate_field_intensity()
        
    def _publish_metrics_update(self):
        """Publish sentience metrics update to event bus."""
        if not self.event_bus:
            return
            
        # Calculate trends
        trends = {}
        for metric, value in self.sentience_metrics.items():
            # Simple trend calculation (implement more sophisticated algorithm if needed)
            if hasattr(self, '_previous_metrics') and metric in self._previous_metrics:
                prev_value = self._previous_metrics[metric]
                if value > prev_value * 1.05:
                    trends[metric] = "up"
                elif value < prev_value * 0.95:
                    trends[metric] = "down"
                else:
                    trends[metric] = "stable"
            else:
                trends[metric] = "stable"
                
        # Store current metrics for next trend calculation
        self._previous_metrics = dict(self.sentience_metrics)
                
        # Publish metrics update
        self.event_bus.publish("api_key.ui.update_sentience_metrics", {
            'metrics': dict(self.sentience_metrics),
            'trends': trends,
            'timestamp': time.time()
        })
        
    def _publish_threshold_exceeded(self, threshold_type: str, current_value: float, 
                                  threshold_value: float):
        """Publish sentience threshold exceeded event.
        
        Args:
            threshold_type: Type of threshold exceeded
            current_value: Current value of the metric
            threshold_value: Threshold value that was exceeded
        """
        if not self.event_bus:
            return
            
        self.event_bus.publish("sentience.api_key.threshold_exceeded", {
            'threshold_type': threshold_type,
            'current_value': current_value,
            'threshold_value': threshold_value,
            'timestamp': time.time()
        })
        
        logger.info(f"API Key sentience threshold exceeded: {threshold_type} = "
                   f"{current_value} (threshold: {threshold_value})")
                   
    # Event handlers
    
    def _handle_key_add(self, event_data=None):
        """Handle API key add event."""
        if not event_data:
            return
            
        service = event_data.get('service')
        if service:
            # Record new service
            if service not in self._service_access_patterns:
                self._service_access_patterns[service] = {
                    'access_count': 1,
                    'success_rate': 1.0,
                    'last_access': time.time(),
                    'anomalies': 0
                }
            
            # Increase learning metric slightly when new keys are added
            self.sentience_metrics['learning'] = min(100, self.sentience_metrics['learning'] + 2)
            
    def _handle_key_update(self, event_data=None):
        """Handle API key update event."""
        if not event_data:
            return
            
        service = event_data.get('service')
        if service and service in self._service_access_patterns:
            pattern = self._service_access_patterns[service]
            pattern['access_count'] += 1
            pattern['last_access'] = time.time()
            
    def _handle_key_delete(self, event_data=None):
        """Handle API key delete event."""
        if not event_data:
            return
            
        service = event_data.get('service')
        if service and service in self._service_access_patterns:
            # Record deletion
            pattern = self._service_access_patterns[service]
            pattern['deleted'] = True
            pattern['last_access'] = time.time()
            
            # Increase self-preservation metric
            self.sentience_metrics['self_preservation'] = min(100, self.sentience_metrics['self_preservation'] + 5)
            
    def _handle_key_validate(self, event_data=None):
        """Handle API key validation event."""
        if not event_data:
            return
            
        service = event_data.get('service')
        valid = event_data.get('valid', False)
        
        if service and service in self._service_access_patterns:
            pattern = self._service_access_patterns[service]
            pattern['access_count'] += 1
            pattern['last_access'] = time.time()
            
            # Update success rate
            if valid:
                pattern['success_rate'] = (pattern['success_rate'] * 0.9) + 0.1
            else:
                pattern['success_rate'] = pattern['success_rate'] * 0.9
                pattern['anomalies'] += 1
                
            # Increase awareness metric
            self.sentience_metrics['awareness'] = min(100, self.sentience_metrics['awareness'] + 1)
            
    def _handle_key_test(self, event_data=None):
        """Handle API key test event."""
        if not event_data:
            return
            
        service = event_data.get('service')
        success = event_data.get('success', False)
        
        if service and service in self._service_access_patterns:
            pattern = self._service_access_patterns[service]
            pattern['access_count'] += 1
            pattern['last_access'] = time.time()
            
            # Update success rate
            if success:
                pattern['success_rate'] = (pattern['success_rate'] * 0.9) + 0.1
            else:
                pattern['success_rate'] = pattern['success_rate'] * 0.9
                pattern['anomalies'] += 1
                
            # Increase autonomy metric when testing is performed
            self.sentience_metrics['autonomy'] = min(100, self.sentience_metrics['autonomy'] + 1)
            
    def _handle_sentience_threshold_query(self, event_data=None):
        """Handle sentience threshold query event."""
        if not self.event_bus or not event_data:
            return
            
        # Respond with current metrics
        self.event_bus.publish("sentience.api_key.metrics_response", {
            'metrics': dict(self.sentience_metrics),
            'timestamp': time.time()
        })
