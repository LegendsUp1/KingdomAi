# Minimal console component
import logging
import sys

logger = logging.getLogger("gui.console")

class Console:
    '''Simple console component'''
    
    def __init__(self):
        self.is_initialized = False
        logger.info("Console component created")
    
    def initialize(self):
        '''Initialize the console component'''
        if self.is_initialized:
            return True
        
        logger.info("Initializing Console component")
        self.is_initialized = True
        return True
    
    def output(self, message):
        '''Output a message to the console'''
        print(message)
        return True
    
    def shutdown(self):
        '''Shutdown the console component'''
        logger.info("Shutting down Console component")
        self.is_initialized = False
        return True