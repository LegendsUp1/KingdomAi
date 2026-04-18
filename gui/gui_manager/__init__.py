#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Manager Module Initialization
Provides access to the GUI Manager singleton.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Singleton instance
_gui_manager_instance = None

# Import GUIManager class directly for easy access
from .gui_manager import GUIManager

def get_gui_manager():
    """
    Get the singleton instance of the GUI Manager.
    
    Returns:
        The GUIManager instance or None if not initialized
    """
    global _gui_manager_instance
    
    if _gui_manager_instance is None:
        # Try to import and initialize
        try:
            from .gui_manager import GUIManager
            _gui_manager_instance = GUIManager.get_instance()
            logger.info("Created new GUI Manager instance")
        except ImportError:
            logger.warning("Could not import GUIManager class")
        except Exception as e:
            logger.error(f"Error initializing GUI Manager: {e}")
    
    return _gui_manager_instance
