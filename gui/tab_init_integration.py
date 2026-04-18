"""
Kingdom AI Tab Initialization Integration Module

This module integrates all individual tab initialization methods into the TabManager class.
It ensures all 10 tabs (Dashboard, Trading, Mining, Thoth AI, Code Generation, Voice, API Key,
Wallet, VR, and Settings) are properly initialized and connected to the event bus.
"""

import importlib
import logging
import sys
import os
from typing import Dict, Any, Callable, Coroutine, Optional, Union
import inspect

# Configure logging
logger = logging.getLogger("KingdomAI.TabIntegration")

def integrate_tab_initializers(tab_manager_instance):
    """
    Integrate all tab initialization methods into the TabManager instance.
    
    This function dynamically imports all tab initialization modules and adds their
    methods to the TabManager instance, replacing any existing implementations
    with comprehensive ones from dedicated modules.
    
    Args:
        tab_manager_instance: The TabManager instance to integrate with
    """
    logger.info("Integrating tab initialization methods into TabManager")
    
    # Define all tab modules to integrate
    tab_modules = [
        "dashboard_tab_init",
        "trading_tab_init",
        "mining_tab_init",
        "codegen_tab_init",
        "thoth_tab_init",
        "voice_tab_init",
        "apikey_tab_init",
        "wallet_tab_init",
        "vr_tab_init",
        "settings_tab_init"
    ]
    
    # Track successful integrations
    integrated_tabs = []
    
    for module_name in tab_modules:
        try:
            # Import the module
            module_path = f"gui.{module_name}"
            module = importlib.import_module(module_path)
            logger.info(f"Successfully imported {module_path}")
            
            # Find all methods in the module that contain "_init_" and "update_"
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj):
                    if "_init_" in name:
                        # Bind the initialization method to the TabManager instance
                        setattr(tab_manager_instance.__class__, name, obj)
                        logger.info(f"Integrated initialization method: {name}")
                        
                        # Add to integrated tabs if it's a primary method
                        tab_name = name.replace("_init_", "").replace("_tab", "")
                        if tab_name not in integrated_tabs:
                            integrated_tabs.append(tab_name)
                    
                    elif "update_" in name and any(tab in name for tab in ["dashboard", "trading", "mining", "wallet", "vr", "voice", "thoth", "api_key", "settings"]):
                        # Bind the update method to the TabManager instance
                        setattr(tab_manager_instance.__class__, name, obj)
                        logger.info(f"Integrated update method: {name}")
                        
        except ImportError as e:
            logger.error(f"Failed to import {module_name}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error integrating {module_name}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            continue
    
    # Verify all tabs were integrated
    expected_tabs = ["dashboard", "trading", "mining", "codegen", "thoth", "voice", "apikey", "wallet", "vr", "settings"]
    missing_tabs = [tab for tab in expected_tabs if tab not in integrated_tabs]
    
    if missing_tabs:
        logger.warning(f"Some tabs were not integrated: {missing_tabs}")
    else:
        logger.info("All tabs successfully integrated")
    
    # Apply consistent styling across all tabs
    apply_consistent_styling(tab_manager_instance)
    
    return integrated_tabs

def apply_consistent_styling(tab_manager_instance):
    """Apply consistent styling across all tabs for a cohesive user experience"""
    try:
        logger.info("Applying consistent styling across all tabs")
        
        # Check if styles module is available
        if hasattr(tab_manager_instance, 'styles') and tab_manager_instance.styles:
            # Apply global theme
            tab_manager_instance.styles.apply_theme()
            
            # Set consistent fonts across all widgets
            if tab_manager_instance.using_pyqt:
                # PyQt styling
                for tab_id, tab_frame in tab_manager_instance.tab_frames.items():
                    try:
                        tab_manager_instance.styles.apply_style(tab_frame, "tab")
                    except Exception as e:
                        logger.error(f"Error applying style to {tab_id}: {e}")
            else:
                # Tkinter styling
                for tab_id, tab_frame in tab_manager_instance.tab_frames.items():
                    try:
                        tab_manager_instance.styles.apply_style(tab_frame, "tab")
                    except Exception as e:
                        logger.error(f"Error applying style to {tab_id}: {e}")
        else:
            logger.warning("Styles module not available, skipping style application")
    except Exception as e:
        logger.error(f"Error applying consistent styling: {e}")
        import traceback
        logger.debug(traceback.format_exc())

def test_gui_functionality(tab_manager_instance):
    """Test the GUI for real-time updates, event handling, and UI responsiveness"""
    try:
        logger.info("Testing GUI functionality")
        
        # Test event bus connectivity
        if tab_manager_instance.event_bus:
            tab_manager_instance.event_bus.publish_sync("gui.test_event", {"message": "GUI test event"})
            logger.info("Event bus test successful")
        else:
            logger.warning("Event bus not available, skipping event test")
        
        # Test tab switching
        if tab_manager_instance.notebook:
            current_tab = tab_manager_instance.notebook.current()
            logger.info(f"Current tab: {current_tab}")
            
            # Try to switch to all tabs to verify they're accessible
            for tab_id in tab_manager_instance.tab_frames:
                try:
                    if tab_manager_instance.using_pyqt:
                        for i in range(tab_manager_instance.notebook.count()):
                            if tab_manager_instance.notebook.tabText(i) == tab_id:
                                tab_manager_instance.notebook.setCurrentIndex(i)
                                break
                    else:  # Tkinter
                        tab_manager_instance.notebook.select(tab_manager_instance.tab_frames[tab_id])
                    logger.info(f"Successfully switched to tab: {tab_id}")
                except Exception as e:
                    logger.error(f"Failed to switch to tab {tab_id}: {e}")
            
            # Restore original tab
            if tab_manager_instance.using_pyqt:
                for i in range(tab_manager_instance.notebook.count()):
                    if tab_manager_instance.notebook.tabText(i) == current_tab:
                        tab_manager_instance.notebook.setCurrentIndex(i)
                        break
            else:  # Tkinter
                tab_manager_instance.notebook.select(current_tab)
        else:
            logger.warning("Notebook not available, skipping tab switch test")
            
        # Test data requests for all tabs
        request_methods = [
            "request_dashboard_updates",
            "request_trading_status",
            "request_mining_status",
            "request_codegen_status",
            "request_thoth_status",
            "request_voice_status",
            "request_wallet_data",
            "request_api_key_data",
            "request_vr_updates"
        ]
        
        for method_name in request_methods:
            if hasattr(tab_manager_instance, method_name) and callable(getattr(tab_manager_instance, method_name)):
                try:
                    logger.info(f"Testing {method_name}")
                    method = getattr(tab_manager_instance, method_name)
                    
                    # If it's an async method, schedule it as an async task
                    if inspect.iscoroutinefunction(method):
                        tab_manager_instance._schedule_async_task(method())
                    else:
                        method()
                        
                    logger.info(f"{method_name} executed successfully")
                except Exception as e:
                    logger.error(f"Error executing {method_name}: {e}")
            else:
                logger.warning(f"{method_name} not available")
        
        logger.info("GUI functionality tests completed")
        
    except Exception as e:
        logger.error(f"Error testing GUI functionality: {e}")
        import traceback
        logger.debug(traceback.format_exc())
