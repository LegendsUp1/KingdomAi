#!/usr/bin/env python3

import logging
import traceback
import time
from collections import defaultdict
import json
import os

# Try to import tkinter - handle both regular Tkinter and Custom Tkinter
try:
    import tkinter as tk
    from tkinter import ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

# Try to import customtkinter if available
try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
except ImportError:
    HAS_CUSTOMTKINTER = False

# Import base component from the Kingdom AI system
from core.base_component import BaseComponent

class AIGUIManager(BaseComponent):
    """
    AI-powered GUI Manager for Kingdom AI
    
    This component extends the GUI functionality with AI-powered features:
    - Interaction pattern learning and prediction
    - Adaptive UI based on usage patterns
    - Smart widget highlighting and suggestions
    - Dynamic layout optimization
    - Context-aware help
    """
    
    def __init__(self, gui_manager=None, **kwargs):
        """Initialize the AI GUI Manager.
        
        Args:
            gui_manager: Reference to the main GUIManager
            **kwargs: Additional configuration parameters
        """
        super().__init__("AIGUIManager")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Store reference to main GUI manager
        self.gui_manager = gui_manager
        
        # Initialize AI components
        self.interaction_history = []
        self.interaction_patterns = defaultdict(lambda: defaultdict(int))
        self.widget_registry = {}
        self.suggestion_widgets = {}
        self.last_action = None
        self.color_transitions = {}
        self.learning_enabled = kwargs.get('learning_enabled', True)
        
        # Configuration
        self.config = {
            'prediction_threshold': 3,  # Minimum count to consider a prediction valid
            'history_limit': 1000,      # Maximum interaction history items
            'suggestion_delay': 500,    # Milliseconds before showing suggestion
            'transition_speed': 50,     # Color transition speed (ms)
            'data_path': os.path.join(os.path.dirname(__file__), '../data/ai_gui_data.json')
        }
        
        # Color schemes for highlighting
        self.highlight_colors = {
            'suggestion': '#f39c12',   # Orange highlight for suggestions
            'active': '#2ecc71',       # Green highlight for active elements
            'warning': '#e74c3c',      # Red highlight for warnings
            'neutral': '#3498db'       # Blue highlight for neutral focus
        }
        
        # Initialize trackers
        self.task_id_counter = 0
        self.active_tasks = {}
        self.active_transitions = {}
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.config['data_path']), exist_ok=True)
        
        # Load saved interaction data if available
        self.load_interaction_data()
        
        self.logger.info("AI GUI Manager initialized")
    
    async def initialize(self) -> bool:
        """Initialize the AI GUI Manager asynchronously."""
        self.logger.info("Initializing AI GUI Manager...")
        await self.subscribe_to_events()
        return True
    
    def initialize_sync(self) -> bool:
        """Initialize the AI GUI Manager synchronously."""
        self.logger.info("Initializing AI GUI Manager (sync)...")
        self.subscribe_to_events_sync()
        return True
    
    async def subscribe_to_events(self):
        """Subscribe to events asynchronously."""
        if self.event_bus:
            self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
            self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
    
    def subscribe_to_events_sync(self):
        """Subscribe to events synchronously."""
        if self.event_bus:
            self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
            self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
    
    def handle_gui_update(self, event):
        """Handle GUI update events."""
        try:
            if event.data and 'action' in event.data:
                action = event.data['action']
                if action == 'register_widget':
                    self.register_widget(event.data.get('widget'), 
                                        event.data.get('name'),
                                        event.data.get('widget_type'))
                elif action == 'record_interaction':
                    self.record_interaction(event.data.get('widget_id'),
                                          event.data.get('interaction_type'))
                elif action == 'update_suggestion':
                    self.update_suggestions()
        except Exception as e:
            self.logger.error(f"Error handling GUI update: {e}")
            self.logger.error(traceback.format_exc())
    
    def handle_shutdown(self, event):
        """Handle system shutdown event."""
        try:
            self.save_interaction_data()
            self.logger.info("AI GUI Manager shutting down")
        except Exception as e:
            self.logger.error(f"Error during AI GUI Manager shutdown: {e}")
    
    def register_widget(self, widget, name=None, widget_type=None):
        """Register a widget with the AI GUI Manager for monitoring.
        
        Args:
            widget: The widget to register (tk/ttk/ctk)
            name: User-friendly name for the widget
            widget_type: Type of widget (button, tab, etc.)
        """
        if not widget:
            return
            
        widget_id = str(widget)
        
        if widget_id in self.widget_registry:
            return widget_id
            
        if not name:
            name = getattr(widget, 'text', None) or f"Widget-{len(self.widget_registry)}"
            
        if not widget_type:
            if HAS_CUSTOMTKINTER and isinstance(widget, ctk.CTkButton):
                widget_type = 'button'
            elif HAS_TKINTER:
                if isinstance(widget, tk.Button) or isinstance(widget, ttk.Button):
                    widget_type = 'button'
                elif isinstance(widget, ttk.Notebook):
                    widget_type = 'notebook'
                elif isinstance(widget, ttk.Treeview):
                    widget_type = 'treeview'
                elif isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                    widget_type = 'entry'
                else:
                    widget_type = 'other'
            else:
                widget_type = 'other'
                
        # Store widget information
        self.widget_registry[widget_id] = {
            'widget': widget,
            'name': name,
            'type': widget_type,
            'interaction_count': 0,
            'last_interaction': None
        }
        
        # Bind appropriate events based on widget type
        try:
            if widget_type == 'button':
                self._bind_button_events(widget, widget_id)
            elif widget_type == 'notebook':
                self._bind_notebook_events(widget, widget_id)
            elif widget_type == 'treeview':
                self._bind_treeview_events(widget, widget_id)
            elif widget_type == 'entry':
                self._bind_entry_events(widget, widget_id)
            else:
                # Generic event binding
                if hasattr(widget, 'bind'):
                    widget.bind('<Button-1>', lambda e, wid=widget_id: 
                               self._handle_widget_interaction(wid, 'click'))
        except Exception as e:
            self.logger.error(f"Error binding events to widget {name}: {e}")
            
        return widget_id
                
    def _bind_button_events(self, widget, widget_id):
        """Bind events to a button widget."""
        if HAS_CUSTOMTKINTER and isinstance(widget, ctk.CTkButton):
            original_command = widget._command
            def command_wrapper():
                self._handle_widget_interaction(widget_id, 'click')
                if callable(original_command):
                    return original_command()
            widget.configure(command=command_wrapper)
        elif HAS_TKINTER:
            if isinstance(widget, tk.Button):
                original_command = widget.cget('command')
                def command_wrapper():
                    self._handle_widget_interaction(widget_id, 'click')
                    if callable(original_command):
                        return original_command()
                widget.configure(command=command_wrapper)
            else:
                widget.bind('<Button-1>', lambda e, wid=widget_id: 
                           self._handle_widget_interaction(wid, 'click'))
    
    def _bind_notebook_events(self, widget, widget_id):
        """Bind events to a notebook (tabbed) widget."""
        if not hasattr(widget, 'bind'):
            return
            
        widget.bind('<<NotebookTabChanged>>', lambda e, wid=widget_id:
                   self._handle_widget_interaction(wid, 'tab_change'))
    
    def _bind_treeview_events(self, widget, widget_id):
        """Bind events to a treeview widget."""
        if not hasattr(widget, 'bind'):
            return
            
        widget.bind('<<TreeviewSelect>>', lambda e, wid=widget_id:
                   self._handle_widget_interaction(wid, 'selection'))
    
    def _bind_entry_events(self, widget, widget_id):
        """Bind events to an entry widget."""
        if not hasattr(widget, 'bind'):
            return
            
        widget.bind('<FocusIn>', lambda e, wid=widget_id:
                   self._handle_widget_interaction(wid, 'focus'))
        widget.bind('<Return>', lambda e, wid=widget_id:
                   self._handle_widget_interaction(wid, 'submit'))
    
    def _handle_widget_interaction(self, widget_id, interaction_type):
        """Handle interaction with a registered widget.
        
        Args:
            widget_id: The ID of the widget that was interacted with
            interaction_type: The type of interaction (click, select, etc.)
        """
        if not self.learning_enabled:
            return
            
        if widget_id not in self.widget_registry:
            return
            
        # Record the interaction and update patterns
        self.record_interaction(widget_id, interaction_type)
        
        # Update widget metrics
        widget_info = self.widget_registry[widget_id]
        widget_info['interaction_count'] += 1
        widget_info['last_interaction'] = time.time()
        
        # Update suggestions
        self.update_suggestions()
    
    def record_interaction(self, widget_id, interaction_type):
        """Record an interaction to build the AI model.
        
        Args:
            widget_id: The ID of the widget that was interacted with
            interaction_type: The type of interaction (click, select, etc.)
        """
        if not self.learning_enabled or not widget_id:
            return
            
        action = f"{widget_id}:{interaction_type}"
        
        # Record in history
        self.interaction_history.append({
            'action': action,
            'timestamp': time.time()
        })
        
        # Trim history if needed
        if len(self.interaction_history) > self.config['history_limit']:
            self.interaction_history = self.interaction_history[-self.config['history_limit']:]
        
        # Update transition patterns
        if self.last_action is not None:
            self.interaction_patterns[self.last_action][action] += 1
        
        self.last_action = action
    
    def predict_next_action(self, action=None):
        """Predict the next likely action based on the current state.
        
        Args:
            action: The current action to base the prediction on.
                   If None, uses the last recorded action.
                   
        Returns:
            A tuple of (widget_id, interaction_type) or None if no prediction.
        """
        if not self.learning_enabled or len(self.interaction_patterns) == 0:
            return None
            
        # Use provided action or last recorded action
        current_action = action or self.last_action
        if current_action is None:
            return None
            
        # Get transitions from this action
        transitions = self.interaction_patterns.get(current_action, {})
        if not transitions:
            return None
            
        # Find the most likely next action that meets threshold
        next_action = max(transitions.items(), key=lambda x: x[1])
        if next_action[1] < self.config['prediction_threshold']:
            return None
            
        # Parse the action string
        parts = next_action[0].split(':', 1)
        if len(parts) != 2:
            return None
            
        return (parts[0], parts[1])
    
    def update_suggestions(self):
        """Update the UI with suggestions based on predicted next actions."""
        if not self.learning_enabled:
            return
            
        # Get the predicted next action
        prediction = self.predict_next_action()
        if not prediction:
            return
            
        widget_id, interaction_type = prediction
        
        # Check if the widget exists
        if widget_id not in self.widget_registry:
            return
            
        widget_info = self.widget_registry[widget_id]
        
        # Generate suggestion message
        suggestion_message = f"Next suggested: {widget_info['name']}"
        
        # Update suggestion widgets
        for suggestion_widget in self.suggestion_widgets.values():
            if hasattr(suggestion_widget, 'configure'):
                suggestion_widget.configure(text=suggestion_message)
            elif hasattr(suggestion_widget, 'config'):
                suggestion_widget.config(text=suggestion_message)
        
        # Highlight the suggested widget
        self.highlight_widget(widget_id)
    
    def highlight_widget(self, widget_id, color_key='suggestion'):
        """Highlight a widget to indicate it's the suggested next action.
        
        Args:
            widget_id: ID of the widget to highlight
            color_key: Key for the highlight color to use
        """
        if widget_id not in self.widget_registry:
            return
            
        widget_info = self.widget_registry[widget_id]
        widget = widget_info['widget']
        
        # Get highlight color
        highlight_color = self.highlight_colors.get(color_key, self.highlight_colors['neutral'])
        
        # Store original colors for later restoration
        self.store_widget_colors(widget_id, widget)
        
        # Apply highlight based on widget type
        try:
            if HAS_CUSTOMTKINTER and isinstance(widget, ctk.CTkButton):
                widget.configure(fg_color=highlight_color)
            elif HAS_TKINTER:
                if isinstance(widget, tk.Button):
                    widget.config(bg=highlight_color)
                elif isinstance(widget, ttk.Button):
                    style_name = f"Highlight.TButton.{widget_id}"
                    style = ttk.Style()
                    style.configure(style_name, background=highlight_color)
                    widget.configure(style=style_name)
        except Exception as e:
            self.logger.error(f"Error highlighting widget {widget_id}: {e}")
    
    def store_widget_colors(self, widget_id, widget):
        """Store the original colors of a widget before highlighting.
        
        Args:
            widget_id: ID of the widget
            widget: The widget object
        """
        if widget_id in self.color_transitions:
            return
            
        try:
            if HAS_CUSTOMTKINTER and isinstance(widget, ctk.CTkButton):
                self.color_transitions[widget_id] = {
                    'original': widget.cget('fg_color'),
                    'current': widget.cget('fg_color')
                }
            elif HAS_TKINTER:
                if isinstance(widget, tk.Button):
                    self.color_transitions[widget_id] = {
                        'original': widget.cget('bg'),
                        'current': widget.cget('bg')
                    }
                elif isinstance(widget, ttk.Button):
                    style = ttk.Style()
                    orig_style = widget.cget('style') or 'TButton'
                    bg = style.lookup(orig_style, 'background')
                    self.color_transitions[widget_id] = {
                        'original': bg or '#d9d9d9',
                        'current': bg or '#d9d9d9'
                    }
        except Exception as e:
            self.logger.error(f"Error storing widget colors for {widget_id}: {e}")
    
    def restore_widget_colors(self, widget_id=None):
        """Restore original colors of highlighted widgets.
        
        Args:
            widget_id: ID of widget to restore, or None for all widgets
        """
        if widget_id:
            widget_ids = [widget_id]
        else:
            widget_ids = list(self.color_transitions.keys())
            
        for wid in widget_ids:
            if wid not in self.color_transitions:
                continue
                
            if wid not in self.widget_registry:
                continue
                
            widget_info = self.widget_registry[wid]
            widget = widget_info['widget']
            original_color = self.color_transitions[wid]['original']
            
            try:
                if HAS_CUSTOMTKINTER and isinstance(widget, ctk.CTkButton):
                    widget.configure(fg_color=original_color)
                elif HAS_TKINTER:
                    if isinstance(widget, tk.Button):
                        widget.config(bg=original_color)
                    elif isinstance(widget, ttk.Button):
                        style = ttk.Style()
                        orig_style = widget.cget('style').split('.')[0] or 'TButton'
                        widget.configure(style=orig_style)
            except Exception as e:
                self.logger.error(f"Error restoring widget colors for {wid}: {e}")
                
            # Remove from transitions
            del self.color_transitions[wid]
    
    def add_suggestion_widget(self, widget, widget_id=None):
        """Register a widget to display AI suggestions.
        
        Args:
            widget: The widget to show suggestions in (usually a Label)
            widget_id: Optional ID for the suggestion widget
            
        Returns:
            The ID of the registered suggestion widget
        """
        if not widget_id:
            widget_id = f"suggestion_{len(self.suggestion_widgets)}"
            
        self.suggestion_widgets[widget_id] = widget
        return widget_id
    
    def load_interaction_data(self):
        """Load saved interaction patterns from disk."""
        try:
            if os.path.exists(self.config['data_path']):
                with open(self.config['data_path'], 'r') as f:
                    data = json.load(f)
                    
                    # Convert string keys back to numeric keys in defaultdict
                    patterns = defaultdict(lambda: defaultdict(int))
                    for a1, transitions in data.get('patterns', {}).items():
                        for a2, count in transitions.items():
                            patterns[a1][a2] = count
                    
                    self.interaction_patterns = patterns
                    self.logger.info(f"Loaded interaction data from {self.config['data_path']}")
        except Exception as e:
            self.logger.error(f"Error loading interaction data: {e}")
    
    def save_interaction_data(self):
        """Save interaction patterns to disk."""
        try:
            # Convert defaultdict to regular dict for JSON serialization
            patterns_dict = {}
            for a1, transitions in self.interaction_patterns.items():
                patterns_dict[a1] = dict(transitions)
                
            data = {
                'patterns': patterns_dict,
                'timestamp': time.time()
            }
            
            with open(self.config['data_path'], 'w') as f:
                json.dump(data, f, indent=2)
                
            self.logger.info(f"Saved interaction data to {self.config['data_path']}")
        except Exception as e:
            self.logger.error(f"Error saving interaction data: {e}")
    
    def update_configuration(self, config_updates):
        """Update the configuration settings.
        
        Args:
            config_updates: Dictionary of configuration updates
        """
        for key, value in config_updates.items():
            if key in self.config:
                self.config[key] = value
                
        self.logger.info(f"Updated AI GUI Manager configuration: {config_updates}")
    
    def toggle_learning(self, enabled=None):
        """Enable or disable AI learning.
        
        Args:
            enabled: Boolean to enable/disable, or None to toggle
        """
        if enabled is None:
            self.learning_enabled = not self.learning_enabled
        else:
            self.learning_enabled = bool(enabled)
            
        self.logger.info(f"AI GUI learning {'enabled' if self.learning_enabled else 'disabled'}")
        
        if not self.learning_enabled:
            # Clear any active highlights
            self.restore_widget_colors()
    
    def get_widget_usage_stats(self):
        """Get usage statistics for all registered widgets.
        
        Returns:
            Dictionary of widget usage statistics
        """
        stats = {}
        for widget_id, widget_info in self.widget_registry.items():
            stats[widget_id] = {
                'name': widget_info['name'],
                'type': widget_info['type'],
                'interaction_count': widget_info['interaction_count'],
                'last_interaction': widget_info['last_interaction']
            }
        return stats
    
    def get_most_used_widgets(self, limit=5):
        """Get the most frequently used widgets.
        
        Args:
            limit: Maximum number of widgets to return
            
        Returns:
            List of tuples (widget_id, interaction_count)
        """
        widget_usage = [(wid, info['interaction_count']) 
                        for wid, info in self.widget_registry.items()]
        
        # Sort by interaction count (descending)
        sorted_usage = sorted(widget_usage, key=lambda x: x[1], reverse=True)
        
        return sorted_usage[:limit]
    
    def get_pattern_insights(self, limit=10):
        """Get insights on the most common interaction patterns.
        
        Args:
            limit: Maximum number of patterns to return
            
        Returns:
            List of dictionaries with pattern insights
        """
        all_transitions = []
        
        for source, transitions in self.interaction_patterns.items():
            for target, count in transitions.items():
                source_parts = source.split(':', 1)
                target_parts = target.split(':', 1)
                
                if len(source_parts) != 2 or len(target_parts) != 2:
                    continue
                    
                source_id, source_type = source_parts
                target_id, target_type = target_parts
                
                source_name = self.widget_registry.get(source_id, {}).get('name', 'Unknown')
                target_name = self.widget_registry.get(target_id, {}).get('name', 'Unknown')
                
                all_transitions.append({
                    'source': source_name,
                    'target': target_name,
                    'source_action': source_type,
                    'target_action': target_type,
                    'count': count
                })
        
        # Sort by count (descending)
        sorted_transitions = sorted(all_transitions, key=lambda x: x['count'], reverse=True)
        
        return sorted_transitions[:limit]
    
    def get_navigation_suggestions(self, current_page):
        """Get suggestions for navigation based on the current page.
        
        Args:
            current_page: Identifier for the current page or view
            
        Returns:
            List of suggested next pages or actions
        """
        # Construct an action for the current page
        current_action = f"{current_page}:view"
        
        # Get predictions based on this action
        transitions = self.interaction_patterns.get(current_action, {})
        if not transitions:
            return []
            
        # Sort transitions by count
        sorted_transitions = sorted(transitions.items(), key=lambda x: x[1], reverse=True)
        
        # Extract and format suggestions
        suggestions = []
        for action, count in sorted_transitions:
            parts = action.split(':', 1)
            if len(parts) != 2:
                continue
                
            widget_id, action_type = parts
            
            # Only include navigational actions
            if action_type not in ('click', 'tab_change'):
                continue
                
            widget_name = self.widget_registry.get(widget_id, {}).get('name', 'Unknown')
            
            suggestions.append({
                'id': widget_id,
                'name': widget_name,
                'action': action_type,
                'confidence': count / max(transitions.values()) if transitions else 0
            })
            
        return suggestions[:5]  # Return top 5 suggestions
