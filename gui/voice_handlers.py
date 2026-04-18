#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Voice Recognition Event Handlers Module
Contains implementation of voice recognition event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("KingdomAI.VoiceHandlers")

# Voice event handler methods
async def update_voice_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update voice recognition status display when voice.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing voice status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty voice status data")
            return
            
        # Update voice status
        if 'status' in event_data:
            self.voice_status = event_data['status']
            self.voice_data['status'] = self.voice_status
            
        # Update recording status if provided
        if 'is_recording' in event_data:
            self.is_recording = event_data['is_recording']
            self.voice_data['is_recording'] = self.is_recording
            
        # Update playback status if provided
        if 'is_playing' in event_data:
            self.is_playing = event_data['is_playing']
            self.voice_data['is_playing'] = self.is_playing
            
        # Update voice status display if voice tab is present
        if 'voice' in self.tab_frames:
            voice_frame = self.tab_frames['voice']
            
            # Update status label if it exists
            if hasattr(voice_frame, 'status_label'):
                if self.using_pyqt:
                    voice_frame.status_label.setText(f"Voice Status: {self.voice_status}")
                elif self.using_tkinter:
                    voice_frame.status_label.config(text=f"Voice Status: {self.voice_status}")
            
            # Update recording indicator if it exists
            if hasattr(voice_frame, 'recording_indicator'):
                indicator_color = "red" if self.is_recording else "gray"
                
                if self.using_pyqt:
                    voice_frame.recording_indicator.setStyleSheet(f"background-color: {indicator_color};")
                elif self.using_tkinter:
                    voice_frame.recording_indicator.config(bg=indicator_color)
            
            # Update record button if it exists
            if hasattr(voice_frame, 'record_button'):
                button_text = "Stop Recording" if self.is_recording else "Start Recording"
                
                if self.using_pyqt:
                    voice_frame.record_button.setText(button_text)
                elif self.using_tkinter:
                    voice_frame.record_button.config(text=button_text)
                    
        self.logger.debug(f"Updated voice status: {self.voice_status}, recording: {self.is_recording}")
    except Exception as e:
        self.logger.error(f"Error updating voice status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_voice_command(self, event_type: str, event_data: Dict[str, Any]):
    """Update recognized voice command display when voice.command events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing recognized voice command
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty voice command data")
            return
            
        # Add command to history if it's provided
        if 'command' in event_data:
            command = event_data['command']
            confidence = event_data.get('confidence', 0)
            timestamp = event_data.get('timestamp', 'Unknown')
            
            command_entry = {
                'command': command,
                'confidence': confidence,
                'timestamp': timestamp
            }
            
            self.voice_command_history.append(command_entry)
            # Limit history size
            if len(self.voice_command_history) > 50:
                self.voice_command_history = self.voice_command_history[-50:]
            
            # Store in voice data
            self.voice_data['command_history'] = self.voice_command_history
            
            # Update latest recognized command
            self.voice_data['latest_command'] = command
            self.voice_data['latest_confidence'] = confidence
            
        # Update voice command display if voice tab is present
        if 'voice' in self.tab_frames:
            voice_frame = self.tab_frames['voice']
            
            # Update current command display if it exists
            if hasattr(voice_frame, 'command_label'):
                command = event_data.get('command', 'No command')
                confidence = event_data.get('confidence', 0)
                
                if self.using_pyqt:
                    voice_frame.command_label.setText(f"Command: {command} (Confidence: {confidence:.1f}%)")
                elif self.using_tkinter:
                    voice_frame.command_label.config(text=f"Command: {command} (Confidence: {confidence:.1f}%)")
            
            # Update command history display if it exists
            if hasattr(voice_frame, 'command_history'):
                if self.using_pyqt:
                    # Clear and update list
                    voice_frame.command_history.clear()
                    for cmd in self.voice_command_history:
                        timestamp = cmd.get('timestamp', 'Unknown')
                        command = cmd.get('command', 'Unknown')
                        confidence = cmd.get('confidence', 0)
                        
                        voice_frame.command_history.addItem(
                            f"[{timestamp}] {command} (Confidence: {confidence:.1f}%)"
                        )
                elif self.using_tkinter:
                    # Clear and update listbox
                    voice_frame.command_history.delete(0, 'end')
                    for cmd in self.voice_command_history:
                        timestamp = cmd.get('timestamp', 'Unknown')
                        command = cmd.get('command', 'Unknown')
                        confidence = cmd.get('confidence', 0)
                        
                        voice_frame.command_history.insert(
                            'end',
                            f"[{timestamp}] {command} (Confidence: {confidence:.1f}%)"
                        )
                        
        self.logger.debug(f"Updated voice command: {command if 'command' in event_data else 'None'}")
    except Exception as e:
        self.logger.error(f"Error updating voice command: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_voice_response(self, event_type: str, event_data: Dict[str, Any]):
    """Update AI response display when voice.response events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing AI voice response
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty voice response data")
            return
            
        # Add response to history if it's provided
        if 'response' in event_data:
            response = event_data['response']
            timestamp = event_data.get('timestamp', 'Unknown')
            
            response_entry = {
                'response': response,
                'timestamp': timestamp,
                'command': event_data.get('command', 'Unknown')  # Original command if available
            }
            
            self.voice_response_history.append(response_entry)
            # Limit history size
            if len(self.voice_response_history) > 50:
                self.voice_response_history = self.voice_response_history[-50:]
            
            # Store in voice data
            self.voice_data['response_history'] = self.voice_response_history
            self.voice_data['latest_response'] = response
            
        # Update voice response display if voice tab is present
        if 'voice' in self.tab_frames:
            voice_frame = self.tab_frames['voice']
            
            # Update current response display if it exists
            if hasattr(voice_frame, 'response_label'):
                response = event_data.get('response', 'No response')
                
                if self.using_pyqt:
                    voice_frame.response_label.setText(f"Response: {response}")
                elif self.using_tkinter:
                    voice_frame.response_label.config(text=f"Response: {response}")
            
            # Update response history display if it exists
            if hasattr(voice_frame, 'response_history'):
                if self.using_pyqt:
                    # Clear and update list
                    voice_frame.response_history.clear()
                    for resp in self.voice_response_history:
                        timestamp = resp.get('timestamp', 'Unknown')
                        response = resp.get('response', 'Unknown')
                        command = resp.get('command', '')
                        
                        display = f"[{timestamp}] {response}"
                        if command:
                            display += f" (Command: {command})"
                            
                        voice_frame.response_history.addItem(display)
                elif self.using_tkinter:
                    # Clear and update listbox
                    voice_frame.response_history.delete(0, 'end')
                    for resp in self.voice_response_history:
                        timestamp = resp.get('timestamp', 'Unknown')
                        response = resp.get('response', 'Unknown')
                        command = resp.get('command', '')
                        
                        display = f"[{timestamp}] {response}"
                        if command:
                            display += f" (Command: {command})"
                            
                        voice_frame.response_history.insert('end', display)
                        
        self.logger.debug(f"Updated voice response: {response if 'response' in event_data else 'None'}")
    except Exception as e:
        self.logger.error(f"Error updating voice response: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def start_voice_recognition(self):
    """Initialize voice recognition services and start listening for commands."""
    try:
        self.logger.info("Starting voice recognition")
        
        # Update voice status
        self.voice_status = "connecting"
        
        # Connect to Redis Quantum Nexus on required port and password
        if hasattr(self, 'redis_client'):
            try:
                # Ensure Redis connection uses port 6380 with QuantumNexus2025 password
                await self.redis_client.initialize(
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    environment="voice"
                )
                self.logger.info("Connected to Redis Quantum Nexus on port 6380 for voice recognition")
            except Exception as redis_error:
                self.logger.error(f"Failed to connect to Redis Quantum Nexus: {redis_error}")
                self.voice_status = "disconnected"
                return False
        
        # Initialize voice service
        if self.event_bus:
            await self.event_bus.emit("initialize_voice_recognition")
            await self.event_bus.emit("request_voice_status")
            
        # Set initial recording state to not recording
        self.is_recording = False
        self.voice_status = "connected"
        return True
    except Exception as e:
        self.logger.error(f"Error starting voice recognition: {e}")
        self.voice_status = "error"
        import traceback
        self.logger.error(traceback.format_exc())
        return False
