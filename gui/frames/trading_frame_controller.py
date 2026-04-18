"""
Controller module for integrating all TradingFrame components.
This file brings together all the methods needed to complete the TradingFrame class
with full Redis Quantum Nexus integration on port 6380.
"""

import importlib
import logging
from pathlib import Path

class TradingFrameController:
    """
    Controller class that integrates all components for the TradingFrame.
    """
    @staticmethod
    def integrate_methods(trading_frame_class):
        """
        Integrate all methods from helper modules into the TradingFrame class.
        
        Args:
            trading_frame_class: The TradingFrame class to integrate methods into
            
        Returns:
            bool: True if integration was successful, False otherwise
        """
        logger = logging.getLogger("TradingFrameController")
        logger.info("Integrating TradingFrame components")
        
        try:
            # Base directory where helper files are located
            base_dir = Path(__file__).parent
            
            # List of helper modules and their classes
            helper_modules = [
                ("trading_frame_methods", "TradingFrameMethods"),
                ("trading_frame_handlers", "TradingFrameHandlers"),
                ("trading_frame_update_ui", "TradingFrameUpdateUI"),
                ("trading_frame_async", "TradingFrameAsync")
            ]
            
            for module_name, class_name in helper_modules:
                try:
                    # Import the module
                    module = importlib.import_module(f"gui.frames.{module_name}")
                    
                    # Get the class from the module
                    helper_class = getattr(module, class_name)
                    
                    # Get all methods from the helper class
                    for method_name in dir(helper_class):
                        # Skip private methods and non-methods
                        if method_name.startswith('__') or not callable(getattr(helper_class, method_name)):
                            continue
                        
                        # Get the method from the helper class
                        method = getattr(helper_class, method_name)
                        
                        # Add the method to the trading frame class
                        setattr(trading_frame_class, method_name, method)
                        
                    logger.info(f"Successfully integrated methods from {class_name}")
                    
                except ImportError as e:
                    logger.error(f"Failed to import module {module_name}: {e}")
                    return False
                except AttributeError as e:
                    logger.error(f"Failed to get class {class_name} from module {module_name}: {e}")
                    return False
            
            logger.info("All TradingFrame components integrated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error integrating TradingFrame components: {e}")
            return False
    
    @staticmethod
    def integrate_and_update(trading_frame_class):
        """
        Integrate methods and update the TradingFrame class with critical Redis configuration.
        
        Args:
            trading_frame_class: The TradingFrame class to update
            
        Returns:
            bool: True if integration was successful, False otherwise
        """
        # First integrate methods
        success = TradingFrameController.integrate_methods(trading_frame_class)
        if not success:
            return False
        
        # Add class-level Redis configuration constants to ensure consistency
        trading_frame_class.REDIS_PORT = 6380  # Mandatory port 6380
        trading_frame_class.REDIS_PASSWORD = 'QuantumNexus2025'
        trading_frame_class.REDIS_MANDATORY = True  # No fallbacks
        
        return True
