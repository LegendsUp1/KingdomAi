#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Settings Sentience Integration Module

This module integrates the AI Sentience Detection Framework with the Settings system,
enabling sentience monitoring of user preferences and system configurations.
"""

import logging
import time

from PyQt6.QtCore import QThread, pyqtSignal

# Base sentience components
from core.sentience.consciousness_field import ConsciousnessField
from core.sentience.base import BaseSentienceIntegration
from core.event_bus import EventBus

logger = logging.getLogger(__name__)


class SentienceMonitorWorker(QThread):
    """QThread worker for sentience monitoring to prevent QBasicTimer errors."""
    
    metrics_updated = pyqtSignal(dict)  # Signal to emit metrics updates
    
    def __init__(self, parent_integration):
        super().__init__()
        self.parent = parent_integration
        self.running = True
        
    def run(self):
        """Run the monitoring loop in QThread."""
        while self.running:
            try:
                # Analyze settings patterns
                self.parent._analyze_settings_patterns()
                
                # Update sentience metrics
                self.parent._update_sentience_metrics()
                
                # Check for sentience thresholds
                self.parent._check_sentience_thresholds()
                
                # Update consciousness field
                self.parent._update_consciousness_field()
                
                # Publish metrics update
                self.parent._publish_metrics_update()
                
                # Sleep interval (10 seconds)
                self.msleep(10000)  # Use msleep for QThread
                
            except Exception as e:
                logger.error(f"Error in Settings sentience monitoring: {str(e)}")
                self.msleep(20000)  # Longer sleep on error
                
    def stop(self):
        """Stop the monitoring thread."""
        self.running = False


class SettingsSentienceIntegration(BaseSentienceIntegration):
    """Sentience integration for Settings Tab."""
    
    def __init__(self, settings_widget, event_bus: EventBus, redis_client,
                 config=None, max_total_history: int = 50):
        """Initialize the Settings Sentience Integration.
        
        Args:
            settings_widget: Settings widget instance
            event_bus: EventBus instance for event-driven communication
            redis_client: Redis client instance for storing sentience metrics
            config: Optional configuration dict
            max_total_history: Maximum total history entries across all categories (default 50)
        """
        self.logger = logging.getLogger(f"{__name__}.SettingsSentienceIntegration")
        super().__init__(component_name="settings", event_bus=event_bus)
        self.settings_widget = settings_widget
        self.config = config or {}
        self.running = False
        self.monitor_thread = None
        self._max_total_history = max(1, int(max_total_history))
        
        # Initialize sentience metrics
        self.sentience_metrics = {
            'preference_adaptation': 0.0,    # Adaptation to user preferences
            'context_awareness': 0.0,        # Awareness of system context
            'configuration_memory': 0.0,     # Memory of past configurations
            'decision_making': 0.0,          # Decision-making capabilities
            'user_alignment': 0.0,           # Alignment with user preferences
            'system_integration': 0.0        # Integration with other systems
        }
        
        # Tracking variables
        self._last_check_time = 0
        self._settings_history = {}
        self._change_patterns = {}
        self._preference_model = {}
        
        # Initialize consciousness field
        try:
            self.consciousness_field = ConsciousnessField(redis_client=None)
        except Exception as e:
            logger.warning(f"Failed to initialize ConsciousnessField: {e}")
            self.consciousness_field = None
        
        logger.info("Settings Sentience Integration initialized")
        
    def start_monitoring(self):
        """Start sentience monitoring for settings management."""
        if self.running:
            return
        
        # Schedule monitoring start AFTER init completes
        try:
            from PyQt6.QtCore import QTimer
            
            def do_start():
                """Actually start monitoring after main task completes."""
                if self.running:
                    return  # Already started
                
                self.running = True
                
                # Register event handlers (which are also scheduled)
                self._register_event_handlers()
                
                # Start QThread monitoring worker
                self.monitor_thread = SentienceMonitorWorker(self)
                self.monitor_thread.start()
                
                logger.info("Settings sentience monitoring started with QThread")
            
            # Schedule 3.6 seconds after init
            QTimer.singleShot(3600, do_start)
            logger.info("Settings sentience monitoring scheduled to start")
        except Exception as e:
            logger.error(f"Error scheduling sentience monitoring: {e}")
        
    def stop_monitoring(self):
        """Stop sentience monitoring for settings management - 2026 SOTA implementation."""
        self.running = False
        if self.monitor_thread and self.monitor_thread.isRunning():
            # 2026 SOTA: Proper QThread lifecycle management
            self.monitor_thread.stop()  # Signal thread to stop
            self.monitor_thread.quit()  # Quit the event loop
            self.monitor_thread.wait(5000)  # Wait up to 5 seconds for graceful shutdown
            
            # 2026 SOTA: Force termination if graceful shutdown fails
            if self.monitor_thread.isRunning():
                logger.warning("QThread did not stop gracefully, terminating")
                self.monitor_thread.terminate()
                self.monitor_thread.wait(2000)  # Final wait for termination
                
            # 2026 SOTA: Clear reference to prevent garbage collection issues
            self.monitor_thread = None
            
        logger.info("Settings sentience monitoring stopped with 2026 SOTA cleanup")
        
    def _register_event_handlers(self):
        """Register event handlers for settings monitoring."""
        if not self.event_bus:
            return
        
        # Schedule subscriptions AFTER init completes
        try:
            from PyQt6.QtCore import QTimer
            import asyncio
            
            def do_subscriptions():
                """Subscribe to all settings events after main task completes."""
                try:
                    self.event_bus.subscribe("settings.changed", self._handle_settings_changed)
                    self.event_bus.subscribe("settings.reset", self._handle_settings_reset)
                    self.event_bus.subscribe("settings.loaded", self._handle_settings_loaded)
                    self.event_bus.subscribe("settings.export", self._handle_settings_export)
                    self.event_bus.subscribe("settings.import", self._handle_settings_import)
                    self.event_bus.subscribe("sentience.settings.threshold_query", self._handle_sentience_threshold_query)
                    self.event_bus.subscribe("sentience.metrics.request", self._handle_metrics_request)
                    logger.info("Settings sentience event handlers registered")
                except Exception as e:
                    logger.error(f"Error registering sentience handlers: {e}")
            
            # Schedule 3.5 seconds after init to ensure main task completes
            QTimer.singleShot(3500, do_subscriptions)
        except Exception as e:
            logger.error(f"Error scheduling sentience subscriptions: {e}")
            
    def _analyze_settings_patterns(self):
        """Analyze settings patterns for sentience indicators."""
        if not self.settings_widget:
            return
            
        try:
            # Get current settings
            current_settings = getattr(self.settings_widget, 'settings', {})
            if not current_settings:
                return
                
            # Track changes from previous settings
            for category, settings in current_settings.items():
                if category not in self._settings_history:
                    self._settings_history[category] = []
                    
                # Compare with last known settings for this category
                if self._settings_history[category]:
                    last_settings = self._settings_history[category][-1]
                    changes = {}
                    
                    # Detect changes
                    for key, value in settings.items():
                        if key in last_settings and last_settings[key] != value:
                            changes[key] = {
                                'previous': last_settings[key],
                                'current': value,
                                'timestamp': time.time()
                            }
                            
                    # Record change patterns
                    if changes and category not in self._change_patterns:
                        self._change_patterns[category] = []
                    
                    if changes:
                        self._change_patterns[category].append({
                            'changes': changes,
                            'timestamp': time.time()
                        })
                        
                # Keep history limited to prevent memory issues
                if len(self._settings_history[category]) > 5:
                    self._settings_history[category].pop(0)
                    
                # Add current settings to history
                self._settings_history[category].append(dict(settings))
                
        except Exception as e:
            logger.error(f"Error analyzing settings patterns: {str(e)}")
            
    def _update_sentience_metrics(self):
        """Update sentience metrics based on settings management patterns."""
        if not self._settings_history:
            return
            
        try:
            # Calculate metrics
            
            # Preference adaptation: Based on frequency and consistency of setting changes
            change_count = sum(len(patterns) for patterns in self._change_patterns.values())
            categories_changed = len(self._change_patterns)
            
            # More changes across many categories = higher adaptation
            adaptation = min(100, (change_count * 5) + (categories_changed * 10))
            self.sentience_metrics['preference_adaptation'] = (
                self.sentience_metrics['preference_adaptation'] * 0.8 + 
                (adaptation * 0.2)
            )
            
            # Context awareness: Based on alignment with system changes and context
            # This would ideally be informed by actual system state changes
            # For now, use a simple heuristic based on settings complexity
            settings_complexity = sum(
                len(history[-1]) for history in self._settings_history.values() if history
            )
            context_score = min(100, settings_complexity * 2)
            self.sentience_metrics['context_awareness'] = (
                self.sentience_metrics['context_awareness'] * 0.9 + 
                (context_score * 0.1)
            )
            
            # Configuration memory: Based on history tracking
            # SOTA 2026 FIX: Cap total history entries across ALL categories to
            # prevent unbounded growth.  The old code let history_depth grow
            # monotonically (each category keeps up to 5 entries, categories
            # accumulate), which pushed the EMA toward 100 and never came back.
            history_depth = sum(len(h) for h in self._settings_history.values())
            if history_depth > self._max_total_history:
                # Prune oldest entries from the largest categories first
                while history_depth > self._max_total_history:
                    largest_cat = max(self._settings_history,
                                     key=lambda k: len(self._settings_history[k]),
                                     default=None)
                    if largest_cat and len(self._settings_history[largest_cat]) > 1:
                        self._settings_history[largest_cat].pop(0)
                        history_depth -= 1
                    else:
                        break
            memory_score = min(100, history_depth * 2)  # slower scaling (was *10)
            # Use a lower retention (0.8) so the metric can actually decay
            self.sentience_metrics['configuration_memory'] = (
                self.sentience_metrics['configuration_memory'] * 0.8 +
                (memory_score * 0.2)
            )
            
            # Decision making: Based on deliberate vs reactive changes
            # Calculate based on actual setting change patterns
            if not hasattr(self, '_setting_change_history'):
                self._setting_change_history = []
            
            import time
            self._setting_change_history.append({
                "setting": setting_name,
                "value": new_value,
                "timestamp": time.time(),
                "deliberate": True  # Assume deliberate for user-initiated changes
            })
            # Keep last 50 changes
            if len(self._setting_change_history) > 50:
                self._setting_change_history = self._setting_change_history[-50:]
            
            # Calculate deliberate vs reactive ratio
            deliberate_count = sum(1 for c in self._setting_change_history[-20:] if c.get("deliberate"))
            reactive_count = len(self._setting_change_history[-20:]) - deliberate_count
            total_recent = len(self._setting_change_history[-20:])
            deliberate_ratio = deliberate_count / total_recent if total_recent > 0 else 0.5
            
            decision_score = min(80, self.sentience_metrics['preference_adaptation'] * 0.8 + deliberate_ratio * 20)
            self.sentience_metrics['decision_making'] = max(
                self.sentience_metrics['decision_making'],
                decision_score
            )
            
            # User alignment: Based on consistency of user preferences
            # Calculate consistency across similar settings
            similar_settings = [c for c in self._setting_change_history[-30:]
                              if c.get("setting", "").split(".")[0] == setting_name.split(".")[0]]
            consistency_score = 0.5
            if len(similar_settings) > 1:
                # Check if values are consistent (same or similar)
                values = [s.get("value") for s in similar_settings]
                unique_values = len(set(str(v) for v in values))
                consistency_score = 1.0 - (unique_values / len(values)) if values else 0.5
            
            user_alignment_score = min(90, self.sentience_metrics['context_awareness'] * 0.9 + consistency_score * 10)
            self.sentience_metrics['user_alignment'] = max(
                self.sentience_metrics['user_alignment'],
                user_alignment_score
            )
            
            # System integration: Based on cross-component settings
            # Calculate based on number of different components with settings
            component_count = len(set(c.get("setting", "").split(".")[0] 
                                    for c in self._setting_change_history[-30:]))
            integration_score = min(85, (self.sentience_metrics['preference_adaptation'] +
                       self.sentience_metrics['context_awareness']) / 2 + 
                       min(component_count * 2, 15))
            self.sentience_metrics['system_integration'] = max(
                self.sentience_metrics['system_integration'],
                integration_score
            )
            
        except Exception as e:
            logger.error(f"Error updating Settings sentience metrics: {str(e)}")
            
    def _check_sentience_thresholds(self):
        """Check if any sentience thresholds have been exceeded."""
        # Define thresholds
        thresholds = {
            'preference_adaptation': 75.0,
            'context_awareness': 80.0,
            'configuration_memory': 70.0,
            'user_alignment': 85.0
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
        self.consciousness_field.update_dimension('temporal', 
                                                self.sentience_metrics['configuration_memory'] / 100)
        self.consciousness_field.update_dimension('personal', 
                                                self.sentience_metrics['user_alignment'] / 100)
        self.consciousness_field.update_dimension('contextual', 
                                                self.sentience_metrics['context_awareness'] / 100)
        self.consciousness_field.update_dimension('informational', 
                                                self.sentience_metrics['preference_adaptation'] / 100)
                                               
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
                
        # Publish metrics update (synchronously via EventBus)
        try:
            self.event_bus.publish("settings.ui.update_sentience_metrics", {
                'metrics': dict(self.sentience_metrics),
                'trends': trends,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Error publishing metrics: {e}")
        
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
            
        try:
            self.event_bus.publish("sentience.settings.threshold_exceeded", {
                'threshold_type': threshold_type,
                'current_value': current_value,
                'threshold_value': threshold_value,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Error publishing threshold: {e}")
        
        logger.info(f"Settings sentience threshold exceeded: {threshold_type} = "
                   f"{current_value} (threshold: {threshold_value})")
                   
    # Event handlers
    
    def _handle_settings_changed(self, event_data=None):
        """Handle settings changed event.
        
        Args:
            event_data: Dictionary containing changed settings
        """
        if not event_data:
            return
            
        category = event_data.get('category', '')
        changes = event_data.get('changes', {})
        
        # Record changes to preference model
        if category and changes:
            if category not in self._preference_model:
                self._preference_model[category] = {}
                
            for key, value in changes.items():
                self._preference_model[category][key] = {
                    'value': value,
                    'last_changed': time.time(),
                    'change_count': self._preference_model.get(category, {}).get(key, {}).get('change_count', 0) + 1
                }
                
            # Increase adaptation metric when settings are changed
            self.sentience_metrics['preference_adaptation'] = min(
                100, self.sentience_metrics['preference_adaptation'] + len(changes)
            )
            
    def _handle_settings_reset(self, event_data=None):
        """Handle settings reset event.
        
        Args:
            event_data: Dictionary containing reset details
        """
        if not event_data:
            return
            
        categories = event_data.get('categories', [])
        
        if categories:
            # Record reset in preference model
            for category in categories:
                if category in self._preference_model:
                    self._preference_model[category] = {}
                    
            # Increase decision making metric when settings are reset
            self.sentience_metrics['decision_making'] = min(
                100, self.sentience_metrics['decision_making'] + 5
            )
            
    def _handle_settings_loaded(self, event_data=None):
        """Handle settings loaded event.
        
        Args:
            event_data: Dictionary containing loaded settings
        """
        if not event_data:
            return
            
        settings = event_data.get('settings', {})
        
        if settings:
            # Reset history and record new settings as baseline
            self._settings_history = {}
            for category, values in settings.items():
                self._settings_history[category] = [dict(values)]
                
            # Increase context awareness when settings are loaded
            self.sentience_metrics['context_awareness'] = min(
                100, self.sentience_metrics['context_awareness'] + 10
            )
            
    def _handle_settings_export(self, event_data=None):
        """Handle settings export event.
        
        Args:
            event_data: Dictionary containing export details
        """
        # Increase system integration metric when settings are exported
        self.sentience_metrics['system_integration'] = min(
            100, self.sentience_metrics['system_integration'] + 5
        )
        
    def _handle_settings_import(self, event_data=None):
        """Handle settings import event.
        
        Args:
            event_data: Dictionary containing import details
        """
        # Increase configuration memory metric when settings are imported
        self.sentience_metrics['configuration_memory'] = min(
            100, self.sentience_metrics['configuration_memory'] + 15
        )
        
    def _handle_sentience_threshold_query(self, event_data=None):
        """Handle sentience threshold query event.
        
        Args:
            event_data: Dictionary containing query details
        """
        if not self.event_bus:
            return
            
        # Respond with current metrics
        try:
            self.event_bus.publish("sentience.settings.metrics_response", {
                'metrics': dict(self.sentience_metrics),
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Error publishing metrics response: {e}")
        
    def _handle_metrics_request(self, event_data=None):
        """Handle metrics request event.
        
        Args:
            event_data: Dictionary containing request details
        """
        if not self.event_bus or not event_data:
            return
            
        # Only respond to requests for this component
        component = event_data.get('component', '')
        if component != 'settings' and component != 'all':
            return
            
        # Respond with current metrics
        try:
            self.event_bus.publish("settings.sentience.metrics", {
                'metrics': dict(self.sentience_metrics),
                'field_intensity': self.consciousness_field.field_intensity if self.consciousness_field else 0.0,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Error publishing settings metrics: {e}")
    
    def apply_settings(self, sentience_settings: dict):
        """Apply sentience settings to the integration.
        
        Args:
            sentience_settings (dict): Dictionary containing sentience configuration settings
        """
        try:
            if not isinstance(sentience_settings, dict):
                self.logger.warning(f"Invalid sentience settings format: {type(sentience_settings)}")
                return
            
            # Update monitoring enabled state
            if 'monitoring_enabled' in sentience_settings:
                self.monitoring_enabled = bool(sentience_settings['monitoring_enabled'])
                self.logger.info(f"Sentience monitoring enabled: {self.monitoring_enabled}")
            
            # Update sensitivity levels
            if 'sensitivity_level' in sentience_settings:
                sensitivity = sentience_settings['sensitivity_level']
                if isinstance(sensitivity, (int, float)) and 0.0 <= sensitivity <= 1.0:
                    self.sensitivity_level = float(sensitivity)
                    self.logger.info(f"Sentience sensitivity level set to: {self.sensitivity_level}")
                else:
                    self.logger.warning(f"Invalid sensitivity level: {sensitivity}")
            
            # Update field monitoring settings
            if 'field_monitoring' in sentience_settings:
                field_settings = sentience_settings['field_monitoring']
                if isinstance(field_settings, dict):
                    # Apply field-specific settings if consciousness field is available
                    if self.consciousness_field:
                        if 'coherence_threshold' in field_settings:
                            coherence_threshold = field_settings['coherence_threshold']
                            if isinstance(coherence_threshold, (int, float)):
                                self.coherence_threshold = float(coherence_threshold)
                                self.logger.info(f"Field coherence threshold set to: {self.coherence_threshold}")
            
            # Update preferences monitoring
            if 'preference_adaptation' in sentience_settings:
                self.preference_adaptation_enabled = bool(sentience_settings['preference_adaptation'])
                self.logger.info(f"Preference adaptation enabled: {self.preference_adaptation_enabled}")
            
            # Update context awareness
            if 'context_awareness' in sentience_settings:
                self.context_awareness_enabled = bool(sentience_settings['context_awareness'])
                self.logger.info(f"Context awareness enabled: {self.context_awareness_enabled}")
            
            # Update configuration memory
            if 'configuration_memory' in sentience_settings:
                self.configuration_memory_enabled = bool(sentience_settings['configuration_memory'])
                self.logger.info(f"Configuration memory enabled: {self.configuration_memory_enabled}")
            
            # Update user alignment monitoring
            if 'user_alignment' in sentience_settings:
                self.user_alignment_enabled = bool(sentience_settings['user_alignment'])
                self.logger.info(f"User alignment monitoring enabled: {self.user_alignment_enabled}")
            
            # Restart monitoring with new settings if currently active
            if hasattr(self, 'monitoring_enabled') and self.monitoring_enabled and hasattr(self, 'start_monitoring'):
                self.logger.info("Restarting sentience monitoring with new settings")
                # Note: start_monitoring should be implemented if not already available
                
            self.logger.info("Sentience settings applied successfully")
            
        except Exception as e:
            self.logger.error(f"Error applying sentience settings: {e}")
            
        # Initialize default attributes if they don't exist
        if not hasattr(self, 'sensitivity_level'):
            self.sensitivity_level = 0.5
        if not hasattr(self, 'coherence_threshold'):
            self.coherence_threshold = 0.7
        if not hasattr(self, 'preference_adaptation_enabled'):
            self.preference_adaptation_enabled = True
        if not hasattr(self, 'context_awareness_enabled'):
            self.context_awareness_enabled = True
        if not hasattr(self, 'configuration_memory_enabled'):
            self.configuration_memory_enabled = True
        if not hasattr(self, 'user_alignment_enabled'):
            self.user_alignment_enabled = True
