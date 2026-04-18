#!/usr/bin/env python3
# type: ignore  # Globally suppress type errors for the entire file
# pyright: reportGeneralTypeIssues=false
# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportIncompatibleMethodOverride=false
# pyright: reportUnknownLambdaType=false
# pyright: reportOptionalCall=false
# pyright: reportOptionalIterable=false
# pyright: reportOptionalSubscript=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportOptionalOperand=false
# pyright: reportTypedDictNotRequiredAccess=false
# pyright: reportFunctionMemberAccess=false
# pyright: reportPrivateUsage=false
# pyright: reportPrivateImportUsage=false
# pyright: reportUntypedFunctionDecorator=false
# pyright: reportUntypedClassDecorator=false
# pyright: reportUntypedBaseClass=false
# pyright: reportUntypedNamedTuple=false
# pyright: reportUnnecessaryIsInstance=false
# pyright: reportUnnecessaryCast=false
# pyright: reportUnnecessaryComparison=false
# pyright: reportImplicitStringConcatenation=false
# pyright: reportUndefinedVariable=false
# pyright: reportUnboundVariable=false
# pyright: reportInvalidStringEscapeSequence=false
# pyright: reportUnusedImport=false
# pyright: reportUnusedClass=false
# pyright: reportUnusedFunction=false
# pyright: reportUnusedVariable=false
# pyright: reportDuplicateImport=false
# pyright: reportWildcardImportFromLibrary=false
# pyright: reportAbstractUsage=false
# pyright: reportInvalidTypeVarUse=false
# pyright: reportCallInDefaultInitializer=false
# pyright: reportTypeCommentUsage=false
# pyright: reportPropertyTypeMismatch=false
# pyright: reportInvalidStubStatement=false
# pyright: reportShadowedImports=false
# pyright: reportImportCycles=false
# pyright: reportOverlappingOverload=false
# pyright: reportDeprecated=false
# pyright: reportInvalidStringEscapeSequence=false

import os
import sys
import asyncio
import inspect

import logging
import threading
import time
import traceback

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QFrame, 
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, 
    QProgressBar, QTabWidget, 
    QSplashScreen, QGroupBox)
from PyQt6.QtCore import (Qt)
from PyQt6.QtGui import (QFont, QPixmap, QColor, QPainter, QGuiApplication)
from typing import Any, Type


# Setup logger
logger = logging.getLogger(__name__)

# Add base directory to path for relative imports
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.append(base_dir)

try:
    from gui.main_window import MainWindow
    try:
        # Prefer loading_screen2 if available
        from gui.loading_screen2 import LoadingScreen
        logger.info("Using loading_screen2 for enhanced loading experience")
    except ImportError:
        # Fall back to loading_screen if loading_screen2 is not available
        from gui.loading_screen import LoadingScreen
        logger.warning("Fallback to original loading_screen")
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

# Import BaseComponent for component-related functionality
from core.base_component import BaseComponent

# Type alias for widgets - used to avoid "variable not allowed in type expression" errors
WidgetType = Any
QtMiscType = Any

# Define constants for PyQt6 alignment and other values
# These replace tkinter constants with PyQt6 equivalents
qt_align_left = Qt.AlignmentFlag.AlignLeft
qt_align_right = Qt.AlignmentFlag.AlignRight
qt_align_top = Qt.AlignmentFlag.AlignTop
qt_align_bottom = Qt.AlignmentFlag.AlignBottom
qt_align_center = Qt.AlignmentFlag.AlignCenter
qt_align_hcenter = Qt.AlignmentFlag.AlignHCenter
qt_align_vcenter = Qt.AlignmentFlag.AlignVCenter

# Style constants
qt_normal = "normal"
qt_disabled = "disabled"
qt_readonly = "readonly"

# Direction/orientation constants
qt_horizontal = Qt.Orientation.Horizontal
qt_vertical = Qt.Orientation.Vertical

# Define fill policies - similar to tkinter's fill
qt_fill_none = 0
qt_fill_x = 1  # Horizontal fill
qt_fill_y = 2  # Vertical fill
qt_fill_both = 3  # Both directions fill

# Helper functions for type checking with PyQt6
def qt_cast(obj: Any, cls: Type[Any]) -> Any:
    """Cast an object to a PyQt6 class for type checking."""
    return obj  # Just return the object as-is, avoiding cast issues

def qt_fill(fill_value: int) -> int:
    """Convert a fill value to a PyQt6 appropriate constant."""
    return fill_value

def qt_alignment(alignment_flag) -> Qt.AlignmentFlag:
    """Convert to a PyQt6 alignment flag."""
    return alignment_flag

def qt_frame_style(style) -> Any:
    """Convert to a PyQt6 frame style."""
    return style

def qt_anchor(alignment_flag) -> Qt.AlignmentFlag:
    """Convert to a PyQt6 alignment flag for anchoring."""
    return alignment_flag

def qt_margin(margin) -> int:
    """Convert a margin value to an integer for PyQt6 layouts."""
    return margin if isinstance(margin, int) else 0

