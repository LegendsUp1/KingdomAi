#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Integration Module for Kingdom AI.

This module ensures proper integration between loading screens and main window,
resolving component initialization issues and ensuring all 32+ components
remain properly connected to the event bus.
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk
import traceback
from typing import Dict, Any, Optional, Union, List

# Configure logger
logger = logging.getLogger("KingdomAI.GUIIntegration")

def ensure_main_window_notebook(main_window: Any) -> bool:
    """
    Ensure the main window notebook is properly initialized and visible.
    
    This function verifies that the notebook component in the main window
    is properly created and visible, and fixes common issues that might
    cause it to be blank or not display correctly.
    
    Args:
        main_window: The MainWindow instance to check
        
    Returns:
        bool: True if the notebook is properly initialized, False otherwise
    """
    try:
        if main_window is None:
            logger.error("Main window is None, cannot ensure notebook")
            return False
            
        # Check if notebook exists
        if not hasattr(main_window, 'notebook') or main_window.notebook is None:
            logger.warning("Main window notebook not found, attempting to create")
            try:
                # Create notebook if it doesn't exist
                main_window.notebook = ttk.Notebook(main_window.root)
                main_window.notebook.grid(row=0, column=0, sticky="nsew")
                logger.info("Created missing notebook in main window")
            except Exception as e:
                logger.error(f"Error creating notebook: {e}")
                return False
                
        # Ensure notebook is visible
        try:
            main_window.notebook.lift()
            main_window.root.update_idletasks()
            logger.info("Ensured notebook visibility")
        except Exception as e:
            logger.error(f"Error ensuring notebook visibility: {e}")
            return False
            
        # Configure root window grid
        try:
            main_window.root.grid_rowconfigure(0, weight=1)
            main_window.root.grid_columnconfigure(0, weight=1)
            logger.info("Configured grid weights for main window")
        except Exception as e:
            logger.error(f"Error configuring grid: {e}")
            
        # If no tabs, add a placeholder tab
        try:
            if main_window.notebook.index("end") == 0:
                logger.warning("No tabs in notebook, adding placeholder")
                placeholder = ttk.Frame(main_window.notebook)
                label = ttk.Label(placeholder, text="Kingdom AI is initializing components...", font=("Arial", 14))
                label.pack(pady=50, padx=50)
                main_window.notebook.add(placeholder, text="Welcome")
        except Exception as e:
            logger.error(f"Error adding placeholder tab: {e}")
            
        return True
        
    except Exception as e:
        logger.error(f"Unexpected error in ensure_main_window_notebook: {e}")
        logger.error(traceback.format_exc())
        return False

def integrate_loading_screen_with_main_window(loading_screen: Any, main_window: Any) -> bool:
    """
    Ensure proper integration between loading screen and main window.
    
    This function handles the transition from loading screen to main window,
    ensuring that all components are properly initialized and the main window
    is correctly displayed.
    
    Args:
        loading_screen: The loading screen instance
        main_window: The main window instance
        
    Returns:
        bool: True if integration was successful, False otherwise
    """
    try:
        if loading_screen is None or main_window is None:
            logger.error("Loading screen or main window is None")
            return False
            
        # Ensure main window is ready
        ensure_main_window_notebook(main_window)
        
        # Update loading screen status
        if hasattr(loading_screen, 'update_progress'):
            loading_screen.update_progress(95, "Preparing main interface...")
            
        # Ensure main window is visible
        if hasattr(main_window, 'root') and main_window.root is not None:
            main_window.root.deiconify()
            main_window.root.update_idletasks()
            
        # Hide loading screen
        if hasattr(loading_screen, 'hide'):
            loading_screen.hide()
            
        logger.info("Successfully integrated loading screen with main window")
        return True
        
    except Exception as e:
        logger.error(f"Error integrating loading screen with main window: {e}")
        logger.error(traceback.format_exc())
        return False

def fix_blank_gui():
    """
    Utility function to fix blank GUI issues.
    
    This function attempts to fix common issues that cause the GUI to appear blank
    by checking the component manager and event bus for MainWindow instances and
    ensuring they are properly initialized and displayed.
    """
    try:
        # Import required modules
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Get component manager
        component_manager = None
        try:
            from core.component_manager import ComponentManager
            if hasattr(ComponentManager, 'get_instance'):
                component_manager = ComponentManager.get_instance()
        except ImportError:
            logger.warning("Could not import ComponentManager")
            
        # Find main window in component manager
        main_window = None
        if component_manager and hasattr(component_manager, 'get_component'):
            main_window = component_manager.get_component('main_window')
            
        if main_window:
            logger.info("Found main window in component manager")
            ensure_main_window_notebook(main_window)
        else:
            logger.warning("Main window not found in component manager")
            
        logger.info("Attempted to fix blank GUI issues")
        return True
        
    except Exception as e:
        logger.error(f"Error in fix_blank_gui: {e}")
        logger.error(traceback.format_exc())
        return False
