#!/usr/bin/env python3
"""
Event handlers for the Kingdom AI GUI.

This module contains the event handler methods that are used by the MainWindow 
class to respond to events from the event bus.
"""

import logging
import traceback
import time
from typing import Dict, Any, Optional, List, cast
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger("KingdomAI.EventHandlers")

class EventHandlers:
    """Mixin class for event handlers in the Kingdom AI GUI."""

    def __init__(self, event_bus=None):
        """Initialize EventHandlers with event bus and widget registry.
        
        Args:
            event_bus: EventBus instance for communication
        """
        self.widget_registry = WidgetRegistry()
        self.event_bus = event_bus
        self.logger = logging.getLogger("KingdomAI.EventHandlers")
        self.logger.info("EventHandlers initialized")
    def _update_status_bar(self, message, error=False):
        """Update the status bar with a message.
        
        Args:
            message: Message to display
            error: If True, display as error
        """
        if hasattr(self, 'status_bar') and self.status_bar:
            try:
                fg_color = "red" if error else "black"
                if hasattr(self.status_bar, 'config'):
                    self.status_bar.config(text=message, foreground=fg_color)
                self.logger.info(f"Status bar updated: {message}")
            except Exception as e:
                self.logger.error(f"Failed to update status bar: {e}")
        else:
            self.logger.warning("Status bar not available for update")




    
    async def _handle_dashboard_update(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle dashboard update events.
        
        Args:
            event_type: The event type
            data: Event data with dashboard metrics
        """
        try:
            # Update dashboard components with the latest metrics
            for metric_name, metric_value in data.get('metrics', {}).items():
                widget_name = f"dashboard_{metric_name}_value"
                widget = await self.widget_registry.get_widget(widget_name)
                if widget is not None and hasattr(widget, 'config'):
                    widget.config(text=str(metric_value))

            # Update status message if provided
            if 'status_message' in data:
                self._update_status_bar(data['status_message'])
                
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
            logger.error(traceback.format_exc())
            
    async def _handle_ai_status(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle AI system status updates.
        
        Args:
            event_type: The event type
            data: Event data with AI status information
        """
        try:
            # Update AI status label
            ai_status = await self.widget_registry.get_widget("ai_status")
            if ai_status is not None and hasattr(ai_status, 'config'):
                status = data.get("status", "Unknown")
                if status == "Connected" or status == "Ready":
                    ai_status.config(text=status, foreground="green")
                elif status == "Error":
                    ai_status.config(text=status, foreground="red")
                else:
                    ai_status.config(text=status, foreground="blue")
                    
            # Log AI status update
            logger.info(f"AI status update received: {data}")
            
        except Exception as e:
            logger.error(f"Error updating AI status: {e}")
            logger.error(traceback.format_exc())
            
    async def _handle_ai_response(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle AI system responses.
        
        Args:
            event_type: The event type
            data: Event data with AI response
        """
        try:
            # Get the chat display widget
            chat_display = await self.widget_registry.get_widget("chat_display")
            if chat_display is not None:
                # Enable editing temporarily
                chat_display.config(state=tk.NORMAL)
                
                # Format and insert the message
                message = data.get("message", "")
                sender = data.get("sender", "AI")
                timestamp = data.get("timestamp", time.strftime("%H:%M:%S"))
                
                # Insert formatted message
                chat_display.insert(tk.END, f"[{timestamp}] {sender}: {message}\n")
                
                # Auto-scroll to the bottom
                chat_display.see(tk.END)
                
                # Disable editing again
                chat_display.config(state=tk.DISABLED)
                
        except Exception as e:
            logger.error(f"Error handling AI response: {e}")
            logger.error(traceback.format_exc())
    
    async def _handle_wallet_status_update(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle wallet status update events.
        
        Args:
            event_type: The event type
            data: Event data with wallet status information
        """
        try:
            # Update wallet status label
            wallet_status = await self.widget_registry.get_widget("wallet_status")
            if wallet_status is not None and hasattr(wallet_status, 'config'):
                status = data.get("status", "Unknown")
                if status == "Connected":
                    wallet_status.config(text=f"Status: {status}", foreground="green")
                elif status == "Error":
                    wallet_status.config(text=f"Status: {status}", foreground="red")
                else:
                    wallet_status.config(text=f"Status: {status}", foreground="blue")
                    
            # Update wallet address if provided
            address = data.get("address")
            if address:
                wallet_address = await self.widget_registry.get_widget("wallet_address")
                if wallet_address is not None and hasattr(wallet_address, 'config'):
                    wallet_address.config(text=f"Address: {address}")
                    
            # Log wallet status update
            logger.info(f"Wallet status update received: {data}")
            
        except Exception as e:
            logger.error(f"Error updating wallet status: {e}")
            logger.error(traceback.format_exc())
            
    async def _handle_api_keys_status(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle API keys status updates.
        
        Args:
            event_type: The event type
            data: Event data with API keys status
        """
        try:
            # Update API keys status label
            api_keys_status = await self.widget_registry.get_widget("api_keys_status")
            if api_keys_status is not None and hasattr(api_keys_status, 'config'):
                status = data.get("status", "Unknown")
                if status == "Connected" or status == "Available":
                    api_keys_status.config(text=f"API Keys: {status}", foreground="green")
                elif status == "Error":
                    api_keys_status.config(text=f"API Keys: {status}", foreground="red")
                else:
                    api_keys_status.config(text=f"API Keys: {status}", foreground="blue")
                    
            # If there's a message, update the status bar
            message = data.get('message')
            if message:
                self._update_status_bar(message)
                
        except Exception as e:
            logger.error(f"Error handling API keys status: {e}")
            logger.error(traceback.format_exc())
            
    async def _handle_api_key_added(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle API key added event.
        
        Args:
            event_type: The event type
            data: Event data with added API key information
        """
        try:
            service = data.get('service', 'Unknown service')
            key_id = data.get('id', 'Unknown')
            self._update_status_bar(f"API Key added for {service}")
            
            # Refresh the API keys list by requesting it
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                await self.event_bus.publish("api.keys.request", {
                    "timestamp": time.time(),
                    "component": "MainWindow"
                })
                
        except Exception as e:
            logger.error(f"Error handling API key added: {e}")
            logger.error(traceback.format_exc())
            
    async def _handle_api_key_deleted(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle API key deleted event.
        
        Args:
            event_type: The event type
            data: Event data with deleted API key information
        """
        try:
            key_id = data.get('id', 'Unknown key')
            self._update_status_bar(f"API Key deleted: {key_id}")
            
            # Refresh the API keys list by requesting it
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                await self.event_bus.publish("api.keys.request", {
                    "timestamp": time.time(),
                    "component": "MainWindow"
                })
                
        except Exception as e:
            logger.error(f"Error handling API key deleted: {e}")
            logger.error(traceback.format_exc())
            
    async def _handle_api_key_test_result(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle API key test result event.
        
        Args:
            event_type: The event type
            data: Event data with API key test results
        """
        try:
            success = data.get("success", False)
            service = data.get("service", "Unknown service")
            
            if success:
                self._update_status_bar(f"API Key test successful for {service}")
            else:
                error_msg = data.get("error", "Unknown error")
                self._update_status_bar(f"API Key test failed for {service}: {error_msg}")
                logger.error(f"API Key test failed for {service}: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error handling API key test result: {e}")
            logger.error(traceback.format_exc())
            
    async def _handle_settings_changed(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle settings changed event.
        
        Args:
            event_type: The event type
            data: Event data with changed settings
        """
        try:
            # Update settings in the UI
            settings = data.get('settings', {})
            for setting_name, setting_value in settings.items():
                # Handle component toggles
                if setting_name.endswith('_enabled') and setting_name.split('_')[0] in ['trading', 'mining', 'ai', 'wallet', 'vr']:
                    component_name = setting_name.split('_')[0]
                    toggle_name = f"{component_name}_toggle"
                    toggle = await self.widget_registry.get_widget(toggle_name)
                    if toggle is not None and hasattr(toggle, 'var'):
                        toggle.var.set(setting_value)
                        
            # Display confirmation
            self._update_status_bar("Settings updated successfully")
            
        except Exception as e:
            logger.error(f"Error handling settings changed: {e}")
            logger.error(traceback.format_exc())

class WidgetRegistry:
    """Registry for GUI widgets to facilitate dynamic updates."""
    
    def __init__(self):
        """Initialize an empty widget registry."""
        self.widgets = {}
        self.logger = logging.getLogger("KingdomAI.WidgetRegistry")
        
    async def register_widget(self, name, widget):
        """Register a widget with a name.
        
        Args:
            name: Widget name/ID
            widget: The widget object
        """
        self.widgets[name] = widget
        return True
        
    async def get_widget(self, name):
        """Get a widget by name.
        
        Args:
            name: Widget name/ID
            
        Returns:
            The widget if found, None otherwise
        """
        return self.widgets.get(name)
        
    async def unregister_widget(self, name):
        """Unregister a widget.
        
        Args:
            name: Widget name/ID
            
        Returns:
            bool: True if widget was unregistered, False otherwise
        """
        if name in self.widgets:
            del self.widgets[name]
            return True
        return False
