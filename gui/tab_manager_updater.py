"""
Kingdom AI Tab Manager Updater

This script updates the TabManager class with all tab initialization methods
from individual modules and ensures proper integration of all tabs.

This is a one-time update script to integrate all tab modules directly into
the TabManager class.
"""

import logging
import os
import sys
import re
import shutil
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KingdomAI.TabManagerUpdater")

def update_tab_manager():
    """Updates tab_manager.py with all tab initialization imports and methods."""
    try:
        # Paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        tab_manager_path = os.path.join(base_dir, "tab_manager.py")
        backup_path = os.path.join(base_dir, f"tab_manager.py.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        # Create backup of tab_manager.py
        if os.path.exists(tab_manager_path):
            shutil.copy2(tab_manager_path, backup_path)
            logger.info(f"Created backup of tab_manager.py at {backup_path}")
        
        # Define import statement to add
        import_statement = """
# Tab initialization imports
from gui.dashboard_tab_init import _init_dashboard_tab, update_dashboard_data
from gui.trading_tab_init import _init_trading_tab, update_trading_data
from gui.mining_tab_init import _init_mining_tab, update_mining_data
from gui.codegen_tab_init import _init_codegen_tab, update_codegen_data
from gui.thoth_tab_init import _init_thoth_tab, update_thoth_data
from gui.voice_tab_init import _init_voice_tab, update_voice_data
from gui.apikey_tab_init import _init_api_keys_tab, update_api_key_data
from gui.wallet_tab_init import _init_wallet_tab, update_wallet_data
from gui.vr_tab_init import _init_vr_tab, update_vr_status
from gui.settings_tab_init import _init_settings_tab, update_settings_data
"""
        
        # Read the current file content
        with open(tab_manager_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Find a suitable location for the import - after the existing imports
        last_import_match = re.search(r'^(import|from)\s+[^\n]+$', content, re.MULTILINE)
        if last_import_match:
            insert_position = last_import_match.end()
            updated_content = content[:insert_position] + "\n" + import_statement + content[insert_position:]
        else:
            # If no imports found, add at the beginning of the file
            updated_content = import_statement + "\n" + content
        
        # Write the updated content
        with open(tab_manager_path, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        
        logger.info("Successfully updated tab_manager.py with all tab imports")
        return True
    
    except Exception as e:
        logger.error(f"Error updating tab_manager.py: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def verify_tab_initialization():
    """Verifies that all tab initialization methods are properly integrated."""
    try:
        # Paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        tab_manager_path = os.path.join(base_dir, "tab_manager.py")
        
        # Get the content
        with open(tab_manager_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Check that all imports are present
        required_imports = [
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
        
        missing_imports = []
        for imp in required_imports:
            if imp not in content:
                missing_imports.append(imp)
        
        if missing_imports:
            logger.warning(f"Missing imports in tab_manager.py: {missing_imports}")
            return False
        
        logger.info("All tab initialization methods are properly imported")
        return True
    
    except Exception as e:
        logger.error(f"Error verifying tab initialization: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def create_integration_test():
    """Creates a test script to verify proper integration of all tabs."""
    try:
        # Paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        test_path = os.path.join(base_dir, "test_tab_integration.py")
        
        # Use triple-single-quoted string so inner """ docstrings do not terminate the literal.
        test_code = '''
import logging
import asyncio
import sys
import os
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KingdomAI.TabIntegrationTest")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.tab_manager import TabManager
from gui.tab_init_integration import integrate_tab_initializers, test_gui_functionality

async def test_tab_manager_integration():
    """Test that all tabs are properly integrated into the TabManager."""
    try:
        logger.info("Creating TabManager instance")
        
        # Create TabManager instance
        tab_manager = TabManager()
        
        # Create the notebook
        success = tab_manager.create_notebook()
        if not success:
            logger.error("Failed to create notebook")
            return False
            
        # Integrate tab initializers
        logger.info("Integrating tab initializers")
        integrated_tabs = integrate_tab_initializers(tab_manager)
        logger.info(f"Integrated tabs: {integrated_tabs}")
        
        # Initialize default tabs
        logger.info("Initializing default tabs")
        await tab_manager._initialize_default_tabs()
        
        # Test GUI functionality
        logger.info("Testing GUI functionality")
        test_gui_functionality(tab_manager)
        
        logger.info("Tab integration test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in tab integration test: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Run the test
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(test_tab_manager_integration())
    
    if result:
        logger.info("All tabs successfully integrated and tested")
        sys.exit(0)
    else:
        logger.error("Tab integration test failed")
        sys.exit(1)
'''
        
        # Write the test script
        with open(test_path, 'w', encoding='utf-8') as file:
            file.write(test_code)
        
        logger.info(f"Created integration test script at {test_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error creating integration test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting TabManager update process")
    
    # Update tab_manager.py
    update_successful = update_tab_manager()
    
    if update_successful:
        # Verify updates
        verify_successful = verify_tab_initialization()
        
        if verify_successful:
            # Create integration test
            create_integration_test()
            logger.info("TabManager update process completed successfully")
        else:
            logger.error("Verification failed, tab_manager.py may need manual update")
    else:
        logger.error("Failed to update tab_manager.py")