class GUIManager(BaseComponent):
    _instance = None
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance of GUIManager."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self, name="GUIManager", event_bus=None, config=None, use_gui=True, root=None):
        """Initialize the GUI Manager.
        
        Args:
            name: Component name
            event_bus: Event bus instance
            config: Configuration dictionary or ConfigManager instance
            use_gui: Whether to use GUI (False for headless mode)
            root: Optional QApplication instance (if provided, will use this instead of creating a new one)
        """
        super().__init__(name=name, event_bus=event_bus, config=config)
        self.logger = logging.getLogger(__name__)
        
        # Store the use_gui flag
        self.use_gui = use_gui and QT_AVAILABLE
        
        if not self.use_gui:
            self.logger.warning("GUI not available or disabled")
        
        # Initialize QApplication if needed
        self.app = None
        if self.use_gui:
            if not QApplication.instance():
                self.app = QApplication([])
            else:
                self.app = QApplication.instance()
        
        # Store the root window (main window) reference
        self.root = root
        
        # Initialize GUI component management
        self.main_window = None
        self.loading_screen = None
        self.splash_screen = None
        self.main_window_initialized = False
        
        # Initialize progress and status tracking
        self.loading_progress = 0
        self.loading_status = "Initializing..."
        
        # Initialize task tracking
        self._subscribed_to_events = False  # Flag to track event subscription status
        self._shutdown_requested = False
        
        # Define event handlers mapping
        self.EVENT_HANDLERS = {
            "system_status": self.on_system_status,
            "component_status": self.on_component_status,
            "system_error": self.on_system_error,
            "gui_update": self.on_gui_update,
            "system_shutdown": self.on_shutdown,
            "trading_status": self._handle_trading_status,
            "loading_update": self._handle_loading_update,
        }
        
        # GUI components
        self.frames = {}
        self.windows = {}
        
        # Timer for periodic UI updates
        self.update_timer = None
        
    @property
    def is_active(self):
        """Check if the GUI is still active and not closed.
        
        Returns:
            bool: True if the GUI is active, False otherwise
        """
        if self._shutdown_requested:
            return False
            
        if hasattr(self, 'root') and self.root:
            try:
                # Check if root window exists and is not destroyed
                return self.root.winfo_exists()
            except Exception:
                return False
                
        return self.is_initialized
        
    def process_events(self):
        """Process GUI events to ensure the application remains responsive.
        
        This method should be called periodically in the main loop
        to ensure the GUI remains responsive. In PyQt6, this is typically
        handled by the event loop, but this method is kept for compatibility.
        """
        if self.use_gui and QApplication.instance():
            try:
                QApplication.instance().processEvents()
            except Exception as e:
                self.logger.error(f"Error processing GUI events: {e}")
                
    async def show_loading_screen(self, path=""):
        """Show the loading screen."""
        if not self.use_gui:
            self.logger.info("GUI disabled, not showing loading screen")
            return
            
        try:
            if QApplication.instance() is None:
                # Initialize QApplication if not already done
                self.app = QApplication(sys.argv)
            else:
                self.app = QApplication.instance()
            
            # Set the application name for proper window manager behavior
            self.app.setApplicationName("Kingdom AI")
            
            # Try to use the provided loading screen implementation
            try:
                self.loading_screen = LoadingScreen()
                self.loading_screen.show()
                self.logger.info("Custom loading screen shown")
            except Exception as e:
                self.logger.error(f"Error showing custom loading screen: {e}")
                self.logger.error(traceback.format_exc())
                # Fall back to built-in loading screen
                self._show_builtin_loading_screen()
            
            # Initialize progress values
            self.loading_progress = 0
            self.loading_status = "Initializing..."
            
            # Register for loading events if event bus available
            if self.event_bus:
                self.event_bus.subscribe("gui.loading.update", self._handle_loading_update)
                
        except Exception as e:
            self.logger.error(f"Failed to show loading screen: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _show_builtin_loading_screen(self):
        """Show a built-in loading screen if the main one can't be loaded."""
        self.logger.info("Using built-in loading screen")
        
        try:
            # Create a splash screen window
            # Load a default image or create a solid color pixmap
            splash_pixmap = QPixmap(600, 350)
            splash_pixmap.fill(QColor(44, 44, 44))  # #2c2c2c background
            
            self.splash_screen = QSplashScreen(splash_pixmap)
            
            # Create layout and widgets for splash screen
            splash_layout = QVBoxLayout()
            
            # Title label
            title_label = QLabel("Kingdom AI")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet(
                "font-size: 24pt; font-weight: bold; color: #00bfff; background: transparent;"
            )
            
            # Subtitle label
            subtitle_label = QLabel("Initializing System")
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle_label.setStyleSheet(
                "font-size: 14pt; color: white; background: transparent;"
            )
            
            # Status label
            self.status_label = QLabel("Starting up...")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_label.setStyleSheet(
                "font-size: 12pt; color: #00bfff; background: transparent;"
            )
            self.status_label.setWordWrap(True)
            
            # Progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setStyleSheet(
                "QProgressBar {border: 1px solid #00bfff; border-radius: 5px; text-align: center; background-color: #1c1c1c;}"
                "QProgressBar::chunk {background-color: #00bfff;}"
            )
            self.progress_bar.setFixedHeight(15)
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            
            # Progress text label
            self.progress_text = QLabel("0%")
            self.progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.progress_text.setStyleSheet(
                "font-size: 10pt; color: white; background: transparent;"
            )
            
            # Version label
            version_label = QLabel("v1.0.0")
            version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            version_label.setStyleSheet(
                "font-size: 8pt; color: #888888; background: transparent;"
            )
            
            # Add widgets to layout
            splash_layout.addSpacing(20)
            splash_layout.addWidget(title_label)
            splash_layout.addSpacing(20)
            splash_layout.addWidget(subtitle_label)
            splash_layout.addSpacing(30)
            splash_layout.addWidget(self.status_label)
            splash_layout.addSpacing(15)
            splash_layout.addWidget(self.progress_bar)
            splash_layout.addSpacing(5)
            splash_layout.addWidget(self.progress_text)
            splash_layout.addStretch(1)
            splash_layout.addWidget(version_label)
            splash_layout.addSpacing(20)
            
            # Create a widget to host the layout
            container = QWidget()
            container.setLayout(splash_layout)
            
            # Render layout to image
            painter = QPainter(splash_pixmap)
            container.render(painter)
            painter.end()
            
            # Update splash screen with new pixmap
            self.splash_screen.setPixmap(splash_pixmap)
            
            # Position at center of screen
            screen = QGuiApplication.primaryScreen().geometry()
            x = (screen.width() - 600) // 2
            y = (screen.height() - 350) // 2
            self.splash_screen.move(x, y)
            
            # Show splash screen
            self.splash_screen.show()
            self.app.processEvents()
            
            # Store reference
            self.loading_screen = self.splash_screen
            
            self.logger.info("Built-in loading screen initialized")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Error showing built-in loading screen: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _handle_loading_update(self, data):
        """Handle updates to the loading screen.
        
        Args:
            data: Dictionary containing status and progress information
        """
        try:
            self.logger.debug(f"Loading update received: {data}")
            
            # Extract data safely
            status = data.get("status", "")
            progress = data.get("progress", 0)
            
            # Update the loading screen if it exists and has the necessary attributes
            if hasattr(self, 'loading_status_var') and self.loading_status_var is not None:
                self.loading_status_var.set(status)
                
            if hasattr(self, 'loading_progress_var') and self.loading_progress_var is not None:
                self.loading_progress_var.set(progress)
                
            # Process PyQt6 events to update the display
            if hasattr(self, 'app') and self.app is not None:
                try:
                    self.app.processEvents()
                except Exception as e:
                    self.logger.error(f"Error updating loading screen: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error handling loading update: {e}")
            self.logger.error(traceback.format_exc())
    async def update_loading_progress(self, progress=None, status_text=None, message=None):
        """
        Update the loading screen with new progress value and status text.
        
        Args:
            progress: The progress value (0-100)
            status_text: The status text to display
            message: Alternative parameter name for status_text (for backward compatibility)
        """
        if not self.use_gui:
            return
            
        # Allow using either status_text or message parameter
        if message is not None and status_text is None:
            status_text = message
            
        try:
            # Define an inner function to update the UI
            def update_ui():
                # Update progress bar if we have one and progress is provided
                if hasattr(self, 'progress_bar') and progress is not None:
                    self.progress_bar.setValue(int(progress))
                    
                    # Also update progress text if we have that widget
                    if hasattr(self, 'progress_text'):
                        self.progress_text.setText(f"{int(progress)}%")
                        
                # Update status label if we have one and status_text is provided
                if hasattr(self, 'status_label') and status_text is not None:
                    self.status_label.setText(status_text)
                    
                # If we have a loading screen object with update_progress method
                if hasattr(self, 'loading_screen'):
                    # For custom loading screens that have their own update methods
                    if hasattr(self.loading_screen, 'update_progress') and progress is not None:
                        self.loading_screen.update_progress(progress)
                        
                    if hasattr(self.loading_screen, 'update_status') and status_text is not None:
                        self.loading_screen.update_status(status_text)
                        
                # Process events to update UI
                if QApplication.instance():
                    QApplication.instance().processEvents()
                    
            # If we're in an async context, run the UI update in the main thread
            if asyncio.get_running_loop():
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, update_ui)
            else:
                # If not in async context, update directly
                update_ui()
                
            # Store current values
            if progress is not None:
                self.loading_progress = progress
                
            if status_text is not None:
                self.loading_status = status_text
                
        except Exception as e:
            self.logger.error(f"Error updating loading progress: {e}")
            self.logger.error(traceback.format_exc())
    
    async def initialize_main_window(self):
        """Initialize and show the main window after loading is complete."""
        if not self.use_gui:
            self.logger.info("GUI disabled, skipping main window initialization")
            return False
            
        try:
            self.logger.info("Initializing main window...")
            
            # First, properly close the loading screen if it exists
            if hasattr(self, 'loading_screen') and self.loading_screen:
                try:
                    if isinstance(self.loading_screen, QSplashScreen):
                        self.loading_screen.close()
                    elif hasattr(self.loading_screen, 'close'):
                        self.loading_screen.close()
                    self.loading_screen = None
                    self.logger.info("Loading screen closed")
                except Exception as e:
                    self.logger.error(f"Error closing loading screen: {e}")
                    # Continue - we still want to try to show the main window
            
            # Create main window in the main thread to avoid threading issues with Qt
            main_window = self.create_main_window()
            if not main_window:
                self.logger.error("Failed to create main window")
                return False
            
            # Initialize components in the main window
            def init_components():
                try:
                    # First try the initialize method
                    if hasattr(self.main_window, 'initialize'):
                        self.main_window.initialize()
                    
                    # Then ensure component frames are initialized
                    if hasattr(self.main_window, 'init_component_frames'):
                        self.main_window.init_component_frames()
                        self.logger.info("Initialized main window component frames")
                    
                    # Ensure window is visible and in front
                    self.main_window.show()
                    self.main_window.activateWindow()  # Brings window to front
                    self.main_window.raise_()  # Raises window on top of stack
                    
                    # Process any pending events
                    QApplication.processEvents()
                        
                    return True
                except Exception as e:
                    self.logger.error(f"Error initializing main window components: {e}")
                    self.logger.error(traceback.format_exc())
                    return False
            
            # Configure event handlers
            def config_events():
                try:
                    # We'll use the event_bus in subscribe_to_events_sync instead of trying async
                    return True
                except Exception as e:
                    self.logger.error(f"Error configuring main window events: {e}")
                    self.logger.error(traceback.format_exc())
                    return False
            
            # Run component initialization on the main thread
            try:
                if threading.current_thread() is threading.main_thread():
                    init_success = init_components()
                else:
                    # Use run_in_executor to run the Qt operation in the main thread
                    loop = asyncio.get_running_loop()
                    init_success = await loop.run_in_executor(None, init_components)
                    
                if not init_success:
                    self.logger.error("Failed to initialize main window components")
                    return False
                    
                # Run event configuration on the main thread
                if threading.current_thread() is threading.main_thread():
                    event_success = config_events()
                else:
                    # Use run_in_executor to run the Qt operation in the main thread
                    loop = asyncio.get_running_loop()
                    event_success = await loop.run_in_executor(None, config_events)
                    
                if not event_success:
                    self.logger.error("Failed to configure main window events")
                    return False
                    
                # Call the main window's subscribe_to_events_sync method
                if hasattr(self.main_window, 'subscribe_to_events_sync') and self.event_bus:
                    try:
                        if threading.current_thread() is threading.main_thread():
                            self.main_window.subscribe_to_events_sync(self.event_bus)
                        else:
                            # Use run_in_executor to run the Qt operation in the main thread
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(
                                None, 
                                lambda: self.main_window.subscribe_to_events_sync(self.event_bus))
                    except Exception as e:
                        self.logger.error(f"Error subscribing main window to events: {e}")
                        self.logger.error(traceback.format_exc())
            except Exception as e:
                self.logger.error(f"Error during main window initialization: {e}")
                self.logger.error(traceback.format_exc())
                return False
                
            self.logger.info("Main window initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing main window: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def show_main_window_async(self):
        """Show the main window asynchronously.
        
        This method initializes and displays the main window after the loading
        screen is hidden, suitable for awaiting in an async context.
        """
        if not self.use_gui:
            self.logger.info("GUI disabled, skipping main window")
            return None
            
        try:
            # First ensure the loading screen is hidden properly
            try:
                await self.hide_loading_screen_async()
            except Exception as e:
                self.logger.error(f"Error hiding loading screen: {e}")
                self.logger.error(traceback.format_exc())
            
            # Define the function to show the main window
            async def show_window():
                try:
                    # Create the main window if it doesn't exist yet
                    if not self.main_window:
                        self.main_window = self.create_main_window()
                        if not self.main_window:
                            self.logger.error("Failed to create main window")
                            return None
                    
                    # Initialize the window components and styling
                    if hasattr(self.main_window, 'initialize_components'):
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self.main_window.initialize_components)
                        self.logger.info("Main window components initialized")
                    
                    # Apply theme and styling
                    if hasattr(self.main_window, 'apply_theme'):
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self.main_window.apply_theme)
                        self.logger.info("Theme applied to main window")
                    
                    # Show the window
                    if hasattr(self.main_window, 'show'):
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self.main_window.show)
                        self.logger.info("Main window shown")
                    elif hasattr(self.main_window, 'deiconify'):
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self.main_window.deiconify)
                        self.logger.info("Main window deiconified")
                    
                    # Publish event that the main window is ready
                    if self.event_bus:
                        await self.event_bus.publish("gui.main_window.ready", {
                            "status": "ready",
                            "timestamp": time.time()
                        })
                    
                    return self.main_window
                    
                except Exception as e:
                    self.logger.error(f"Error showing main window: {e}")
                    self.logger.error(traceback.format_exc())
                    return None
            
            # Show the window
            return await show_window()
            
        except Exception as e:
            self.logger.error(f"Error in show_main_window_async: {e}")
            self.logger.error(traceback.format_exc())
            return None
            
    def create_main_window(self):
        """Create and initialize the main window.
        
        This method creates a MainWindow instance and ensures it's visible.
        Returns the MainWindow instance or None if creation failed.
        """
        try:
            # MainWindow now inherits from QMainWindow in PyQt6
            self.main_window = MainWindow(
                event_bus=self.event_bus,
                config=self.config
            )
            
            # Make sure the main window is visible
            self.main_window.show()       # Ensure it's visible
            self.main_window.raise_()      # Bring to front
            self.main_window.activateWindow() # Force focus
            
            # Initialize all component frames if not already done
            if hasattr(self.main_window, 'init_component_frames'):
                self.main_window.init_component_frames()
                self.logger.info("Initialized main window component frames")
                
            return self.main_window
        except Exception as e:
            self.logger.error(f"Error creating main window: {e}")
            self.logger.error(traceback.format_exc())
            return None
            
    async def subscribe_to_events(self):
        """Subscribe to events using the event bus."""
        self.logger.info("Subscribing to GUI events")
        try:
            if self.event_bus:
                success_count = 0
                total_count = len(self.EVENT_HANDLERS)
                
                for event_type, handler in self.EVENT_HANDLERS.items():
                    try:
                        # Try the async version first
                        if hasattr(self.event_bus, 'subscribe_async'):
                            result = await self.event_bus.subscribe_async(event_type, handler)
                        # Then try the regular version that might return an awaitable
                        elif hasattr(self.event_bus, 'subscribe'):
                            result = self.event_bus.subscribe(event_type, handler)
                            if inspect.isawaitable(result):
                                result = await result
                            # The result is a boolean success indicator
                        else:
                            self.logger.warning(f"Event bus has no subscribe method for {event_type}")
                            result = False
                            
                        if result:
                            success_count += 1
                            self.logger.info(f"Successfully subscribed to event: {event_type}")
                        else:
                            self.logger.warning(f"Failed to subscribe to event: {event_type}")
                    except Exception as e:
                        self.logger.error(f"Error subscribing to {event_type}: {e}")
                        
                self.logger.info(f"Subscribed to {success_count}/{total_count} events")
                return success_count > 0
            else:
                self.logger.warning("No event bus available for subscription")
                return False
        except Exception as e:
            self.logger.error(f"Error subscribing to events: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
            self.logger.error(traceback.format_exc())
            return False
            
    def _create_dashboard_widgets(self):
        """Create dashboard widgets"""
        try:
            dashboard = self.frames["dashboard"]
            
            # Main layout for dashboard
            dashboard_layout = QVBoxLayout(dashboard)
            
            # Header
            header = QLabel("Kingdom AI Dashboard")
            header.setFont(QFont("Helvetica", 16, QFont.Weight.Bold))
            dashboard_layout.addWidget(header, 0, Qt.AlignmentFlag.AlignCenter)
            dashboard_layout.addSpacing(20)
            
            # System status panel
            status_group = QGroupBox("System Status")
            status_layout = QGridLayout(status_group)
            
            # Add system status indicators (using a grid layout)
            status_layout.addWidget(QLabel("Trading System:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
            trading_status = QLabel("Active")
            trading_status.setStyleSheet("color: green")
            status_layout.addWidget(trading_status, 0, 1, Qt.AlignmentFlag.AlignLeft)
            
            status_layout.addWidget(QLabel("Mining System:"), 1, 0, Qt.AlignmentFlag.AlignLeft)
            mining_status = QLabel("Idle")
            mining_status.setStyleSheet("color: orange")
            status_layout.addWidget(mining_status, 1, 1, Qt.AlignmentFlag.AlignLeft)
            
            status_layout.addWidget(QLabel("ML System:"), 2, 0, Qt.AlignmentFlag.AlignLeft)
            ml_status = QLabel("Learning")
            ml_status.setStyleSheet("color: blue")
            status_layout.addWidget(ml_status, 2, 1, Qt.AlignmentFlag.AlignLeft)
            
            # Add the status group to the main layout
            dashboard_layout.addWidget(status_group)
            
            # Actions panel
            actions_group = QGroupBox("Quick Actions")
            actions_layout = QGridLayout(actions_group)
            
            # Add buttons for quick actions
            actions_layout.addWidget(QPushButton("Update Markets"), 0, 0)
            actions_layout.addWidget(QPushButton("Check Wallet"), 0, 1)
            actions_layout.addWidget(QPushButton("Generate Code"), 0, 2)
            actions_layout.addWidget(QPushButton("Launch Miner"), 0, 3)
            
            # Add the actions group to the main layout
            dashboard_layout.addWidget(actions_group)
            
            # Add stretch to push everything to the top
            dashboard_layout.addStretch()
            
        except Exception as e:
            self.logger.error(f"Error creating dashboard widgets: {e}")
            self.logger.error(traceback.format_exc())
            
    def _create_trading_widgets(self):
        """Create trading widgets"""
        try:
            trading_frame = self.frames["trading"]
            
            # Main layout for trading frame
            trading_layout = QVBoxLayout(trading_frame)
            
            # Header
            header = QLabel("Trading System")
            header.setFont(QFont("Helvetica", 16, QFont.Weight.Bold))
            trading_layout.addWidget(header, 0, Qt.AlignmentFlag.AlignCenter)
            trading_layout.addSpacing(20)
            
            # Market selection
            market_group = QGroupBox("Market Selection")
            market_layout = QGridLayout(market_group)
            
            # Exchange selection
            market_layout.addWidget(QLabel("Exchange:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
            exchange_combo = QComboBox()
            exchange_combo.addItems(["Binance", "Coinbase", "Kraken", "Gemini"])
            market_layout.addWidget(exchange_combo, 0, 1, Qt.AlignmentFlag.AlignLeft)
            
            # Pair selection
            market_layout.addWidget(QLabel("Pair:"), 1, 0, Qt.AlignmentFlag.AlignLeft)
            pair_combo = QComboBox()
            pair_combo.addItems(["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"])
            market_layout.addWidget(pair_combo, 1, 1, Qt.AlignmentFlag.AlignLeft)
            
            # Add market group to main layout
            trading_layout.addWidget(market_group)
            
            # Strategy selection
            strategy_group = QGroupBox("Strategy")
            strategy_layout = QGridLayout(strategy_group)
            
            strategy_layout.addWidget(QLabel("Strategy:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
            strategy_combo = QComboBox()
            strategy_combo.addItems(["EMA Crossover", "RSI", "MACD", "Custom"])
            strategy_layout.addWidget(strategy_combo, 0, 1, Qt.AlignmentFlag.AlignLeft)
            
            # Add strategy group to main layout
            trading_layout.addWidget(strategy_group)
            
            # Trading actions
            actions_frame = QFrame()
            actions_layout = QHBoxLayout(actions_frame)
            
            start_button = QPushButton("Start Trading")
            stop_button = QPushButton("Stop Trading")
            performance_button = QPushButton("View Performance")
            
            actions_layout.addWidget(start_button)
            actions_layout.addWidget(stop_button)
            actions_layout.addWidget(performance_button)
            actions_layout.addStretch()
            
            trading_layout.addWidget(actions_frame)
            
            # Add stretch to push everything to the top
            trading_layout.addStretch()
            
        except Exception as e:
            self.logger.error(f"Error creating trading widgets: {e}")
            self.logger.error(traceback.format_exc())
            
    def _create_mining_widgets(self):
        """Create mining dashboard widgets"""
        try:
            mining_frame = self.frames["mining"]
            
            # Main layout for mining frame
            mining_layout = QVBoxLayout(mining_frame)
            
            # Header
            header = QLabel("Mining Dashboard")
            header.setFont(QFont("Helvetica", 16, QFont.Weight.Bold))
            mining_layout.addWidget(header, 0, Qt.AlignmentFlag.AlignCenter)
            mining_layout.addSpacing(20)
            
            # Mining status
            status_group = QGroupBox("Mining Status")
            status_layout = QGridLayout(status_group)
            
            status_layout.addWidget(QLabel("Active Miners:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
            status_layout.addWidget(QLabel("4"), 0, 1, Qt.AlignmentFlag.AlignLeft)
            
            status_layout.addWidget(QLabel("Total Hashrate:"), 1, 0, Qt.AlignmentFlag.AlignLeft)
            status_layout.addWidget(QLabel("125 MH/s"), 1, 1, Qt.AlignmentFlag.AlignLeft)
            
            status_layout.addWidget(QLabel("Mining Pool:"), 2, 0, Qt.AlignmentFlag.AlignLeft)
            status_layout.addWidget(QLabel("Ethermine"), 2, 1, Qt.AlignmentFlag.AlignLeft)
            
            # Add status group to main layout
            mining_layout.addWidget(status_group)
            
            # Mining settings
            settings_group = QGroupBox("Mining Settings")
            settings_layout = QGridLayout(settings_group)
            
            settings_layout.addWidget(QLabel("Cryptocurrency:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
            crypto_combo = QComboBox()
            crypto_combo.addItems(["ETH", "BTC", "XMR"])
            settings_layout.addWidget(crypto_combo, 0, 1, Qt.AlignmentFlag.AlignLeft)
            
            # Add settings group to main layout
            mining_layout.addWidget(settings_group)
            
            # Mining actions
            actions_frame = QFrame()
            actions_layout = QHBoxLayout(actions_frame)
            
            start_button = QPushButton("Start Mining")
            stop_button = QPushButton("Stop Mining")
            optimize_button = QPushButton("Optimize Settings")
            
            actions_layout.addWidget(start_button)
            actions_layout.addWidget(stop_button)
            actions_layout.addWidget(optimize_button)
            actions_layout.addStretch()
            
            mining_layout.addWidget(actions_frame)
            
            # Add stretch to push everything to the top
            mining_layout.addStretch()
            
        except Exception as e:
            self.logger.error(f"Error creating mining widgets: {e}")
            self.logger.error(traceback.format_exc())
            
    def _on_close(self):
        """Handle window close event"""
        self.logger.info("Main window close requested")
        self._shutdown_requested = True
        if self.root:
            self.root.destroy()

    async def on_system_status(self, data):
        """Handle system status events"""
        try:
            status = data.get("status", "")
            details = data.get("details", "")
            
            if status:
                logger.info(f"GUI processing system status: {status}")
                
                # Update status in the UI
                if hasattr(self, 'main_window') and self.main_window:
                    if hasattr(self.main_window, '_update_status_bar'):
                        self.main_window._update_status_bar(f"System: {status} - {details}")
            
        except Exception as e:
            logger.error(f"Error handling system status in GUI: {e}")
            logger.error(traceback.format_exc())
    
    async def on_component_status(self, data):
        """Handle component status updates"""
        try:
            component = data.get("component", "")
            status = data.get("status", "")
            details = data.get("details", "")
            
            if component and status:
                logger.info(f"GUI processing component status: {component} -> {status}")
                
                # Update component status in the UI
                if hasattr(self, 'main_window') and self.main_window:
                    if hasattr(self.main_window, '_handle_component_status_event'):
                        # Schedule the update on the main thread
                        if self.root:
                            self.root.after(0, lambda: 
                                self.main_window._handle_component_status_event(
                                    "component.status", 
                                    {"component": component, "status": status, "details": details}
                                )
                            )
            
        except Exception as e:
            logger.error(f"Error handling component status in GUI: {e}")
            logger.error(traceback.format_exc())
    
    async def on_system_error(self, data):
        """Handle system error events"""
        try:
            error = data.get("error", "")
            component = data.get("component", "unknown")
            
            if error:
                logger.info(f"GUI processing system error from {component}: {error[:50]}...")
                
                # Show error in the UI
                if hasattr(self, 'main_window') and self.main_window:
                    if hasattr(self.main_window, '_update_status_bar'):
                        self.main_window._update_status_bar(f"Error in {component}: {error}", is_error=True)
                    
                    if hasattr(self.main_window, '_log'):
                        # Schedule the update on the main thread
                        if self.root:
                            self.root.after(0, lambda: 
                                self.main_window._log(f"ERROR: {error}", is_error=True)
                            )
            
        except Exception as e:
            logger.error(f"Error handling system error in GUI: {e}")
            logger.error(traceback.format_exc())
    
    async def on_gui_update(self, data):
        """Handle GUI update events"""
        try:
            update_type = data.get("type", "")
            component = data.get("component", "")
            content = data.get("content", {})
            
            logger.info(f"GUI update: {update_type} for {component}")
            
            # Apply the update to the UI
            if hasattr(self, 'main_window') and self.main_window:
                if hasattr(self.main_window, '_handle_gui_update_event'):
                    # Schedule the update on the main thread
                    if self.root:
                        self.root.after(0, lambda: 
                            self.main_window._handle_gui_update_event(
                                "gui.update", 
                                {"type": update_type, "component": component, "content": content}
                            )
                        )
            
        except Exception as e:
            logger.error(f"Error handling GUI update: {e}")
            logger.error(traceback.format_exc())
    
    async def on_shutdown(self, data):
        """Handle system shutdown event"""
        try:
            logger.info("GUI Manager shutdown initiated")
            
            # Show shutdown notification in UI
            if hasattr(self, 'main_window') and self.main_window:
                if hasattr(self.main_window, '_update_status_bar'):
                    self.main_window._update_status_bar("System shutting down...")
                
                # Schedule the window close on the main thread
                if self.root:
                    self.root.after(1000, self.root.destroy)
            
            logger.info("GUI Manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during GUI Manager shutdown: {e}")
            logger.error(traceback.format_exc())

    # API Key Management Helper Methods
    def _mask_key(self, key_value):
        """Mask an API key or secret for display
        
        Args:
            key_value: The key to mask
            
        Returns:
            str: The masked key
        """
        if not key_value:
            return ""
            
        if len(key_value) <= 8:
            return "*" * len(key_value)
            
        # Show first 4 and last 4 characters, mask the rest
        return key_value[:4] + "*" * (len(key_value) - 8) + key_value[-4:]
    
    def _unmask_field(self, service, field):
        """Unmask a field when it receives focus
        
        Args:
            service: The service name
            field: Either 'key' or 'secret'
        """
        if service not in self.api_key_entries:
            return
            
        entry_data = self.api_key_entries[service]
        
        if field == 'key':
            entry = entry_data['key_entry']
            entry_var = entry_data['key_var']
        else:  # field == 'secret'
            entry = entry_data['secret_entry']
            entry_var = entry_data['secret_var']
        
        # Show actual value temporarily
        actual_value = getattr(entry, '_actual_value', "")
        entry_var.set(actual_value)
    
    def _mask_field(self, service, field):
        """Mask a field when it loses focus
        
        Args:
            service: The service name
            field: Either 'key' or 'secret'
        """
        if service not in self.api_key_entries:
            return
            
        entry_data = self.api_key_entries[service]
        
        if field == 'key':
            entry = entry_data['key_entry']
            entry_var = entry_data['key_var']
        else:  # field == 'secret'
            entry = entry_data['secret_entry']
            entry_var = entry_data['secret_var']
        
        # Check if value changed
        new_value = entry_var.get()
        old_value = getattr(entry, '_actual_value', "")
        
        if new_value != old_value:
            # Value changed, update actual value and mark as modified
            entry._actual_value = new_value
            entry_data['is_modified'] = True
            
            # Change background color to indicate modified field
            entry.config(style="Modified.TEntry")
        
        # Mask the value again
        entry_var.set(self._mask_key(new_value))
    
    def _update_api_key(self, service):
        """Update API key for a service
        
        Args:
            service: The service name
        """
        if service not in self.api_key_entries:
            return
            
        entry_data = self.api_key_entries[service]
        
        # Get actual values
        api_key = entry_data['key_entry']._actual_value
        api_secret = entry_data['secret_entry']._actual_value
        
        if not api_key or not api_secret:
            self.show_notification(
                title="API Key Error",
                message=f"Both API key and secret must be provided for {service}",
                level="error"
            )
            return
        
        # Update status message
        if hasattr(self, 'api_key_status_message'):
            self.api_key_status_message.config(text=f"Updating {service} API key...")
        
        # Send update request via event bus
        key_data = {
            "api_key": api_key,
            "api_secret": api_secret
        }
        
        asyncio.create_task(self._send_api_key_update(service, key_data))
        
        # Reset modified flag
        entry_data['is_modified'] = False
        
        # Reset styles - using PyQt6 style sheet approach
        entry_data['key_entry'].setStyleSheet("")
        entry_data['secret_entry'].setStyleSheet("")
    
    async def _send_api_key_update(self, service, key_data):
        """Send API key update event
        
        Args:
            service: The service name
            key_data: Dictionary with api_key and api_secret
        """
        if not self.event_bus:
            self.logger.error("Cannot update API key: No event bus available")
            return
            
        try:
            # Publish update event
            await self.event_bus.publish("api_key.update", {
                "service": service,
                "key_data": key_data,
                "request_id": f"gui_update_{int(time.time())}",
                "component": "GUIManager"
            })
            
            # Show a notification
            if hasattr(self, 'show_notification'):
                self.show_notification(
                    title="API Key Update",
                    message=f"API key for {service} has been updated. Testing connection...",
                    level="info"
                )
        except Exception as e:
            self.logger.error(f"Error updating API key: {e}")
            
            # Show a notification
            if hasattr(self, 'show_notification'):
                self.show_notification(
                    title="API Key Error",
                    message=f"Error updating API key for {service}: {e}",
                    level="error"
                )
    
    def _test_api_key(self, service):
        """Test API key connection for a service
        
        Args:
            service: The service name
        """
        # Update status message
        if hasattr(self, 'api_key_status_message'):
            self.api_key_status_message.config(text=f"Testing {service} API key connection...")
        
        # Send test request via event bus
        asyncio.create_task(self._send_api_key_test(service))
    
    async def _send_api_key_test(self, service):
        """Send API key test event
        
        Args:
            service: The service name
        """
        if not self.event_bus:
            self.logger.error("Cannot test API key: No event bus available")
            return
            
        try:
            # Publish test event
            await self.event_bus.publish("api_key.test", {
                "service": service,
                "request_id": f"gui_test_{int(time.time())}",
                "component": "GUIManager"
            })
        except Exception as e:
            self.logger.error(f"Error testing API key: {e}")
            
            # Show a notification
            if hasattr(self, 'show_notification'):
                self.show_notification(
                    title="API Key Test Error",
                    message=f"Error testing API key for {service}: {e}",
                    level="error"
                )
    
    def _save_all_api_keys(self):
        """Save all modified API keys"""
        modified_services = []
        
        # Find all modified entries
        for service, entry_data in self.api_key_entries.items():
            if entry_data['is_modified']:
                modified_services.append(service)
        
        if not modified_services:
            # No changes to save
            if hasattr(self, 'api_key_status_message'):
                self.api_key_status_message.config(text="No changes to save")
                
            # Show a notification
            if hasattr(self, 'show_notification'):
                self.show_notification(
                    title="No Changes",
                    message="No API key changes to save",
                    level="info"
                )
            return
        
        # Update all modified keys
        for service in modified_services:
            self._update_api_key(service)
        
        # Show a notification
        if hasattr(self, 'show_notification'):
            self.show_notification(
                title="API Keys Saved",
                message=f"Updated {len(modified_services)} API keys",
                level="success"
            )

            
    def _handle_gui_update(self, data):
            
        """Handle gui_update events."""
            
        try:
            
            self.logger.debug(f"Received gui_update event: {data}")
            
            # Process event
            
        except Exception as e:
            self.logger.error(f"Error in _handle_gui_update: {e}")

    async def debug_async(self, message):
        """Log a debug message asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.debug, message)

    async def error_async(self, message, exc_info=False):
        """Log an error message asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.error, message, exc_info)
        except Exception as e:
            # If we can't log asynchronously, try to log synchronously
            self.error(f"Error in error_async: {e}")

    def error(self, message, exc_info=False):
        """Log an error message."""
        try:
            logger.error(message, exc_info=exc_info)
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("log.error", {"message": message})
                
            # Also send to system.error event for central error handling
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("system.error", {
                    "component": self.name,
                    "message": message,
                    "traceback": traceback.format_exc() if exc_info else None
                })
        except Exception as e:
            # Last resort fallback if even error logging fails
            print(f"CRITICAL ERROR in {self.name}: {message} | Error logging failed: {e}")

    async def hide_loading_screen_async(self):
        """Hide the loading screen asynchronously."""
        try:
            # First try to use the module function directly
            try:
                # Import the module function
                from gui.loading_screen import hide_loading_screen, close_loading_screen
                
                # Run in main thread to avoid threading issues
                def close_loading():
                    try:
                        # First hide the screen
                        hide_loading_screen()
                        # Then fully close it
                        close_loading_screen()
                        return True
                    except Exception as e:
                        self.logger.error(f"Error closing loading screen: {e}")
                        self.logger.error(traceback.format_exc())
                        return False
                
                # Execute on main thread
                if threading.current_thread() is threading.main_thread():
                    success = close_loading()
                else:
                    # Use run_in_executor to run the operation in the main thread
                    loop = asyncio.get_running_loop()
                    success = await loop.run_in_executor(None, close_loading)
                    
                if success:
                    self.logger.info("Loading screen closed via module functions")
                else:
                    self.logger.warning("Failed to close loading screen via module functions")
                    
            except (ImportError, Exception) as e:
                self.logger.warning(f"Could not use module functions to close loading screen: {e}")
                
                # Fall back to object method if available
                if hasattr(self, 'loading_screen') and self.loading_screen:
                    def close_loading_object():
                        try:
                            # For QSplashScreen
                            if isinstance(self.loading_screen, QSplashScreen):
                                self.loading_screen.close()
                            # For any other PyQt6 window with close method
                            elif hasattr(self.loading_screen, 'close'):
                                self.loading_screen.close()
                            
                            self.loading_screen = None
                            return True
                        except Exception as e:
                            self.logger.error(f"Error closing loading screen object: {e}")
                            self.logger.error(traceback.format_exc())
                            return False
                    
                    # Execute on main thread
                    if threading.current_thread() is threading.main_thread():
                        close_loading_object()
                    else:
                        # Use run_in_executor to run the operation in the main thread
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, close_loading_object)
                        
                    self.logger.info("Loading screen closed via object method")
                else:
                    self.logger.warning("No loading screen object to close")
            
            # Signal that loading is complete
            if self.event_bus:
                await self.event_bus.publish("gui.loading.complete", {
                    "status": "complete",
                    "timestamp": time.time()
                })
                
            self.logger.info("Loading screen hidden and closed")
            
        except Exception as e:
            self.logger.error(f"Error hiding loading screen: {e}")
            self.logger.error(traceback.format_exc())

    def initialize_gui(self):
        """Initialize the GUI and create frames."""
        try:
            self.logger.info("Initializing GUI frames")
            
            # If the QApplication doesn't exist, create it
            if QApplication.instance() is None:
                self.app = QApplication(sys.argv)
            else:
                self.app = QApplication.instance()
            
            # Create main window if it doesn't exist
            if not hasattr(self, 'main_window') or self.main_window is None:
                self.main_window = QMainWindow()
                self.main_window.setWindowTitle("Kingdom AI")
                self.main_window.setMinimumSize(800, 600)
                self._center_window()
            
            # Create main widget and layout
            self.main_widget = QWidget()
            self.main_layout = QVBoxLayout(self.main_widget)
            
            # Add tab widget for tabs
            self.notebook = QTabWidget()
            self.main_layout.addWidget(self.notebook)
            
            # Create frames for each tab
            self.frames = {
                "dashboard": QWidget(),
                "trading": QWidget(),
                "mining": QWidget(),
                "meta_learning": QWidget(),
                "code_gen": QWidget(),
                "settings": QWidget()
            }
            
            # Add tabs to notebook
            self.notebook.addTab(self.frames["dashboard"], "Dashboard")
            self.notebook.addTab(self.frames["trading"], "Trading")
            self.notebook.addTab(self.frames["mining"], "Mining")
            self.notebook.addTab(self.frames["meta_learning"], "Meta-Learning")
            self.notebook.addTab(self.frames["code_gen"], "Code Generator")
            self.notebook.addTab(self.frames["settings"], "Settings")
            
            # Status bar at bottom
            self.status_bar = QStatusBar()
            self.main_window.setStatusBar(self.status_bar)
            self.status_label = QLabel("System Ready")
            self.status_label.setFont(QFont("Helvetica", 10))
            self.status_bar.addWidget(self.status_label)
            
            # Set the main widget as the central widget
            self.main_window.setCentralWidget(self.main_widget)
            
            # Add dashboard widgets
            self._create_dashboard_widgets()
            
            # Add trading widgets
            self._create_trading_widgets()
            
            # Add mining widgets
            self._create_mining_widgets()
            
            # Configure the main window to handle close events
            self.main_window.closeEvent = lambda event: self._on_close()
            
            self.main_window_initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing GUI: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def start_event_loop(self):
        """Start the GUI event loop.
        
        This method runs the PyQt6 event loop in an async-friendly way
        by periodically yielding control back to the event loop.
        """
        if not self.use_gui or not hasattr(self, 'app') or self.app is None:
            self.logger.warning("Cannot start GUI event loop: GUI not enabled or app not available")
            return
            
        self.logger.info("Starting GUI event loop")
        
        try:
            # Start the main loop
            while True:
                try:
                    # Process PyQt6 events
                    self.app.processEvents()
                    
                    # Give control back to asyncio loop briefly
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    self.logger.error(f"Error in GUI event loop: {e}")
                    self.logger.error(traceback.format_exc())
                    # Continue running despite errors
                    await asyncio.sleep(0.1)
                    
            self.logger.info("GUI event loop finished")
            
        except asyncio.CancelledError:
            self.logger.info("GUI event loop was cancelled")
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.close()
            
        except Exception as e:
            self.logger.error(f"Fatal error in GUI event loop: {e}")
            self.logger.error(traceback.format_exc())
            if hasattr(self, 'main_window') and self.main_window:
                try:
                    self.main_window.close()
                except:
                    pass
            raise
            
    async def _handle_trading_status(self, data):
        # Handle trading status update events
        try:
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"Trading Status: {data.get('status', 'Unknown')}")
        except Exception as e:
            self.logger.error(f"Error handling trading status: {e}")

    def start_gui(self):
        """Start the GUI system.
        
        This method shows the loading screen and initializes the main window.
        It is the main entry point for starting the GUI from kingdomkeys.py.
        """
        self.logger.info("Starting Kingdom AI GUI...")
        
        try:
            # Show loading screen
            self.show_loading_screen()
            
            # Initialize main window
            self.initialize_main_window()
            
            self.logger.info("GUI started successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error starting GUI: {e}")
            self.logger.error(traceback.format_exc())
            return False

