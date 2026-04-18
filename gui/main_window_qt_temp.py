def is_ready(self):
    """Check if GUI is ready.
    
    Implements GUIManager compatibility for status checks.
    
    Returns:
        bool: True if GUI is initialized and ready, False otherwise
    """
    return self.initialized
