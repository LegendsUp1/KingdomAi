#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Code Generator Event Handlers Module
Contains implementation of code generator event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("KingdomAI.CodeGenHandlers")

# Code Generator event handler methods
async def update_codegen_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update code generator status display when codegen.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing code generator status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty code generator status data")
            return
            
        # Update code generator status
        if 'status' in event_data:
            self.codegen_status = event_data['status']
            self.codegen_data['status'] = self.codegen_status
            
        # Update code generator status display if code_gen tab is present
        if 'code_gen' in self.tab_frames:
            codegen_frame = self.tab_frames['code_gen']
            
            # Update status label if it exists
            if hasattr(codegen_frame, 'status_label'):
                if self.using_pyqt:
                    codegen_frame.status_label.setText(f"Code Generator Status: {self.codegen_status}")
                elif self.using_tkinter:
                    codegen_frame.status_label.config(text=f"Code Generator Status: {self.codegen_status}")
            
            # Update model status widgets based on status
            if hasattr(codegen_frame, 'model_status_indicator'):
                if self.codegen_status == "ready":
                    indicator_color = "green"
                elif self.codegen_status == "loading":
                    indicator_color = "yellow"
                else:
                    indicator_color = "red"
                    
                if self.using_pyqt:
                    codegen_frame.model_status_indicator.setStyleSheet(f"background-color: {indicator_color};")
                elif self.using_tkinter:
                    codegen_frame.model_status_indicator.config(bg=indicator_color)
                    
            # Update generate button if it exists
            if hasattr(codegen_frame, 'generate_button'):
                if self.codegen_status == "ready":
                    # Model is ready, enable generate button
                    if self.using_pyqt:
                        codegen_frame.generate_button.setEnabled(True)
                    elif self.using_tkinter:
                        codegen_frame.generate_button.config(state='normal')
                else:
                    # Model is not ready, disable generate button
                    if self.using_pyqt:
                        codegen_frame.generate_button.setEnabled(False)
                    elif self.using_tkinter:
                        codegen_frame.generate_button.config(state='disabled')
                    
        self.logger.debug(f"Updated code generator status: {self.codegen_status}")
    except Exception as e:
        self.logger.error(f"Error updating code generator status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_codegen_models(self, event_type: str, event_data: Dict[str, Any]):
    """Update code generator models display when codegen.models events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing code generator model information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty code generator models data")
            return
            
        # Store models data
        if 'models' in event_data:
            models = event_data['models']
            self.codegen_data['models'] = models
            
        # Update current model if provided
        if 'current_model' in event_data:
            current_model = event_data['current_model']
            self.codegen_data['current_model'] = current_model
            
        # Update code generator models display if code_gen tab is present
        if 'code_gen' in self.tab_frames:
            codegen_frame = self.tab_frames['code_gen']
            
            # Update models dropdown if it exists
            if hasattr(codegen_frame, 'model_dropdown'):
                if self.using_pyqt:
                    # Clear and update dropdown
                    codegen_frame.model_dropdown.clear()
                    for model in models:
                        model_id = model.get('id', 'Unknown')
                        model_name = model.get('name', 'Unknown')
                        codegen_frame.model_dropdown.addItem(model_name, model_id)
                        
                    # Set current model
                    for i in range(codegen_frame.model_dropdown.count()):
                        if codegen_frame.model_dropdown.itemData(i) == current_model:
                            codegen_frame.model_dropdown.setCurrentIndex(i)
                            break
                elif self.using_tkinter:
                    # Get current StringVar for dropdown
                    if hasattr(codegen_frame, 'model_var'):
                        # Clear dropdown
                        codegen_frame.model_dropdown['menu'].delete(0, 'end')
                        
                        # Create model name to ID mapping for later use
                        model_map = {}
                        for model in models:
                            model_id = model.get('id', 'Unknown')
                            model_name = model.get('name', 'Unknown')
                            model_map[model_name] = model_id
                            # Add to dropdown
                            codegen_frame.model_dropdown['menu'].add_command(
                                label=model_name,
                                command=lambda name=model_name: codegen_frame.model_var.set(name)
                            )
                        
                        # Set current model by finding its name
                        current_name = "Unknown"
                        for model in models:
                            if model.get('id') == current_model:
                                current_name = model.get('name', 'Unknown')
                                break
                                
                        codegen_frame.model_var.set(current_name)
            
            # Update current model label if it exists
            if hasattr(codegen_frame, 'current_model_label'):
                # Find current model name
                current_name = "Unknown"
                for model in models:
                    if model.get('id') == current_model:
                        current_name = model.get('name', 'Unknown')
                        break
                
                if self.using_pyqt:
                    codegen_frame.current_model_label.setText(f"Current Model: {current_name}")
                elif self.using_tkinter:
                    codegen_frame.current_model_label.config(text=f"Current Model: {current_name}")
                    
        self.logger.debug(f"Updated code generator models with {len(models) if models else 0} models")
    except Exception as e:
        self.logger.error(f"Error updating code generator models: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_codegen_output(self, event_type: str, event_data: Dict[str, Any]):
    """Update code output display when codegen.output events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing generated code output
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty code output data")
            return
            
        # Add code to generated code history if provided
        if 'code' in event_data:
            code = event_data['code']
            timestamp = event_data.get('timestamp', 'Unknown')
            language = event_data.get('language', 'Unknown')
            description = event_data.get('description', '')
            
            code_entry = {
                'code': code,
                'timestamp': timestamp,
                'language': language,
                'description': description
            }
            
            self.generated_code.append(code_entry)
            # Limit history size
            if len(self.generated_code) > 20:
                self.generated_code = self.generated_code[-20:]
            
            # Store in codegen data
            self.codegen_data['generated_code'] = self.generated_code
            self.codegen_data['latest_code'] = code
            
        # Update code output display if code_gen tab is present
        if 'code_gen' in self.tab_frames:
            codegen_frame = self.tab_frames['code_gen']
            
            # Update code output text area if it exists
            if hasattr(codegen_frame, 'code_output'):
                code = event_data.get('code', '')
                language = event_data.get('language', 'Unknown')
                
                if self.using_pyqt:
                    # Set code output text
                    codegen_frame.code_output.setPlainText(code)
                elif self.using_tkinter:
                    # Clear and set code output text
                    codegen_frame.code_output.delete(1.0, 'end')
                    codegen_frame.code_output.insert('end', code)
            
            # Update language label if it exists
            if hasattr(codegen_frame, 'language_label'):
                language = event_data.get('language', 'Unknown')
                
                if self.using_pyqt:
                    codegen_frame.language_label.setText(f"Language: {language}")
                elif self.using_tkinter:
                    codegen_frame.language_label.config(text=f"Language: {language}")
                    
        self.logger.debug(f"Updated code generator output")
    except Exception as e:
        self.logger.error(f"Error updating code generator output: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def generate_code(self, prompt=None, language=None, model_id=None):
    """Generate code based on provided prompt and parameters.
    
    Args:
        prompt: The prompt to generate code from
        language: The programming language to generate code in
        model_id: The ID of the model to use
        
    Returns:
        bool: True if code generation request was sent successfully, False otherwise
    """
    try:
        self.logger.info("Requesting code generation")
        
        # Ensure we have a prompt
        if not prompt:
            self.logger.warning("No prompt provided for code generation")
            return False
            
        # Prepare request data
        request_data = {
            'prompt': prompt
        }
        
        # Add language if provided
        if language:
            request_data['language'] = language
            
        # Add model ID if provided
        if model_id:
            request_data['model_id'] = model_id
        
        # Connect to Redis Quantum Nexus on required port and password
        if hasattr(self, 'redis_client'):
            try:
                # Ensure Redis connection uses port 6380 with QuantumNexus2025 password
                await self.redis_client.initialize(
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    environment="codegen"
                )
                self.logger.info("Connected to Redis Quantum Nexus on port 6380 for code generation")
            except Exception as redis_error:
                self.logger.error(f"Failed to connect to Redis Quantum Nexus: {redis_error}")
                self.codegen_status = "disconnected"
                return False
        
        # Request code generation
        if self.event_bus:
            await self.event_bus.emit("generate_code", request_data)
            self.codegen_status = "generating"
            return True
        else:
            self.logger.warning("No event bus available for code generation")
            return False
    except Exception as e:
        self.logger.error(f"Error generating code: {e}")
        import traceback
        self.logger.error(traceback.format_exc())
        return False
