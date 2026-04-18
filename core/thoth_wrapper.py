#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Thoth AI Wrapper Module

This module ensures proper import and initialization of Thoth AI components
by providing reliable imports and fallbacks.
"""

import os
import sys
import logging
import importlib.util
import traceback

# Create logger
logger = logging.getLogger("KingdomAI.ThothWrapper")

class ThothWrapper:
    """
    Wrapper class for ensuring reliable Thoth AI integration and initialization
    """
    
    @staticmethod
    def import_thoth():
        """
        Import the ThothAI class using a systematic approach.
        
        Returns:
            ThothAI class or None if not found
        """
        # Initialize to None so we can check if any import succeeds
        ThothAI = None
        
        # Define possible import paths in order of preference
        import_paths = [
            "core.thoth.ThothAI",
            "core.thothai.ThothAI", 
            "components.thoth.ThothAI", 
            "ai.thoth_ai.ThothAI", 
            "ai.thoth.ThothAI",
            "core.thoth.Thoth"
        ]
        
        # Try each import path
        for import_path in import_paths:
            try:
                logger.debug(f"Attempting to import {import_path}")
                module_parts = import_path.split('.')
                class_name = module_parts[-1]
                module_path = '.'.join(module_parts[:-1])
                
                # Dynamic import
                module = __import__(module_path, fromlist=[class_name])
                imported_class = getattr(module, class_name)
                
                # If we're importing Thoth instead of ThothAI, alias it
                if class_name == "Thoth":
                    ThothAI = imported_class
                    logger.info(f"Successfully imported {class_name} from {module_path} as ThothAI")
                else:
                    ThothAI = imported_class
                    logger.info(f"Successfully imported {class_name} from {module_path}")
                
                # Exit the loop if import succeeds
                break
            except (ImportError, AttributeError) as e:
                logger.debug(f"Failed to import {import_path}: {e}")
        
        # If standard imports fail, try a more aggressive approach with importlib
        if ThothAI is None:
            try:
                # Additional search paths
                additional_paths = [
                    os.path.abspath(os.path.dirname(os.path.dirname(__file__))),  # Project root
                    os.path.abspath(os.path.dirname(__file__)),  # core directory
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'components')),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai')),
                ]
                
                # Add paths to sys.path if not already there
                for path in additional_paths:
                    if path not in sys.path:
                        sys.path.append(path)
                
                # The most likely module locations
                modules_to_try = [
                    ("thoth.py", ["ThothAI", "Thoth"]), 
                    ("thothai.py", ["ThothAI"]),
                    ("thoth_ai.py", ["ThothAI"]),
                ]
                
                # Try every combination of path and module
                for base_path in additional_paths:
                    for module_file, class_names in modules_to_try:
                        module_path = os.path.join(base_path, module_file)
                        if os.path.exists(module_path):
                            logger.info(f"Found potential module at {module_path}")
                            
                            try:
                                spec = importlib.util.spec_from_file_location("thoth_module", module_path)
                                if spec and spec.loader:
                                    module = importlib.util.module_from_spec(spec)
                                    spec.loader.exec_module(module)
                                    
                                    # Try each potential class name
                                    for class_name in class_names:
                                        if hasattr(module, class_name):
                                            ThothAI = getattr(module, class_name)
                                            logger.info(f"Successfully imported {class_name} from {module_path}")
                                            return ThothAI
                            except Exception as e:
                                logger.debug(f"Error importing from {module_path}: {e}")
            except Exception as e:
                logger.error(f"Error in advanced import attempt: {e}")
                logger.debug(traceback.format_exc())
        
        return ThothAI

    @staticmethod
    def import_thoth_gui_integration():
        """
        Import the ThothGUIIntegration class reliably
        
        Returns:
            ThothGUIIntegration class or None if not found
        """
        ThothGUIIntegration = None
        
        try:
            # Try direct import first
            from core.thoth_gui_integration import ThothGUIIntegration
            return ThothGUIIntegration
        except ImportError:
            pass
            
        # Try more approaches using importlib for the gui integration
        try:
            # Try to find thoth_gui_integration.py in core directory
            module_path = os.path.join(os.path.dirname(__file__), 'thoth_gui_integration.py')
            if os.path.exists(module_path):
                spec = importlib.util.spec_from_file_location("thoth_gui_integration", module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "ThothGUIIntegration"):
                        ThothGUIIntegration = getattr(module, "ThothGUIIntegration")
                        logger.info(f"Successfully imported ThothGUIIntegration from {module_path}")
        except Exception as e:
            logger.error(f"Error importing ThothGUIIntegration: {e}")
            logger.debug(traceback.format_exc())
            
        return ThothGUIIntegration


# Create singleton instance
_wrapper_instance = ThothWrapper()

# Function to get ThothAI class
def get_thoth_ai():
    """Get the ThothAI class using the singleton wrapper instance."""
    return _wrapper_instance.import_thoth()

# Function to get ThothGUIIntegration class
def get_thoth_gui_integration():
    """Get the ThothGUIIntegration class using the singleton wrapper instance."""
    return _wrapper_instance.import_thoth_gui_integration()

# Function to initialize Thoth AI system
def initialize_thoth(event_bus=None, config=None):
    """
    Initialize the Thoth AI system with the event bus and configuration.
    
    Args:
        event_bus: The event bus for component communication
        config: Configuration dictionary
        
    Returns:
        dict: Thoth system components including ThothAI and ThothGUIIntegration instances
    """
    logger.info("Initializing Thoth AI system")
    components = {}
    
    # Get the Thoth classes
    ThothAI = get_thoth_ai()
    ThothGUIIntegration = get_thoth_gui_integration()
    
    if ThothAI:
        try:
            # Create ThothAI instance
            thoth_ai = ThothAI(event_bus=event_bus, config=config)
            components['thoth_ai'] = thoth_ai
            logger.info("ThothAI instance created successfully")
            
            # Initialize ThothAI
            try:
                thoth_ai.initialize()
                logger.info("ThothAI initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing ThothAI: {e}")
                logger.debug(traceback.format_exc())
        except Exception as e:
            logger.error(f"Error creating ThothAI instance: {e}")
            logger.debug(traceback.format_exc())
    else:
        logger.warning("ThothAI class not found, Thoth AI functionality will be limited")
    
    if ThothGUIIntegration and event_bus:
        try:
            # Create ThothGUIIntegration instance
            thoth_gui = ThothGUIIntegration(event_bus=event_bus, config=config)
            components['thoth_gui'] = thoth_gui
            logger.info("ThothGUIIntegration instance created successfully")
            
            # Initialize ThothGUIIntegration
            try:
                thoth_gui.initialize()
                logger.info("ThothGUIIntegration initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing ThothGUIIntegration: {e}")
                logger.debug(traceback.format_exc())
        except Exception as e:
            logger.error(f"Error creating ThothGUIIntegration instance: {e}")
            logger.debug(traceback.format_exc())
    else:
        if not ThothGUIIntegration:
            logger.warning("ThothGUIIntegration class not found")
        if not event_bus:
            logger.warning("Event bus not provided for ThothGUIIntegration")
            
    return components

# Define public exports
__all__ = ["ThothWrapper", "get_thoth_ai", "get_thoth_gui_integration", "initialize_thoth"]
