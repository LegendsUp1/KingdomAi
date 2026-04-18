#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VR Frame fixes for Kingdom AI system.

This script contains methods to fix and sanitize attribute access in the VRFrame class.
"""

import logging
import tkinter as tk
from tkinter import ttk
import asyncio

logger = logging.getLogger(__name__)

def fix_refresh_visualization(frame):
    """Fix the visualization refresh method to handle null canvas.
    
    Args:
        frame: The VRFrame instance
    """
    try:
        # Ensure canvas exists
        if not hasattr(frame, 'visualization_canvas') or frame.visualization_canvas is None:
            logger.warning("Visualization canvas not available")
            return
            
        # Clear existing visualization
        frame.visualization_canvas.delete("all")
        
        # Get canvas dimensions safely
        try:
            width = frame.visualization_canvas.winfo_width()
            height = frame.visualization_canvas.winfo_height()
            if width <= 0 or height <= 0:
                width, height = 300, 200  # Default dimensions
        except Exception:
            width, height = 300, 200  # Default dimensions
        
        # Draw grid lines
        for i in range(0, width, 20):
            frame.visualization_canvas.create_line(i, 0, i, height, fill="#EEEEEE")
        for i in range(0, height, 20):
            frame.visualization_canvas.create_line(0, i, width, i, fill="#EEEEEE")
            
        # Draw center reference
        frame.visualization_canvas.create_oval(
            width/2-5, height/2-5, width/2+5, height/2+5, 
            fill="#AAAAAA", outline="#666666", tags="center"
        )
                           
        # Draw tracking data points if available
        if hasattr(frame, 'tracking_data') and frame.tracking_data:
            for device, position in frame.tracking_data.items():
                if isinstance(position, dict) and 'x' in position and 'y' in position:
                    x, y = position['x'], position['y']
                    # Scale and offset to canvas coordinates
                    canvas_x = width/2 + x * 50
                    canvas_y = height/2 - y * 50  # Y is inverted in canvas
                    draw_tracking_point(frame, canvas_x, canvas_y, device)
    except Exception as e:
        logger.error(f"Error refreshing visualization: {e}")

def draw_tracking_point(frame, x, y, label):
    """Draw a tracking point on the visualization canvas with null safety.
    
    Args:
        frame: The VRFrame instance
        x: X position
        y: Y position
        label: Point label
    """
    try:
        if not hasattr(frame, 'visualization_canvas') or frame.visualization_canvas is None:
            return
            
        # Draw point
        frame.visualization_canvas.create_oval(
            x-10, y-10, x+10, y+10, 
            fill="#3366CC", outline="#0033CC", tags="tracking"
        )
                           
        # Draw label
        frame.visualization_canvas.create_text(
            x, y-20, text=label, fill="#333333", tags="tracking"
        )
    except Exception as e:
        logger.error(f"Error drawing tracking point: {e}")

def update_ui_controls_state(frame):
    """Update UI controls based on connection state with safe attribute access.
    
    Args:
        frame: The VRFrame instance
    """
    try:
        # Determine connection status safely
        is_connected = hasattr(frame, 'connected') and frame.connected
        
        # Update connection controls
        safe_config(frame, 'connect_button', {'state': 'disabled' if is_connected else 'normal'})
        safe_config(frame, 'disconnect_button', {'state': 'normal' if is_connected else 'disabled'})
        
        # Update tracking controls
        is_tracking = hasattr(frame, 'tracking_enabled') and frame.tracking_enabled
        safe_config(frame, 'tracking_checkbox', {'state': 'normal' if is_connected else 'disabled'})
        safe_config(frame, 'calibrate_button', {'state': 'normal' if is_connected and is_tracking else 'disabled'})
        safe_config(frame, 'reset_tracking_button', {'state': 'normal' if is_connected and is_tracking else 'disabled'})
        
        # Update passthrough controls
        passthrough_enabled = False
        if hasattr(frame, 'passthrough_var') and frame.passthrough_var is not None:
            try:
                passthrough_enabled = frame.passthrough_var.get()
            except Exception:
                pass
        
        safe_config(frame, 'passthrough_checkbox', {'state': 'normal' if is_connected else 'disabled'})
        safe_config(frame, 'passthrough_slider', {'state': 'normal' if is_connected and passthrough_enabled else 'disabled'})
        
        # Update environment controls
        is_env_loaded = hasattr(frame, 'environment_loaded') and frame.environment_loaded
        safe_config(frame, 'environment_dropdown', {'state': 'normal' if is_connected else 'disabled'})
        safe_config(frame, 'load_env_button', {'state': 'normal' if is_connected else 'disabled'})
        safe_config(frame, 'customize_env_button', {'state': 'normal' if is_connected and is_env_loaded else 'disabled'})
    except Exception as e:
        logger.error(f"Error updating UI controls: {e}")

def safe_config(frame, attr_name, config_dict):
    """Safely configure a widget attribute if it exists.
    
    Args:
        frame: The VRFrame instance
        attr_name: Name of the attribute to access
        config_dict: Configuration dictionary for widget
    """
    try:
        attr = getattr(frame, attr_name, None)
        if attr is not None and hasattr(attr, 'config'):
            attr.config(**config_dict)
    except Exception as e:
        logger.debug(f"Could not configure {attr_name}: {e}")

def run_gui_integration_tests(test_path):
    """Run the GUI integration tests.
    
    Args:
        test_path: Path to the test file
    
    Returns:
        bool: True if tests passed, False otherwise
    """
    import subprocess
    import os
    
    try:
        # Ensure the test path exists
        if not os.path.exists(test_path):
            logger.error(f"Test file not found: {test_path}")
            return False
            
        # Run the tests
        logger.info(f"Running GUI integration tests from: {test_path}")
        result = subprocess.run(
            ['python', test_path], 
            capture_output=True, 
            text=True,
            check=False
        )
        
        # Log the output
        logger.info("Test output:")
        logger.info(result.stdout)
        
        if result.stderr:
            logger.error("Test errors:")
            logger.error(result.stderr)
            
        # Check if tests passed
        if result.returncode == 0:
            logger.info("All GUI integration tests passed!")
            return True
        else:
            logger.error(f"Tests failed with code: {result.returncode}")
            return False
    except Exception as e:
        logger.error(f"Error running GUI integration tests: {e}")
        return False
