# Enhanced GUIManager implementation for PyQt6 and TK compatibility
import logging
import threading
from typing import Dict, Any, Optional, Union, List, Callable
import sys
import os

logger = logging.getLogger("gui.gui_manager")

def get_gui_manager():
    """Get the default GUI manager instance
    
    Returns:
        GUIManager: The default GUI manager instance
    """
    # Forward to the class method
    return GUIManager.get_instance()

class GUIManager:
    '''Enhanced GUI manager for component management with both PyQt6 and TK support'''
    
    # Singleton instance
    _instance = None
    _instances = {}
    
    @classmethod
    def get_instance(cls, instance_id=None, **kwargs):
        """Get a GUIManager instance
        
        Args:
            instance_id: ID of the instance to get
        
        Returns:
            GUIManager: Instance with the given ID
        """
        with cls._lock:
            if instance_id is None:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
                return cls._instance
            else:
                if instance_id not in cls._instances:
                    cls._instances[instance_id] = cls(instance_id=instance_id, **kwargs)
                return cls._instances[instance_id]
    
    _lock = threading.Lock()
    
    def __init__(self, event_bus=None, config=None, root_window=None, instance_id=None, use_qt=True):
        # Initialize core attributes
        self.components = {}  # Ensure components attribute is always present
        self.is_initialized = False
        self.loading_screen_visible = False
        self.main_window_visible = False
        self.event_bus = event_bus
        self.config = config or {}
        # Always create a root window if not provided
        if root_window is None:
            self.root = tk.Tk()
            self.has_gui = True
            self.logger = logging.getLogger("KingdomAI.GUIManager")
            self.logger.info("GUIManager initialized with root window: Yes (created)")
        else:
            self.root = root_window
            self.has_gui = True
            self.logger = logging.getLogger("KingdomAI.GUIManager")
            self.logger.info("GUIManager initialized with root window: Yes (provided)")
        
    def _handle_trading_status(self, event_data):
        """Handle trading status updates from the trading system
        
        Args:
            event_data: Trading status event data
        """
        self.logger.info(f"Received trading status update: {event_data}")
        # Update trading status display if main window is visible
        if self.main_window_visible and hasattr(self, 'main_window'):
            if hasattr(self.main_window, 'update_trading_status'):
                self.main_window.update_trading_status(event_data)
            else:
                self.logger.warning("Main window doesn't have update_trading_status method")
        self.logger.info("GUIManager created")
    
    async def initialize(self) -> bool:
        """Initialize the GUI manager and all GUI subcomponents."""
        try:
            self.logger.info("Initializing GUI Manager...")
            # Robust event subscription
            if self.event_bus:
                try:
                    subscribe = getattr(self.event_bus, 'subscribe_sync', None)
                    if not callable(subscribe):
                        subscribe = getattr(self.event_bus, 'subscribe', None)
                    if callable(subscribe):
                        subscribe('trading_status', self._handle_trading_status)
                        if hasattr(self, '_handle_system_initialized'):
                            subscribe('system_initialized', self._handle_system_initialized)
                except Exception as e:
                    self.logger.error(f"Error during event subscriptions: {e}")
            # Initialize basic components (loading screen, main window, etc.)
            self._init_components()
            self.is_initialized = True
            self.logger.info("GUI Manager initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize GUI Manager: {e}")
            return False
    
    async def update_loading_progress(self, progress: int, message: str) -> None:
        """Update the loading progress display
        
        Args:
            progress: Progress percentage (0-100)
            message: Status message to display
        """
        try:
            self.logger.debug(f"Loading progress: {progress}% - {message}")
            # If we have a loading screen component, update it
            if hasattr(self, 'loading_screen') and self.loading_screen_visible:
                if hasattr(self.loading_screen, 'update_progress_sync'):
                    self.loading_screen.update_progress_sync(progress, message)
        except Exception as e:
            self.logger.error(f"Error updating loading progress synchronously: {e}")
            
    def _init_components(self):
        """Initialize basic GUI components and ensure they are attached to the root window."""
        try:
            # Add minimal console component
            from gui.console import Console
            self.console = Console()
            self.components["console"] = self.console
            if hasattr(self.console, 'initialize'):
                self.console.initialize()
            # Initialize loading screen component
            from gui.loading_screen import LoadingScreen
            self.loading_screen = LoadingScreen()
            self.components["loading_screen"] = self.loading_screen
            # Initialize main window component
            from gui.main_window import MainWindow
            self.main_window = MainWindow(event_bus=self.event_bus, config=self.config)
            self.components["main_window"] = self.main_window
            # Wire GUI tabs to backend components via TabIntegrator
            try:
                from gui.tab_integration import get_tab_integrator
                integrator = get_tab_integrator(self.event_bus)
                if integrator:
                    integrator.integrate_tabs(self.main_window)
                    self.logger.info("TabIntegrator integrated tabs in GUIManager initialization")
            except Exception as exc:
                self.logger.error(f"Tab integration failed in GUIManager: {exc}")
            self.logger.info("Initialized GUI components")
        except ImportError as e:
            self.logger.error(f"Failed to import GUI component: {e}")
        except Exception as e:
            self.logger.error(f"Error initializing GUI components: {e}")
    
    def set_components(self, components_dict):
        """Set components to be managed by the GUI Manager
        
        Args:
            components_dict: Dictionary of component instances
        
        Returns:
            bool: True if components were set successfully
        """
        try:
            self.logger.info(f"Setting {len(components_dict)} components in GUI Manager")
            # Store references to each component
            for name, component in components_dict.items():
                self.components[name] = component
                self.logger.debug(f"Added component: {name}")
                
            # Special handling for main window
            if hasattr(self, 'root') and self.root and "main_window" not in self.components:
                try:
                    # Import here to avoid circular imports
                    from gui.main_window import MainWindow
                    self.logger.info("Creating MainWindow component")
                    main_window = MainWindow(self.event_bus, root=self.root)
                    self.components["main_window"] = main_window
                    self.logger.info("MainWindow component created")
                except Exception as e:
                    self.logger.error(f"Error creating MainWindow: {e}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
            
            self.logger.info("Components set successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error setting components: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def show_loading_screen(self, message="Loading Kingdom AI..."):
        '''Show the loading screen with optional message'''
        if not self.is_initialized or "loading_screen" not in self.components:
            logger.warning("Cannot show loading screen - GUI not fully initialized")
            return False
            
        try:
            loading_screen = self.components["loading_screen"]
            if hasattr(loading_screen, "show"):
                loading_screen.show(message)
                self.loading_screen_visible = True
                logger.info(f"Loading screen displayed: {message}")
                return True
            else:
                logger.warning("Loading screen component has no 'show' method")
                return False
        except Exception as e:
            logger.error(f"Error showing loading screen: {e}")
            return False
            
    async def show_loading_screen_async(self, message="Loading Kingdom AI..."):
        '''Async version of show_loading_screen'''
        try:
            result = self.show_loading_screen(message)
            # Use a small sleep to allow the display to update
            import asyncio
            await asyncio.sleep(0.1)
            return result
        except Exception as e:
            logger.error(f"Error in async loading screen display: {e}")
            return False
    
    def hide_loading_screen(self):
        '''Hide the loading screen'''
        if not self.loading_screen_visible or "loading_screen" not in self.components:
            return True
            
        try:
            loading_screen = self.components["loading_screen"]
            if hasattr(loading_screen, "hide"):
                loading_screen.hide()
                self.loading_screen_visible = False
                logger.info("Loading screen hidden")
                return True
            else:
                logger.warning("Loading screen component has no 'hide' method")
                return False
        except Exception as e:
            logger.error(f"Error hiding loading screen: {e}")
            return False
            
    async def hide_loading_screen_async(self):
        '''Async version of hide_loading_screen'''
        try:
            result = self.hide_loading_screen()
            # Use a small sleep to allow the display to update
            import asyncio
            await asyncio.sleep(0.1)
            return result
        except Exception as e:
            logger.error(f"Error in async loading screen hiding: {e}")
            return False
    
    def show_main_window(self):
        # Show the main application window with proper transition from loading screen
        if not self.is_initialized or "main_window" not in self.components:
            logger.warning("Cannot show main window - GUI not fully initialized")
            return False
            
        try:
            import time
            
            # Validate that all required components are available before proceeding
            logger.info("Validating all required components before GUI transition")
            required_components = [
                "main_window", "loading_screen", "console"
            ]
            
            # Optional components that should be loaded if available
            optional_components = [
                "thoth_ai", "trading_system", "mining_system", "wallet_manager", 
                "blockchain_connector", "vr_system", "voice_system"
            ]
            
            # Check for required components
            missing_required = [c for c in required_components if c not in self.components]
            if missing_required:
                logger.warning(f"Missing required components: {missing_required}")
                return False
                
            # Log optional components status
            missing_optional = [c for c in optional_components if c not in self.components]
            if missing_optional:
                logger.info(f"Some optional components not loaded yet: {missing_optional}")
                
            # First ensure all components are properly initialized
            if hasattr(self, 'components') and 'main_window' in self.components:
                main_window = self.components['main_window']
                
                # Complete any final loading screen animations
                if self.loading_screen_visible and "loading_screen" in self.components:
                    # Ensure loading reaches 100%
                    self.update_loading_progress(100, "Finalizing components...")
                    time.sleep(0.2)  # Give animation time to complete
                    self.update_loading_progress(100, "Initializing main window...")
                    time.sleep(0.5)  # Give user time to see the final message
                
                # Ensure components are initialized before showing the window
                if hasattr(main_window, 'init_component_frames'):
                    logger.info("Initializing component frames before transition")
                    main_window.init_component_frames()
            
            # Hide loading screen with proper sequence - only after all initialization is complete
            if self.loading_screen_visible:
                logger.info("Hiding loading screen with proper transition sequence")
                # Final confirmation that everything is ready
                self.update_loading_progress(100, "Kingdom AI Ready - Launching...")
                time.sleep(0.5)  # Final delay to ensure user sees 100% completion
                
                # Use the enhanced close function for smooth transition
                from gui.loading_screen import close_loading_screen
                close_loading_screen()
                self.loading_screen_visible = False
            else:
                # Just to be safe, call our own hide method
                self.hide_loading_screen()
            
            # Brief pause to allow loading screen to properly close
            time.sleep(0.3)  # Longer pause to ensure complete transition
            
            # Show main window
            main_window = self.components["main_window"]
            
            # Ensure main window is properly configured before showing
            if hasattr(main_window, '_setup_styles'):
                logger.info("Ensuring styles are properly set before showing main window")
                main_window._setup_styles()
            
            if hasattr(main_window, 'show'):
                # One final check to make sure window is ready to be shown
                if hasattr(main_window, 'update_idletasks'):
                    main_window.update_idletasks()
                    
                main_window.show()
                self.main_window_visible = True
                logger.info("Main window displayed successfully")
                # Publish event that main window is now visible
                if self.event_bus:
                    self.event_bus.publish_sync('gui.main_window.visible', {
                        'timestamp': time.time()
                    })
                return True
            elif hasattr(main_window, 'deiconify'):
                # Some Tkinter windows might use deiconify instead of show
                if hasattr(main_window, 'update_idletasks'):
                    main_window.update_idletasks()
                    
                main_window.deiconify()
                self.main_window_visible = True
                logger.info("Main window displayed via deiconify")
                # Publish event that main window is now visible
                if self.event_bus:
                    self.event_bus.publish_sync('gui.main_window.visible', {
                        'timestamp': time.time()
                    })
                return True
            else:
                logger.warning("Main window component has no 'show' or 'deiconify' method")
                return False
        except Exception as e:
            logger.error(f"Error showing main window: {e}")
            logger.error(traceback.format_exc())
            return False
            
        try:
            # Hide loading screen first
            self.hide_loading_screen()
            
            # Show main window
            main_window = self.components["main_window"]
            if hasattr(main_window, "show"):
                main_window.show()
                self.main_window_visible = True
                logger.info("Main window displayed")
                return True
            else:
                logger.warning("Main window component has no 'show' method")
                return False
        except Exception as e:
            logger.error(f"Error showing main window: {e}")
            return False
            
    async def show_main_window_async(self):
        '''Async version of show_main_window'''
        try:
            # Hide loading screen first asynchronously
            await self.hide_loading_screen_async()
            
            # Show main window
            result = self.show_main_window()
            # Use a small sleep to allow the display to update
            import asyncio
            await asyncio.sleep(0.1)
            return result
        except Exception as e:
            logger.error(f"Error in async main window display: {e}")
            return False
    
    def update_loading_progress(self, progress_value, message=None):
        '''Update the loading progress bar and message'''
        if not self.loading_screen_visible or "loading_screen" not in self.components:
            return False
            
        try:
            loading_screen = self.components["loading_screen"]
            if hasattr(loading_screen, "update_progress"):
                loading_screen.update_progress(progress_value, message)
                return True
            else:
                logger.warning("Loading screen component has no 'update_progress' method")
                return False
        except Exception as e:
            logger.error(f"Error updating loading progress: {e}")
            return False
    
    def shutdown(self):
        '''Shutdown the GUI manager'''
        logger.info("Shutting down GUIManager")
        
        for name, component in self.components.items():
            if hasattr(component, "shutdown"):
                component.shutdown()
        
        self.is_initialized = False
        logger.info("GUIManager shutdown complete")
    
    def start_gui(self):
        '''Start the GUI - main entry point called from kingdomkeys.py'''
        logger.info("Starting GUI via start_gui method")
        
        try:
            # Check if Redis Quantum Nexus connection is available - strict policy
            import redis
            try:
                redis_client = redis.Redis(
                    host='localhost', 
                    port=6380,  # Quantum Nexus specific port
                    password='QuantumNexus2025',  # Required password
                    decode_responses=True,
                    socket_timeout=5
                )
                # Test connection
                if not redis_client.ping():
                    logger.critical("Redis Quantum Nexus connection failed - aborting startup")
                    raise ConnectionError("Redis Quantum Nexus connection required but unavailable")
                logger.info("Successfully connected to Redis Quantum Nexus on port 6380")
            except ConnectionError:
                raise
            except Exception as e:
                logger.critical(f"Redis Quantum Nexus connection error: {e}")
                logger.critical("System halting due to missing Redis Quantum Nexus connection")
                raise ConnectionError("Redis Quantum Nexus connection required but unavailable") from e
                
            # If we get here, Redis connection is successful
            # Now initialize the GUI
            if not self.is_initialized:
                # If async is available, use it
                try:
                    import asyncio
                    if asyncio.get_event_loop().is_running():
                        # We're in an existing event loop
                        asyncio.create_task(self.initialize())
                        asyncio.create_task(self.show_loading_screen_async())
                    else:
                        # No running event loop, use sync methods instead
                        self.initialize()
                        # Can't use async without event loop, skip loading screen animation
                except (ImportError, RuntimeError):
                    # If asyncio not available or not in event loop, use sync methods
                    self.initialize()
                    self.show_loading_screen()
            else:
                # Already initialized, just show main window
                try:
                    import asyncio
                    if asyncio.get_event_loop().is_running():
                        asyncio.create_task(self.show_main_window_async())
                    else:
                        # No running event loop, use sync method
                        self.show_main_window()
                except (ImportError, RuntimeError):
                    self.show_main_window()
                    
            logger.info("GUI started successfully")
            return True
        except Exception as e:
            logger.critical(f"Error starting GUI: {e}")
            raise
    
    def is_ready(self):
        '''Check if GUI is ready'''
        return self.is_initialized

    async def _handle_system_initialized(self, event_data):
        """Handle system initialized event by showing main window."""
        self.logger.info(f"Received system_initialized event: {event_data}")
        
        # Hide loading screen and show main window
        self.logger.info("System initialized, showing main window")
        self.show_main_window()

# Helper function
def get_gui_manager():
    '''Get the GUIManager singleton instance'''
    return GUIManager.get_instance()