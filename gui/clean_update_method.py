#!/usr/bin/env python3
"""Clean implementation of the update_tab_data method."""

def update_tab_data(self, tab_name, data):
    """Update tab data with information from event bus.
    
    Args:
        tab_name: Name of the tab to update
        data: Data payload from event bus
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Validate inputs
        if not self.tabs:
            self.logger.warning("No tabs initialized")
            return False
            
        if tab_name not in self.tabs:
            self.logger.warning(f"Tab '{tab_name}' not found")
            return False
            
        # Get tab content widget
        tab_widget = self.tabs[tab_name].get("content")
        
        # Call standard update method if available
        if tab_widget and hasattr(tab_widget, "update_with_data"):
            tab_widget.update_with_data(data)
            
        # Handle special tab types
        success = True
        
        if tab_name == "Trading":
            success = self._update_trading_tab_display(data)
        elif tab_name == "Mining":
            success = self._update_mining_tab_display(data)
        elif tab_name == "Dashboard":
            success = self._update_dashboard_tab_display(data)
            
        # Log result
        if success:
            self.logger.debug(f"Updated tab {tab_name}")
            
        return success
        
    except Exception as e:
        self.logger.error(f"Error updating {tab_name}: {e}")
        self.logger.error(traceback.format_exc())
        return False
