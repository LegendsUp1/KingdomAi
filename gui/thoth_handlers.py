#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Thoth AI Event Handlers Module
Contains implementation of Thoth AI event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("KingdomAI.ThothHandlers")

# Thoth AI event handler methods
async def update_thoth_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update Thoth AI status display when thoth.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing Thoth AI status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty Thoth AI status data")
            return
            
        # Update Thoth status
        if 'status' in event_data:
            self.thoth_status = event_data['status']
            self.thoth_data['status'] = self.thoth_status
            
        # Update Thoth status display if thoth tab is present
        if 'thoth' in self.tab_frames:
            thoth_frame = self.tab_frames['thoth']
            
            # Update status label if it exists
            if hasattr(thoth_frame, 'status_label'):
                if self.using_pyqt:
                    thoth_frame.status_label.setText(f"Thoth AI Status: {self.thoth_status}")
                elif self.using_tkinter:
                    thoth_frame.status_label.config(text=f"Thoth AI Status: {self.thoth_status}")
            
            # Update connection indicator if it exists
            if hasattr(thoth_frame, 'connection_indicator'):
                if self.thoth_status == "connected":
                    indicator_color = "green"
                elif self.thoth_status == "connecting":
                    indicator_color = "yellow"
                else:
                    indicator_color = "red"
                    
                if self.using_pyqt:
                    thoth_frame.connection_indicator.setStyleSheet(f"background-color: {indicator_color};")
                elif self.using_tkinter:
                    thoth_frame.connection_indicator.config(bg=indicator_color)
                    
        self.logger.debug(f"Updated Thoth AI status: {self.thoth_status}")
    except Exception as e:
        self.logger.error(f"Error updating Thoth AI status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_thoth_conversation(self, event_type: str, event_data: Dict[str, Any]):
    """Update conversation history when thoth.conversation events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing conversation information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty conversation data")
            return
            
        # Add message to conversation history if it's a new message
        if 'message' in event_data:
            message = event_data['message']
            self.thoth_conversation_history.append(message)
            # Limit history size
            if len(self.thoth_conversation_history) > 100:
                self.thoth_conversation_history = self.thoth_conversation_history[-100:]
            
            # Store in AI data
            self.thoth_data['conversation_history'] = self.thoth_conversation_history
            
        # Update conversation display if thoth tab is present
        if 'thoth' in self.tab_frames:
            thoth_frame = self.tab_frames['thoth']
            
            # Update conversation history display if it exists
            if hasattr(thoth_frame, 'conversation_text'):
                # Format the entire conversation history
                conversation_text = ""
                for msg in self.thoth_conversation_history:
                    speaker = msg.get('speaker', 'Unknown')
                    text = msg.get('text', '')
                    timestamp = msg.get('timestamp', '')
                    
                    # Add formatted message
                    conversation_text += f"[{timestamp}] {speaker}: {text}\n\n"
                
                if self.using_pyqt:
                    thoth_frame.conversation_text.setPlainText(conversation_text)
                    # Scroll to bottom
                    scrollbar = thoth_frame.conversation_text.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
                elif self.using_tkinter:
                    # Clear and set text
                    thoth_frame.conversation_text.delete(1.0, 'end')
                    thoth_frame.conversation_text.insert('end', conversation_text)
                    # Scroll to bottom
                    thoth_frame.conversation_text.see('end')
                    
        self.logger.debug(f"Updated conversation history with {len(self.thoth_conversation_history)} messages")
    except Exception as e:
        self.logger.error(f"Error updating conversation history: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_thoth_analysis(self, event_type: str, event_data: Dict[str, Any]):
    """Update market analysis display when thoth.analysis events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing market analysis information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty analysis data")
            return
            
        # Store analysis in AI data
        if 'analysis' in event_data:
            analysis = event_data['analysis']
            self.thoth_data['analysis'] = analysis
            
        # Update analysis display if thoth tab is present
        if 'thoth' in self.tab_frames:
            thoth_frame = self.tab_frames['thoth']
            
            # Update analysis display if it exists
            if hasattr(thoth_frame, 'analysis_text'):
                analysis_text = analysis.get('text', 'No analysis available') if analysis else 'No analysis available'
                
                if self.using_pyqt:
                    thoth_frame.analysis_text.setPlainText(analysis_text)
                elif self.using_tkinter:
                    # Clear and set text
                    thoth_frame.analysis_text.delete(1.0, 'end')
                    thoth_frame.analysis_text.insert('end', analysis_text)
            
            # Update sentiment indicator if it exists
            if hasattr(thoth_frame, 'sentiment_label') and analysis and 'sentiment' in analysis:
                sentiment = analysis['sentiment']
                
                if self.using_pyqt:
                    thoth_frame.sentiment_label.setText(f"Market Sentiment: {sentiment}")
                elif self.using_tkinter:
                    thoth_frame.sentiment_label.config(text=f"Market Sentiment: {sentiment}")
                    
        self.logger.debug("Updated Thoth AI analysis")
    except Exception as e:
        self.logger.error(f"Error updating analysis: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_thoth_recommendations(self, event_type: str, event_data: Dict[str, Any]):
    """Update trading recommendations display when thoth.recommendations events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing trading recommendations
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty recommendations data")
            return
            
        # Store recommendations in AI data
        if 'recommendations' in event_data:
            recommendations = event_data['recommendations']
            self.thoth_data['recommendations'] = recommendations
            
        # Update recommendations display if thoth tab is present
        if 'thoth' in self.tab_frames:
            thoth_frame = self.tab_frames['thoth']
            
            # Update recommendations list if it exists
            if hasattr(thoth_frame, 'recommendations_list'):
                if self.using_pyqt:
                    # Clear and update list
                    thoth_frame.recommendations_list.clear()
                    for rec in recommendations:
                        symbol = rec.get('symbol', 'Unknown')
                        action = rec.get('action', 'Unknown')
                        confidence = rec.get('confidence', 0)
                        price = rec.get('target_price', 0)
                        
                        thoth_frame.recommendations_list.addItem(
                            f"{symbol}: {action.upper()} (Confidence: {confidence:.1f}%) - Target: ${price:.2f}"
                        )
                elif self.using_tkinter:
                    # Clear and update listbox
                    thoth_frame.recommendations_list.delete(0, 'end')
                    for rec in recommendations:
                        symbol = rec.get('symbol', 'Unknown')
                        action = rec.get('action', 'Unknown')
                        confidence = rec.get('confidence', 0)
                        price = rec.get('target_price', 0)
                        
                        thoth_frame.recommendations_list.insert(
                            'end',
                            f"{symbol}: {action.upper()} (Confidence: {confidence:.1f}%) - Target: ${price:.2f}"
                        )
                        
        self.logger.debug(f"Updated Thoth AI recommendations with {len(recommendations) if recommendations else 0} recommendations")
    except Exception as e:
        self.logger.error(f"Error updating recommendations: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def initialize_thoth_ai(self):
    """Initialize Thoth AI services and connect to data feeds."""
    try:
        self.logger.info("Initializing Thoth AI")
        
        # Update Thoth status
        self.thoth_status = "connecting"
        
        # Connect to Redis Quantum Nexus on required port and password
        if hasattr(self, 'redis_client'):
            try:
                # Ensure Redis connection uses port 6380 with QuantumNexus2025 password
                await self.redis_client.initialize(
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    environment="thoth"
                )
                self.logger.info("Connected to Redis Quantum Nexus on port 6380 for Thoth AI")
            except Exception as redis_error:
                self.logger.error(f"Failed to connect to Redis Quantum Nexus: {redis_error}")
                self.thoth_status = "disconnected"
                return False
        
        # Request AI data
        if self.event_bus:
            await self.event_bus.emit("initialize_thoth")
            await self.event_bus.emit("request_thoth_status")
            await self.event_bus.emit("request_market_analysis")
            
        self.thoth_status = "connected"
        return True
    except Exception as e:
        self.logger.error(f"Error initializing Thoth AI: {e}")
        self.thoth_status = "error"
        import traceback
        self.logger.error(traceback.format_exc())
        return False
