#!/usr/bin/env python3

import logging
import traceback

# Import the AI GUI Manager
from core.ai_gui_manager import AIGUIManager
from core.base_component import BaseComponent

class GUIAIIntegration(BaseComponent):
    """
    Integration class to connect the AI GUI Manager with the main GUI system
    
    This component serves as a bridge between the traditional GUI system and
    the AI-powered enhancements, handling widget registration, event forwarding,
    and AI suggestions display.
    """
    
    def __init__(self, gui_manager=None, **kwargs):
        """Initialize the GUI AI Integration.
        
        Args:
            gui_manager: Reference to the main GUIManager
            **kwargs: Additional configuration parameters
        """
        super().__init__("GUIAIIntegration")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Store reference to main GUI manager
        self.gui_manager = gui_manager
        
        # Create AI GUI Manager
        self.ai_gui_manager = AIGUIManager(gui_manager, **kwargs)
        
        # Status tracking
        self.is_initialized = False
        self.suggestion_widget = None
        self.ai_enabled = kwargs.get('ai_enabled', True)
        
        self.logger.info("GUI AI Integration initialized")
    
    async def initialize(self) -> bool:
        """Initialize the GUI AI Integration asynchronously."""
        self.logger.info("Initializing GUI AI Integration...")
        
        # Initialize AI GUI Manager
        await self.ai_gui_manager.initialize()
        
        # Subscribe to events
        await self.subscribe_to_events()
        
        self.is_initialized = True
        return True
    
    def initialize_sync(self) -> bool:
        """Initialize the GUI AI Integration synchronously."""
        self.logger.info("Initializing GUI AI Integration (sync)...")
        
        # Initialize AI GUI Manager
        self.ai_gui_manager.initialize_sync()
        
        # Subscribe to events
        self.subscribe_to_events_sync()
        
        self.is_initialized = True
        return True
    
    async def subscribe_to_events(self):
        """Subscribe to events asynchronously."""
        if self.event_bus:
            self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
            self.event_bus.subscribe_sync("gui.widget.register", self.handle_widget_register)
            self.event_bus.subscribe_sync("gui.widget.interaction", self.handle_widget_interaction)
            self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
    
    def subscribe_to_events_sync(self):
        """Subscribe to events synchronously."""
        if self.event_bus:
            self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
            self.event_bus.subscribe_sync("gui.widget.register", self.handle_widget_register)
            self.event_bus.subscribe_sync("gui.widget.interaction", self.handle_widget_interaction)
            self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
    
    def handle_gui_update(self, event):
        """Handle GUI update events."""
        if not self.ai_enabled:
            return
            
        try:
            if event.data and 'action' in event.data:
                # Forward relevant events to AI GUI Manager
                if event.data['action'] in ['register_widget', 'record_interaction', 'update_suggestion']:
                    self.ai_gui_manager.handle_gui_update(event)
        except Exception as e:
            self.logger.error(f"Error handling GUI update: {e}")
            self.logger.error(traceback.format_exc())
    
    def handle_widget_register(self, event):
        """Handle widget registration events."""
        if not self.ai_enabled:
            return
            
        try:
            if event.data:
                widget = event.data.get('widget')
                name = event.data.get('name')
                widget_type = event.data.get('widget_type')
                
                # Register widget with AI GUI Manager
                self.ai_gui_manager.register_widget(widget, name, widget_type)
        except Exception as e:
            self.logger.error(f"Error handling widget registration: {e}")
            self.logger.error(traceback.format_exc())
    
    def handle_widget_interaction(self, event):
        """Handle widget interaction events."""
        if not self.ai_enabled:
            return
            
        try:
            if event.data:
                widget_id = event.data.get('widget_id')
                interaction_type = event.data.get('interaction_type')
                
                # Forward interaction to AI GUI Manager
                self.ai_gui_manager.record_interaction(widget_id, interaction_type)
                
                # Update suggestions
                self.ai_gui_manager.update_suggestions()
        except Exception as e:
            self.logger.error(f"Error handling widget interaction: {e}")
            self.logger.error(traceback.format_exc())
    
    def handle_shutdown(self, event):
        """Handle system shutdown event."""
        try:
            if self.ai_gui_manager:
                self.ai_gui_manager.handle_shutdown(event)
                
            self.logger.info("GUI AI Integration shutting down")
        except Exception as e:
            self.logger.error(f"Error during GUI AI Integration shutdown: {e}")
    
    def register_widget(self, widget, name=None, widget_type=None):
        """Register a widget with the AI system.
        
        Args:
            widget: The widget to register (tk/ttk/ctk)
            name: User-friendly name for the widget
            widget_type: Type of widget (button, tab, etc.)
            
        Returns:
            The ID of the registered widget
        """
        if not self.ai_enabled or not self.ai_gui_manager:
            return None
            
        return self.ai_gui_manager.register_widget(widget, name, widget_type)
    
    def set_suggestion_widget(self, widget):
        """Set the widget to display AI suggestions.
        
        Args:
            widget: The widget to show suggestions in (usually a Label)
            
        Returns:
            The ID of the registered suggestion widget
        """
        if not self.ai_enabled or not self.ai_gui_manager:
            return None
            
        self.suggestion_widget = widget
        return self.ai_gui_manager.add_suggestion_widget(widget)
    
    def toggle_ai(self, enabled=None):
        """Enable or disable AI features.
        
        Args:
            enabled: Boolean to enable/disable, or None to toggle
        """
        if enabled is None:
            self.ai_enabled = not self.ai_enabled
        else:
            self.ai_enabled = bool(enabled)
            
        self.logger.info(f"AI GUI features {'enabled' if self.ai_enabled else 'disabled'}")
        
        if self.ai_gui_manager:
            self.ai_gui_manager.toggle_learning(self.ai_enabled)
    
    def get_usage_insights(self):
        """Get insights on widget usage and interaction patterns.
        
        Returns:
            Dictionary of usage statistics and insights
        """
        if not self.ai_enabled or not self.ai_gui_manager:
            return {}
            
        most_used = self.ai_gui_manager.get_most_used_widgets()
        patterns = self.ai_gui_manager.get_pattern_insights()
        
        return {
            'most_used_widgets': most_used,
            'interaction_patterns': patterns
        }
    
    def get_navigation_suggestions(self, current_page):
        """Get suggestions for navigation based on the current page.
        
        Args:
            current_page: Identifier for the current page or view
            
        Returns:
            List of suggested next pages or actions
        """
        if not self.ai_enabled or not self.ai_gui_manager:
            return []
            
        return self.ai_gui_manager.get_navigation_suggestions(current_page)
