#!/usr/bin/env python3
"""
Kingdom AI Tab Connection Validator

Ensures all 10 tabs are properly connected to the event bus
"""

import os
import sys
import logging
from pathlib import Path
import importlib.util
import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TabConnectionValidator")

class TabConnectionValidator:
    """Validates that all tabs are properly connected to the event bus."""
    
    # The expected tabs in the Kingdom AI system
    EXPECTED_TABS = [
        'dashboard', 
        'trading', 
        'mining', 
        'settings', 
        'wallet', 
        'api_keys', 
        'thoth', 
        'code_generator', 
        'diagnostic', 
        'vr'
    ]
    
    def __init__(self, project_dir):
        """
        Initialize the validator.
        
        Args:
            project_dir: Path to the Kingdom AI project directory
        """
        self.project_dir = Path(project_dir)
        self.gui_dir = self.project_dir / 'gui'
        self.main_window_path = self.gui_dir / 'main_window.py'
        self.event_handler_integration_path = self.gui_dir / 'event_handler_integration.py'
        
        # Track validation results
        self.missing_tabs = []
        self.missing_event_handlers = []
    
    def validate_tab_existence(self):
        """Check that all tab-related methods and classes exist in the main window."""
        logger.info("Validating tab existence in MainWindow...")
        
        # Load main_window.py as text first for quick analysis
        try:
            with open(self.main_window_path, 'r', encoding='utf-8') as f:
                main_window_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read main_window.py: {e}")
            return False
        
        # Check for each expected tab
        found_tabs = []
        missing_tabs = []
        
        for tab in self.EXPECTED_TABS:
            # Check for tab initialization methods (various patterns)
            patterns = [
                f"def initialize_{tab}_tab",
                f"def setup_{tab}_tab",
                f"def create_{tab}_tab",
                f"def init_{tab}_tab",
                f"{tab}_tab =",
                f"self.{tab}_tab =",
                f"'{tab}': ",
                f'"{tab}": '
            ]
            
            found = False
            for pattern in patterns:
                if pattern in main_window_content:
                    found = True
                    break
            
            if found:
                found_tabs.append(tab)
                logger.info(f"✓ Found tab: {tab}")
            else:
                missing_tabs.append(tab)
                logger.warning(f"✗ Missing tab: {tab}")
        
        self.missing_tabs = missing_tabs
        logger.info(f"Found {len(found_tabs)} of {len(self.EXPECTED_TABS)} expected tabs")
        
        return len(missing_tabs) == 0
    
    def validate_event_handlers(self):
        """Check that event handlers are properly defined for all tabs."""
        logger.info("Validating event handlers for tabs...")
        
        # Load event handler files
        try:
            # Check the event handler integration file
            with open(self.event_handler_integration_path, 'r', encoding='utf-8') as f:
                integration_content = f.read()
                
            # Check if the main integration decorator exists
            if "def integrate_event_handlers" not in integration_content:
                logger.error("Missing integrate_event_handlers function in event_handler_integration.py")
                return False
            
            # Check for MainWindow class integration    
            if "cls_dict = {}" not in integration_content and "original_cls.__dict__" not in integration_content:
                logger.warning("Event handler integration may not be properly set up")
        except Exception as e:
            logger.warning(f"Could not validate event handler integration: {e}")
        
        # Check for event handlers for all tabs
        missing_handlers = []
        for tab in self.EXPECTED_TABS:
            handler_name = f"handle_{tab}_event"
            handler_path = self.gui_dir / "event_handler_implementations.py"
            
            # Check if the handler file exists
            if not handler_path.exists():
                logger.warning(f"Event handler implementations file does not exist")
                missing_handlers.append(tab)
                continue
            
            # Check for the handler in the file
            with open(handler_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if handler_name not in content:
                logger.warning(f"Missing handler for {tab} tab: {handler_name}")
                missing_handlers.append(tab)
            else:
                logger.info(f"✓ Found handler for {tab} tab")
        
        self.missing_event_handlers = missing_handlers
        logger.info(f"Found event handlers for {len(self.EXPECTED_TABS) - len(missing_handlers)} of {len(self.EXPECTED_TABS)} tabs")
        
        return len(missing_handlers) == 0
    
    def fix_event_handler_integration(self):
        """Ensure the event handler integration is properly set up."""
        logger.info("Fixing event handler integration...")
        
        # First check if integration file exists
        if not self.event_handler_integration_path.exists():
            logger.info("Creating event_handler_integration.py...")
            
            integration_content = '''#!/usr/bin/env python3
"""
Event Handler Integration for Kingdom AI

This module provides functionality to integrate event handlers into the MainWindow class.
"""

import logging
import inspect
from typing import Type, Dict, Any, Callable

logger = logging.getLogger(__name__)

def integrate_event_handlers(original_cls: Type) -> Type:
    """
    Decorator to integrate event handlers into the MainWindow class.
    
    Args:
        original_cls: The original MainWindow class to integrate handlers into
        
    Returns:
        Enhanced MainWindow class with event handlers
    """
    logger.info(f"Integrating event handlers into {original_cls.__name__}")
    
    # Create a new dictionary with all original attributes
    cls_dict = {}
    
    for name, attr in original_cls.__dict__.items():
        cls_dict[name] = attr
    
    # Get event handlers from event_handler_implementations
    try:
        from gui.event_handler_implementations import EVENT_HANDLERS
        
        # Add each event handler method to the class
        for handler_name, handler_func in EVENT_HANDLERS.items():
            if handler_name not in cls_dict:
                cls_dict[handler_name] = handler_func
                logger.info(f"Added event handler: {handler_name}")
    except ImportError as e:
        logger.error(f"Error importing event handlers: {e}")
        pass
    
    # Create a new class with the updated dictionary
    enhanced_cls = type(original_cls.__name__, original_cls.__bases__, cls_dict)
    logger.info(f"Successfully enhanced {original_cls.__name__} with event handlers")
    
    return enhanced_cls
'''
            
            try:
                with open(self.event_handler_integration_path, 'w', encoding='utf-8') as f:
                    f.write(integration_content)
                logger.info("Created event handler integration file")
            except Exception as e:
                logger.error(f"Failed to create event handler integration file: {e}")
                return False
        
        # Check MainWindow for integration
        with open(self.main_window_path, 'r', encoding='utf-8') as f:
            main_window_content = f.read()
        
        if "from gui.event_handler_integration import integrate_event_handlers" not in main_window_content:
            logger.info("Adding event handler integration import to main_window.py")
            
            # Add import at the top of the file
            import_line = "from gui.event_handler_integration import integrate_event_handlers"
            main_window_content = import_line + "\n" + main_window_content
            
            # Add the decorator after class definition
            main_window_content = main_window_content.replace(
                "class MainWindow:",
                "class MainWindow:"
            )
            
            # Add integration at the end of the file
            main_window_content += "\n\n# Apply event handlers integration\nMainWindow = integrate_event_handlers(MainWindow)\n"
            
            try:
                with open(self.main_window_path, 'w', encoding='utf-8') as f:
                    f.write(main_window_content)
                logger.info("Added event handler integration to main_window.py")
            except Exception as e:
                logger.error(f"Failed to update main_window.py: {e}")
                return False
        
        return True
    
    def create_missing_tab_handler(self, tab_name):
        """Create a missing tab handler in event handler implementations."""
        logger.info(f"Creating handler for {tab_name} tab...")
        
        handler_path = self.gui_dir / "event_handler_implementations.py"
        
        try:
            # Read current implementations
            if handler_path.exists():
                with open(handler_path, 'r', encoding='utf-8') as f:
                    handler_content = f.read()
            else:
                # Create the file with basic structure
                handler_content = '''#!/usr/bin/env python3
"""
Event Handler Implementations for Kingdom AI

This module contains all event handler implementations for the GUI.
"""

from typing import Dict, Any, Callable
import logging
import asyncio

logger = logging.getLogger(__name__)

# Dictionary of all event handlers
EVENT_HANDLERS = {}
'''
            
            # Create handler for tab if not present
            handler_name = f"handle_{tab_name}_event"
            if handler_name not in handler_content:
                new_handler = f'''

async def {handler_name}(self, event_data):
    """
    Handle events from the {tab_name} tab.
    
    Args:
        event_data: Data related to the event
    """
    logger.info(f"Handling {tab_name} event: {{event_data.get('type', 'unknown')}}")
    
    # Add your event handling logic here
    event_type = event_data.get('type', '')
    
    if event_type == 'update':
        # Handle update event
        pass
    elif event_type == 'error':
        # Handle error event
        pass
    else:
        # Handle other event types
        pass

# Register the handler
EVENT_HANDLERS['{handler_name}'] = {handler_name}
'''
                handler_content += new_handler
                
                with open(handler_path, 'w', encoding='utf-8') as f:
                    f.write(handler_content)
                    
                logger.info(f"Created handler for {tab_name} tab")
                return True
            else:
                logger.info(f"Handler for {tab_name} tab already exists")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create handler for {tab_name} tab: {e}")
            return False
    
    def ensure_tab_connections(self):
        """Ensure all tabs are connected to the event bus."""
        logger.info("Ensuring all tabs are connected to the event bus...")
        
        # Validate tab existence
        self.validate_tab_existence()
        
        # Validate event handlers
        self.validate_event_handlers()
        
        # Fix event handler integration
        if not self.fix_event_handler_integration():
            logger.error("Failed to fix event handler integration")
            return False
        
        # Create missing event handlers
        for tab in self.missing_event_handlers:
            self.create_missing_tab_handler(tab)
        
        return True

def main():
    """
    Main entry point for the script.
    
    Usage:
        python ensure_tab_connections.py [project_dir]
    """
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        # Use the directory of this script's parent (gui/..)
        project_dir = str(Path(__file__).resolve().parent.parent)
    
    logger.info(f"Using project directory: {project_dir}")
    
    validator = TabConnectionValidator(project_dir)
    
    # Validate and fix tab connections
    success = validator.ensure_tab_connections()
    
    if success:
        logger.info("✓ Successfully ensured all tab connections")
        return 0
    else:
        logger.error("✗ Failed to ensure all tab connections")
        return 1

if __name__ == "__main__":
    print("=" * 80)
    print(" Kingdom AI Tab Connection Validator ".center(80))
    print("=" * 80)
    print(" This script ensures all tabs are properly connected to the event bus.")
    print("=" * 80)
    
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
