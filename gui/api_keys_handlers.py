#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI API Keys Event Handlers Module
Contains implementation of API keys event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("KingdomAI.APIKeysHandlers")

# API Keys event handler methods
async def update_api_keys_list(self, event_type: str, event_data: Dict[str, Any]):
    """Update API keys list display when apikeys.list events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing API keys information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty API keys data")
            return
            
        # Update API keys data
        if 'keys' in event_data:
            self.api_keys = event_data['keys']
            self.apikey_data['keys'] = self.api_keys
            
        # Update API keys display if api_keys tab is present
        if 'api_keys' in self.tab_frames:
            apikey_frame = self.tab_frames['api_keys']
            
            # Update API keys list if it exists
            if hasattr(apikey_frame, 'keys_list'):
                if self.using_pyqt:
                    # Clear and update list
                    apikey_frame.keys_list.clear()
                    for key_id, key_data in self.api_keys.items():
                        name = key_data.get('name', 'Unnamed')
                        api_type = key_data.get('type', 'Unknown')
                        status = key_data.get('status', 'Unknown')
                        
                        # Create asterisks-masked key value
                        key_value = key_data.get('key', '')
                        if key_value:
                            # Show first 4 and last 4 chars, asterisks in between
                            if len(key_value) > 8:
                                masked_key = f"{key_value[:4]}{'*' * (len(key_value) - 8)}{key_value[-4:]}"
                            else:
                                masked_key = '********'
                        else:
                            masked_key = ''
                        
                        display = f"{name} ({api_type}) - {status}"
                        apikey_frame.keys_list.addItem(display)
                elif self.using_tkinter:
                    # Clear and update listbox
                    apikey_frame.keys_list.delete(0, 'end')
                    for key_id, key_data in self.api_keys.items():
                        name = key_data.get('name', 'Unnamed')
                        api_type = key_data.get('type', 'Unknown')
                        status = key_data.get('status', 'Unknown')
                        
                        # Create asterisks-masked key value
                        key_value = key_data.get('key', '')
                        if key_value:
                            # Show first 4 and last 4 chars, asterisks in between
                            if len(key_value) > 8:
                                masked_key = f"{key_value[:4]}{'*' * (len(key_value) - 8)}{key_value[-4:]}"
                            else:
                                masked_key = '********'
                        else:
                            masked_key = ''
                        
                        display = f"{name} ({api_type}) - {status}"
                        apikey_frame.keys_list.insert('end', display)
                        
        self.logger.debug(f"Updated API keys list with {len(self.api_keys) if self.api_keys else 0} keys")
    except Exception as e:
        self.logger.error(f"Error updating API keys list: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_api_key_validation(self, event_type: str, event_data: Dict[str, Any]):
    """Update API key validation status when apikeys.validation events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing API key validation information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty API key validation data")
            return
            
        # Update key validation status in the api_keys dictionary
        if 'key_id' in event_data and 'status' in event_data:
            key_id = event_data['key_id']
            status = event_data['status']
            
            if key_id in self.api_keys:
                self.api_keys[key_id]['status'] = status
            
        # Update validation status display if api_keys tab is present
        if 'api_keys' in self.tab_frames:
            apikey_frame = self.tab_frames['api_keys']
            
            # Update validation status label if it exists
            if hasattr(apikey_frame, 'validation_label'):
                key_id = event_data.get('key_id', '')
                status = event_data.get('status', 'Unknown')
                name = self.api_keys.get(key_id, {}).get('name', 'Unknown') if key_id else 'Unknown'
                
                if self.using_pyqt:
                    apikey_frame.validation_label.setText(f"Key '{name}' validation: {status}")
                    # Set color based on status
                    if status == 'valid':
                        apikey_frame.validation_label.setStyleSheet("color: green;")
                    elif status == 'invalid':
                        apikey_frame.validation_label.setStyleSheet("color: red;")
                    else:
                        apikey_frame.validation_label.setStyleSheet("color: orange;")
                elif self.using_tkinter:
                    apikey_frame.validation_label.config(text=f"Key '{name}' validation: {status}")
                    # Set color based on status
                    if status == 'valid':
                        apikey_frame.validation_label.config(fg="green")
                    elif status == 'invalid':
                        apikey_frame.validation_label.config(fg="red")
                    else:
                        apikey_frame.validation_label.config(fg="orange")
            
        self.logger.debug(f"Updated API key validation status for key {event_data.get('key_id', 'Unknown')}")
    except Exception as e:
        self.logger.error(f"Error updating API key validation: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_api_key_operation(self, event_type: str, event_data: Dict[str, Any]):
    """Update API key operation status when apikeys.operation events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing API key operation information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty API key operation data")
            return
        
        # Handle different operations
        if 'operation' in event_data:
            operation = event_data['operation']
            success = event_data.get('success', False)
            message = event_data.get('message', '')
            key_id = event_data.get('key_id', '')
            
            # Update UI based on operation result if api_keys tab is present
            if 'api_keys' in self.tab_frames:
                apikey_frame = self.tab_frames['api_keys']
                
                # Update operation status label if it exists
                if hasattr(apikey_frame, 'operation_label'):
                    op_text = f"{operation.title()} operation {'succeeded' if success else 'failed'}"
                    if message:
                        op_text += f": {message}"
                        
                    if self.using_pyqt:
                        apikey_frame.operation_label.setText(op_text)
                        # Set color based on success
                        if success:
                            apikey_frame.operation_label.setStyleSheet("color: green;")
                        else:
                            apikey_frame.operation_label.setStyleSheet("color: red;")
                    elif self.using_tkinter:
                        apikey_frame.operation_label.config(text=op_text)
                        # Set color based on success
                        if success:
                            apikey_frame.operation_label.config(fg="green")
                        else:
                            apikey_frame.operation_label.config(fg="red")
                
                # Request updated key list if operation was successful
                if success and self.event_bus:
                    # Using _schedule_async_task to avoid blocking
                    self._schedule_async_task(self.event_bus.emit("request_api_keys"))
            
        self.logger.debug(f"Updated API key operation status for {event_data.get('operation', 'Unknown')} operation")
    except Exception as e:
        self.logger.error(f"Error updating API key operation status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def _filter_api_keys(self, api_type=None):
    """Filter API keys by type.
    
    Args:
        api_type: Optional type to filter keys by
    
    Returns:
        dict: Filtered API keys
    """
    try:
        if not api_type:
            return self.api_keys
            
        filtered_keys = {}
        for key_id, key_data in self.api_keys.items():
            if key_data.get('type') == api_type:
                filtered_keys[key_id] = key_data
                
        return filtered_keys
    except Exception as e:
        self.logger.error(f"Error filtering API keys: {e}")
        return {}
