"""
Kingdom AI Event Handler Integration

This module provides functionality to integrate event handlers into the MainWindow class
and ensure all tab frames display real-time data from their respective components.
"""

import inspect
import logging
import sys
import asyncio
import traceback

# Import specific functions instead of wildcard import
import gui.event_handler_implementations as event_handlers

# Import frame event handlers
from gui.frames.frame_event_handlers import (
    integrate_trading_frame,
    integrate_mining_frame,
    integrate_wallet_frame,
    integrate_vr_frame,
    integrate_thoth_frame,
    integrate_code_generator_frame,
    integrate_api_keys_frame
)

logger = logging.getLogger("KingdomAI.EventHandlerIntegration")

def integrate_event_handlers(main_window_class):
    """
    Integrate all event handler methods from event_handler_implementations.py into the MainWindow class.
    
    Args:
        main_window_class: The MainWindow class to integrate event handlers into
    """
    # Get all functions from the event_handler_implementations module
    handler_functions = {}
    for name, obj in inspect.getmembers(event_handlers):
        if inspect.isfunction(obj) and name.startswith('_handle_'):
            handler_functions[name] = obj
    
    # Add each handler function as a method to the MainWindow class
    for name, func in handler_functions.items():
        # Completely skip all duplicate handlers to prevent lint errors and runtime conflicts
        if hasattr(main_window_class, name):
            logger.info(f"Skipping duplicate handler: {name}")
            continue
            
        # Only add if the method doesn't already exist
        if not hasattr(main_window_class, name):
            logger.info(f"Adding event handler method: {name}")
            setattr(main_window_class, name, func)
        else:
            logger.info(f"Event handler method already exists: {name}")
            
    logger.info(f"Successfully integrated {len(handler_functions)} event handlers into MainWindow")
    return main_window_class


async def integrate_frame_event_handlers(main_window):
    """
    Integrate all tab frames with their respective components and ensure they display real-time data.
    
    This function applies the appropriate event handler integration to each frame to ensure
    it can properly connect to its component and display real-time data updates.
    
    Args:
        main_window: The MainWindow instance containing the frames
    """
    logger.info("Integrating frame event handlers for real-time data display")
    
    # Create a list of async tasks for frame integration
    tasks = []
    
    # Trading Frame
    if hasattr(main_window, 'trading_tab'):
        task = asyncio.create_task(integrate_trading_frame(main_window.trading_tab))
        tasks.append(task)
    
    # Mining Frame
    if hasattr(main_window, 'mining_tab'):
        task = asyncio.create_task(integrate_mining_frame(main_window.mining_tab))
        tasks.append(task)
    
    # Wallet Frame
    if hasattr(main_window, 'wallet_tab'):
        task = asyncio.create_task(integrate_wallet_frame(main_window.wallet_tab))
        tasks.append(task)
    
    # VR Frame
    if hasattr(main_window, 'vr_tab'):
        task = asyncio.create_task(integrate_vr_frame(main_window.vr_tab))
        tasks.append(task)
    
    # Thoth Frame
    if hasattr(main_window, 'ai_tab'):
        task = asyncio.create_task(integrate_thoth_frame(main_window.ai_tab))
        tasks.append(task)
    
    # Code Generator Frame
    if hasattr(main_window, 'code_tab'):
        task = asyncio.create_task(integrate_code_generator_frame(main_window.code_tab))
        tasks.append(task)
    
    # API Keys Frame
    if hasattr(main_window, 'settings_tab'):
        task = asyncio.create_task(integrate_api_keys_frame(main_window.settings_tab))
        tasks.append(task)
    
    # Execute all frame integrations concurrently
    if tasks:
        try:
            await asyncio.gather(*tasks)
            logger.info("All frame event handlers integrated successfully")
        except Exception as e:
            logger.error(f"Error integrating frame event handlers: {e}")
            traceback.print_exc()
    else:
        logger.warning("No frames to integrate event handlers for")
    
    return True
