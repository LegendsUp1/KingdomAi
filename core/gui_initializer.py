#!/usr/bin/env python3

"""
Kingdom AI GUI Initializer
Handles proper initialization of the GUI system with AI features
"""

import logging
import traceback
import asyncio
from typing import Dict, Any

# Import base component
from core.base_component import BaseComponent

# Try to import the GUI managers
try:
    from core.gui_manager import GUIManager
except ImportError:
    GUIManager = None

try:
    from core.ai_gui_manager import AIGUIManager
except ImportError:
    AIGUIManager = None

try:
    from core.gui_ai_integration import GUIAIIntegration
except ImportError:
    GUIAIIntegration = None


class GUIInitializer(BaseComponent):
    """
    Handles initialization of the GUI system with all required components
    
    This component ensures that the GUI system is properly initialized with:
    - Main GUI Manager for the application interface
    - AI-powered features for smart interaction
    - Proper style configuration to prevent errors
    - Loading screen and main GUI transitions
    """
    
    def __init__(self, **kwargs):
        """Initialize the GUI initializer
        
        Args:
            **kwargs: Configuration parameters
        """
        super().__init__("GUIInitializer")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Configuration
        self.config = {
            'headless': kwargs.get('headless', False),
            'ai_enabled': kwargs.get('ai_enabled', True),
            'demo_mode': kwargs.get('demo_mode', False),
            'loading_timeout': kwargs.get('loading_timeout', 30)  # seconds
        }
        
        # Component references
        self.gui_manager = None
        self.ai_manager = None
        self.integration = None
        
        # Status tracking
        self.is_initialized = False
        self.loading_complete = False
        self.initialization_error = None
        
        self.logger.info("GUI Initializer created")
    
    async def initialize(self) -> bool:
        """Initialize the GUI system asynchronously
        
        This method initializes the GUI components in the correct sequence:
        1. Core GUI Manager with safe style configuration
        2. AI-powered GUI Manager
        3. Integration between the two
        
        Returns:
            True if initialization succeeds, False otherwise
        """
        self.logger.info("Initializing GUI system...")
        
        try:
            # Subscribe to events
            await self.subscribe_to_events()
            
            # Initialize in headless mode if specified
            if self.config['headless']:
                self.logger.info("Running in headless mode - limited GUI")
                self.is_initialized = True
                self.loading_complete = True
                return True
            
            # Check for GUI components
            if GUIManager is None:
                self.logger.error("GUIManager not available - cannot initialize GUI")
                self.initialization_error = "GUIManager not available"
                return False
            
            # Initialize main GUI manager first
            self.gui_manager = GUIManager(headless=self.config['headless'], 
                                         demo_mode=self.config['demo_mode'])
            self.gui_manager.set_event_bus(self.event_bus)
            
            # Wait for GUI Manager to initialize
            if not await self.initialize_gui_manager():
                self.logger.error("Failed to initialize GUI Manager")
                self.initialization_error = "GUI Manager initialization failed"
                return False
            
            # Initialize AI features if enabled
            if self.config['ai_enabled']:
                if not await self.initialize_ai_features():
                    self.logger.warning("AI features initialization failed - continuing without AI")
            
            # Mark initialization as complete
            self.is_initialized = True
            
            # Transition from loading screen to main GUI
            result = await self.transition_to_main_gui()
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error initializing GUI system: {e}")
            self.logger.error(traceback.format_exc())
            self.initialization_error = str(e)
            return False
    
    def initialize_sync(self) -> bool:
        """Initialize the GUI system synchronously
        
        Returns:
            True if initialization succeeds, False otherwise
        """
        self.logger.info("Initializing GUI system (sync)...")
        
        try:
            # Subscribe to events
            self.subscribe_to_events_sync()
            
            # Initialize in headless mode if specified
            if self.config['headless']:
                self.logger.info("Running in headless mode - limited GUI")
                self.is_initialized = True
                self.loading_complete = True
                return True
            
            # Check for GUI components
            if GUIManager is None:
                self.logger.error("GUIManager not available - cannot initialize GUI")
                self.initialization_error = "GUIManager not available"
                return False
            
            # Initialize main GUI manager first
            self.gui_manager = GUIManager(headless=self.config['headless'], 
                                         demo_mode=self.config['demo_mode'])
            self.gui_manager.set_event_bus(self.event_bus)
            
            # Initialize GUI Manager
            if not self.gui_manager.initialize_sync():
                self.logger.error("Failed to initialize GUI Manager")
                self.initialization_error = "GUI Manager initialization failed"
                return False
            
            # Initialize AI features if enabled
            if self.config['ai_enabled']:
                if AIGUIManager is not None and GUIAIIntegration is not None:
                    self.integration = GUIAIIntegration(gui_manager=self.gui_manager)
                    self.integration.set_event_bus(self.event_bus)
                    
                    if not self.integration.initialize_sync():
                        self.logger.warning("AI integration initialization failed - continuing without AI")
                else:
                    self.logger.warning("AI components not available - continuing without AI")
            
            # Mark initialization as complete
            self.is_initialized = True
            
            # Transition from loading screen to main GUI
            if hasattr(self.gui_manager, 'show_main_gui') and callable(self.gui_manager.show_main_gui):
                self.gui_manager.show_main_gui()
                self.loading_complete = True
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error initializing GUI system: {e}")
            self.logger.error(traceback.format_exc())
            self.initialization_error = str(e)
            return False
    
    async def initialize_gui_manager(self) -> bool:
        """Initialize the main GUI manager
        
        Returns:
            True if initialization succeeds, False otherwise
        """
        self.logger.info("Initializing GUI Manager...")
        
        try:
            # Check if async initialization is available
            if hasattr(self.gui_manager, 'initialize') and asyncio.iscoroutinefunction(self.gui_manager.initialize):
                result = await self.gui_manager.initialize()
            else:
                # Fall back to sync initialization
                result = self.gui_manager.initialize_sync()
            
            if result:
                self.logger.info("GUI Manager initialized successfully")
                
                # Publish GUI status update
                if self.event_bus:
                    self.event_bus.publish("gui.update", {
                        "status": "initialized",
                        "component": "gui_manager"
                    })
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error initializing GUI Manager: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def initialize_ai_features(self) -> bool:
        """Initialize AI features for the GUI
        
        Returns:
            True if initialization succeeds, False otherwise
        """
        self.logger.info("Initializing AI features...")
        
        try:
            # Check for required components
            if AIGUIManager is None or GUIAIIntegration is None:
                self.logger.warning("AI components not available - skipping AI initialization")
                return False
            
            # Create integration layer
            self.integration = GUIAIIntegration(gui_manager=self.gui_manager)
            self.integration.set_event_bus(self.event_bus)
            
            # Initialize integration
            if hasattr(self.integration, 'initialize') and asyncio.iscoroutinefunction(self.integration.initialize):
                result = await self.integration.initialize()
            else:
                # Fall back to sync initialization
                result = self.integration.initialize_sync()
            
            if result:
                self.logger.info("AI features initialized successfully")
                
                # Publish AI status update
                if self.event_bus:
                    self.event_bus.publish("gui.update", {
                        "status": "initialized",
                        "component": "ai_features"
                    })
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error initializing AI features: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def transition_to_main_gui(self) -> bool:
        """Transition from loading screen to main GUI
        
        Returns:
            True if transition succeeds, False otherwise
        """
        self.logger.info("Transitioning to main GUI...")
        
        try:
            # Check if the method exists
            if not hasattr(self.gui_manager, 'show_main_gui') or not callable(self.gui_manager.show_main_gui):
                self.logger.warning("GUI Manager does not have show_main_gui method - cannot transition")
                self.loading_complete = True
                return True
            
            # Show main GUI
            if asyncio.iscoroutinefunction(self.gui_manager.show_main_gui):
                await self.gui_manager.show_main_gui()
            else:
                self.gui_manager.show_main_gui()
            
            self.loading_complete = True
            self.logger.info("Transitioned to main GUI successfully")
            
            # Publish GUI status update
            if self.event_bus:
                self.event_bus.publish("gui.update", {
                    "status": "main_gui_shown",
                    "component": "gui_manager"
                })
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error transitioning to main GUI: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def subscribe_to_events(self):
        """Subscribe to events asynchronously"""
        if self.event_bus:
            self.event_bus.subscribe_sync("system.status", self.handle_system_status)
            self.event_bus.subscribe_sync("system.error", self.handle_system_error)
            self.event_bus.subscribe_sync("system.shutdown", self.handle_system_shutdown)
            self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
    
    def subscribe_to_events_sync(self):
        """Subscribe to events synchronously"""
        if self.event_bus:
            self.event_bus.subscribe_sync("system.status", self.handle_system_status)
            self.event_bus.subscribe_sync("system.error", self.handle_system_error)
            self.event_bus.subscribe_sync("system.shutdown", self.handle_system_shutdown)
            self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
    
    def handle_system_status(self, event):
        """Handle system status events
        
        Args:
            event: The event object
        """
        try:
            if not event.data:
                return
                
            status = event.data.get('status')
            component = event.data.get('component')
            
            if status == 'initializing' and component == 'system':
                self.logger.info("System initializing - preparing GUI")
                # Could show initializing message in loading screen
            
            elif status == 'ready' and component == 'system':
                self.logger.info("System ready - GUI should be fully operational")
                # Could update status indicators
        except Exception as e:
            self.logger.error(f"Error handling system status: {e}")
    
    def handle_system_error(self, event):
        """Handle system error events
        
        Args:
            event: The event object
        """
        try:
            if not event.data:
                return
                
            error = event.data.get('error')
            component = event.data.get('component')
            
            self.logger.warning(f"System error in {component}: {error}")
            
            # Display error in GUI if appropriate
            if self.gui_manager and hasattr(self.gui_manager, 'show_error'):
                self.gui_manager.show_error(component, error)
        except Exception as e:
            self.logger.error(f"Error handling system error: {e}")
    
    def handle_system_shutdown(self, event):
        """Handle system shutdown events
        
        Args:
            event: The event object
        """
        try:
            self.logger.info("System shutting down - cleaning up GUI")
            
            # Clean up AI integration
            if self.integration:
                if hasattr(self.integration, 'handle_shutdown'):
                    self.integration.handle_shutdown(event)
            
            # Clean up GUI manager
            if self.gui_manager:
                if hasattr(self.gui_manager, 'stop') and callable(self.gui_manager.stop):
                    self.gui_manager.stop()
        except Exception as e:
            self.logger.error(f"Error handling system shutdown: {e}")
    
    def handle_gui_update(self, event):
        """Handle GUI update events
        
        Args:
            event: The event object
        """
        try:
            if not event.data:
                return
                
            status = event.data.get('status')
            component = event.data.get('component')
            
            if status == 'loading_progress':
                progress = event.data.get('progress', 0)
                message = event.data.get('message', '')
                self.logger.debug(f"Loading progress: {progress}% - {message}")
            
            elif status == 'initialized' and component == 'gui_manager':
                self.logger.info("GUI Manager initialized")
            
            elif status == 'main_gui_shown':
                self.logger.info("Main GUI shown")
                self.loading_complete = True
        except Exception as e:
            self.logger.error(f"Error handling GUI update: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the GUI system
        
        Returns:
            Dictionary with status information
        """
        return {
            'initialized': self.is_initialized,
            'loading_complete': self.loading_complete,
            'error': self.initialization_error,
            'headless': self.config['headless'],
            'ai_enabled': self.config['ai_enabled'] and self.integration is not None
        }
