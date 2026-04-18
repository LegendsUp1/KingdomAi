"""
GUI Bridge Module for Kingdom AI.

This module bridges the gap between the launcher and the GUI components,
ensuring proper initialization and communication.
"""
import os
import sys
import tkinter as tk
import logging
from typing import Optional, Dict, Any, Union

# Configure logger
logger = logging.getLogger("KingdomAI.GUIBridge")

def create_main_window(root: Optional[tk.Tk] = None, 
                      event_bus: Any = None, 
                      config: Optional[Dict[str, Any]] = None) -> Any:
    """Create and initialize the main window properly.
    
    Args:
        root: Optional Tkinter root window
        event_bus: Event bus instance for communication
        config: Configuration dictionary
        
    Returns:
        Initialized MainWindow instance
    """
    try:
        # Import MainWindow from main_window module
        from gui.main_window import MainWindow
        
        # Create root if not provided
        if root is None:
            root = tk.Tk()
            root.title("Kingdom AI")
            root.geometry("1200x800")
            root.minsize(800, 600)
            
            # Configure the root window
            root.configure(bg='#1e1e1e')
            
            # Create icon if available
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                   "assets", "icons", "kingdom_icon.png")
            if os.path.exists(icon_path):
                try:
                    icon = tk.PhotoImage(file=icon_path)
                    root.iconphoto(True, icon)
                except Exception as e:
                    logger.warning(f"Could not load icon: {e}")
        
        # Initialize the MainWindow with proper parameters
        logger.info("Creating MainWindow with proper parameters")
        main_window = MainWindow(root=root, event_bus=event_bus, config=config)
        
        # Connect MainWindow to event bus if it's provided
        if event_bus is not None and hasattr(main_window, 'set_event_bus'):
            main_window.set_event_bus(event_bus)
            logger.info("MainWindow connected to event bus")
            
        # Ensure the main window notebook is properly initialized
        try:
            from gui.gui_integration import ensure_main_window_notebook
            if ensure_main_window_notebook(main_window):
                logger.info("Main window notebook properly initialized")
            else:
                logger.warning("Could not ensure main window notebook initialization")
        except Exception as e:
            logger.warning(f"Error initializing notebook: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        
        # Register main window with component manager if available
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from core.component_manager import ComponentManager
            
            if hasattr(ComponentManager, 'get_instance'):
                component_manager = ComponentManager.get_instance()
                if component_manager and hasattr(component_manager, 'register_component'):
                    component_manager.register_component('main_window', main_window)
                    logger.info("MainWindow registered with ComponentManager")
        except ImportError:
            logger.warning("ComponentManager not available, skipping registration")
        
        return main_window
    
    except ImportError as e:
        logger.error(f"Error importing MainWindow: {e}")
        logger.warning("Creating fallback SimpleMainWindow")
        
        # Fallback implementation if the real MainWindow is not available
        class SimpleMainWindow:
            def __init__(self):
                self.root = root if root else tk.Tk()
                self.root.title("Kingdom AI (Simple Mode)")
                self.root.geometry("1000x700")
                self.event_bus = event_bus
                self.config = config or {}
                self.notebook = None
                self.tabs = {}
                self._setup_ui()
                
                # Setup event bus connection
                if event_bus and hasattr(event_bus, 'subscribe'):
                    self.set_event_bus(event_bus)
            
            def _setup_ui(self):
                # Create a simple UI
                self.notebook = ttk.Notebook(self.root)
                self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                # Status bar
                self.status_frame = tk.Frame(self.root, height=25)
                self.status_frame.pack(fill=tk.X, side=tk.BOTTOM)
                self.status_label = tk.Label(self.status_frame, text="Kingdom AI Ready", anchor=tk.W)
                self.status_label.pack(side=tk.LEFT, padx=10)
            
            def set_event_bus(self, event_bus):
                self.event_bus = event_bus
                if hasattr(event_bus, 'subscribe'):
                    event_bus.subscribe('system.status', self._handle_system_status)
                    logger.info("SimpleMainWindow connected to event bus")
            
            def _handle_system_status(self, data):
                status = data.get('status', 'Unknown') if isinstance(data, dict) else str(data)
                self.status_label.config(text=f"Status: {status}")
            
            def add_tab(self, tab_name, tab_frame):
                self.notebook.add(tab_frame, text=tab_name)
                self.tabs[tab_name] = tab_frame
                return tab_frame
            
            def run(self):
                self.root.mainloop()
        
        # Create a SimpleMainWindow instance
        return SimpleMainWindow()
    
    except Exception as e:
        logger.error(f"Unexpected error creating main window: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
