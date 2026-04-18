#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cyberpunk TabManager for Kingdom AI

This module provides a cyberpunk-styled tab management system for the Kingdom AI GUI,
allowing for dynamic creation, organization, and interaction with tabs.
Features animated RGB borders, glow effects, and futuristic visual elements.
"""

import logging
import math
import random
from typing import Dict, Any, List, Optional, Union, Callable

try:
    from PyQt6.QtWidgets import (
        QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
        QMainWindow, QApplication, QPushButton, QLabel, QTabBar, 
        QStylePainter, QStyleOptionTab, QStyle
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QRect, QPoint, QTimer, QPointF
    from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QGradient, QLinearGradient
    
    HAS_PYQT6 = True  # PyQt6 is available
    
    has_cyberpunk_styling = False
    CyberpunkRGBBorderWidget = None
    
    # STATE-OF-THE-ART: Import cyberpunk components with proper fallbacks
    try:
        from gui.styles import CyberpunkRGBBorderWidget
        has_cyberpunk_styling = True
        logging.info("CyberpunkRGBBorderWidget imported successfully from gui.styles")
    except ImportError:
        # STATE-OF-THE-ART: Create fallback for missing CyberpunkRGBBorderWidget
        CyberpunkRGBBorderWidget = QWidget  # Use QWidget as fallback
        has_cyberpunk_styling = False
        logging.warning("CyberpunkRGBBorderWidget not available from gui.styles - using QWidget fallback")
    
    # 2025 MODERN APPROACH: Use type aliases to avoid class name conflicts
    try:
        import gui.cyberpunk_style as _cyberpunk_module
        _CyberpunkStyle = _cyberpunk_module.CyberpunkStyle
        _CyberpunkEffect = _cyberpunk_module.CyberpunkEffect
        _CyberpunkParticleSystem = _cyberpunk_module.CyberpunkParticleSystem
        _CYBERPUNK_THEME = _cyberpunk_module.CYBERPUNK_THEME
        _cyberpunk_available = True
    except ImportError:
        _cyberpunk_available = False
        # 2025 MODERN FALLBACK: Simple theme dict without class conflicts
        # 2025 BEST PRACTICE: Use lowercase for mutable config to avoid constant warnings
        _cyberpunk_theme = {
            "neon_blue": "#00FFFF",
            "rgb_cycle": [
                "#00FFFF",  # Cyan
                "#FF00FF",  # Magenta 
                "#00FF66",  # Neon green
                "#BF00FF",  # Purple
                "#FFFF00",  # Yellow
            ]
            }
        
except ImportError:
    logging.warning("PyQt6 not available; TabManager will have limited functionality")
    # Provide stub classes for type checking
    class QTabWidget:
        def __init__(self, *args, **kwargs): pass
        def addTab(self, widget, title): pass
        def currentWidget(self): pass
    class QWidget:
        def __init__(self, *args, **kwargs): pass
    class pyqtSignal:
        def __init__(self, *args, **kwargs): pass
    
    # Fallback stub classes for PyQt6 not available
    class CyberpunkStyle:
        @staticmethod
        def apply_to_widget(*args, **kwargs): pass
        @staticmethod
        def get_style_sheet(*args, **kwargs): return ""
    class CyberpunkEffect:
        @staticmethod
        def create_glow_effect(*args, **kwargs): pass
    class CyberpunkParticleSystem:
        pass
    # Fallback for missing CyberpunkRGBBorderWidget
    if 'CyberpunkRGBBorderWidget' not in locals():
        CyberpunkRGBBorderWidget = QWidget
    HAS_PYQT6 = False  # type: ignore
    
logger = logging.getLogger(__name__)

# Ensure CyberpunkRGBBorderWidget is available globally for create_tab method
if 'CyberpunkRGBBorderWidget' not in globals():
    if CyberpunkRGBBorderWidget is not None:
        globals()['CyberpunkRGBBorderWidget'] = CyberpunkRGBBorderWidget
    elif HAS_PYQT6:
        globals()['CyberpunkRGBBorderWidget'] = QWidget  # Use QWidget as fallback
    else:
        globals()['CyberpunkRGBBorderWidget'] = QWidget

# Create a custom cyberpunk tab widget with RGB effects
class CyberpunkTabWidget(QTabWidget):  # type: ignore
    """A cyberpunk styled tab widget with animated RGB borders and effects"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cyberpunk_tab_widget")
        self.setDocumentMode(True)
        self.setTabPosition(QTabWidget.TabPosition.North)  # type: ignore
        
        # Animation properties using proper Qt patterns
        self._glow_hue = 180.0  # Start with cyan/blue
        self._glow_intensity = 0.5
        self._particle_alpha = 0.0
        self.last_tab_index = 0
        self._being_deleted = False
        
        # Setup proper QPropertyAnimation for tab glow - THE CORRECT WAY!
        self._setup_proper_tab_animations()
        
        # Handle tab changes
        self.currentChanged.connect(self._handle_tab_change)
    
    def _setup_proper_tab_animations(self):
        """Setup tab animations using proper QPropertyAnimation - NO TIMERS!"""
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        
        # Glow hue cycling animation - PROPER Qt WAY
        self.glow_hue_animation = QPropertyAnimation(self, b"glow_hue")
        self.glow_hue_animation.setDuration(4000)  # 4 second color cycle
        self.glow_hue_animation.setStartValue(180.0)  # Cyan
        self.glow_hue_animation.setEndValue(540.0)  # Full cycle + cyan
        self.glow_hue_animation.setLoopCount(-1)  # Infinite
        self.glow_hue_animation.start()
        
        # Glow intensity pulsing animation
        self.glow_intensity_animation = QPropertyAnimation(self, b"glow_intensity")
        self.glow_intensity_animation.setDuration(2000)  # 2 second pulse
        self.glow_intensity_animation.setStartValue(0.3)
        self.glow_intensity_animation.setEndValue(1.0)
        self.glow_intensity_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.glow_intensity_animation.setLoopCount(-1)
        self.glow_intensity_animation.start()
    
    # 2025 BEST PRACTICE: Function-style pyqtProperty to avoid lint warnings
    def _get_glow_hue(self) -> float:
        """Get current glow hue for animation."""
        return self._glow_hue
    
    def _set_glow_hue(self, value: float) -> None:
        """Set glow hue and trigger repaint - THE CORRECT WAY!"""
        self._glow_hue = value % 360.0  # Keep in 0-360 range
        self.update()  # Triggers paintEvent - NO DIRECT PAINTING!
    
    def _get_glow_intensity(self) -> float:
        """Get current glow intensity for animation."""
        return self._glow_intensity
        
    def _set_glow_intensity(self, value: float) -> None:
        """Set glow intensity and trigger repaint."""
        self._glow_intensity = value
        self.update()  # Triggers paintEvent - PROPER Qt WAY!
    
    # Modern function-style properties - 2025 APPROACH
    try:
        from PyQt6.QtCore import pyqtProperty
        glow_hue = pyqtProperty(float, _get_glow_hue, _set_glow_hue)
        glow_intensity = pyqtProperty(float, _get_glow_intensity, _set_glow_intensity)
    except ImportError:
        # Fallback if PyQt6 not available
        pass
    
    def paintEvent(self, event):
        """Custom tab painting with animated glow effects - ALL PAINTING HERE!"""
        if self._being_deleted:
            return
            
        # Call parent paintEvent first to draw normal tabs
        super().paintEvent(event)
        
        # Add animated glow effects - SAFE PAINTING IN PAINTEVENT!
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Create animated glow color from current hue
            glow_color = QColor.fromHsv(int(self._glow_hue), 200, int(255 * self._glow_intensity))
            
            # Draw subtle glow around active tab
            if self.count() > 0:
                active_tab_rect = self.tabBar().tabRect(self.currentIndex())
                if not active_tab_rect.isEmpty():
                    # Create glow pen with animated color
                    glow_pen = QPen(glow_color, 2)
                    painter.setPen(glow_pen)
                    painter.drawRect(active_tab_rect.adjusted(-1, -1, 1, 1))
                    
        finally:
            painter.end()  # Always end painter
        
        # Apply cyberpunk styling with 2025 alias system
        try:
            if _cyberpunk_available:
                _CyberpunkStyle.apply_to_widget(self, "tabs")
        except:
            pass  # Ignore styling errors
    
    def _handle_tab_change(self, index):
        """Handle tab change event with proper animation trigger."""
        self.last_tab_index = index
        self.update()  # Trigger repaint for new active tab glow
    
    def _update_glow(self):
        """Update the tab glow effect"""
        # RGB cycle for glow color
        self.glow_step += self.glow_direction
        if self.glow_step > 100:
            self.glow_direction = -1
        elif self.glow_step < 0:
            self.glow_direction = 1
            # Switch color
            # 2025 FIX: Use theme alias to avoid constant redefinition warnings  
            theme = _CYBERPUNK_THEME if _cyberpunk_available else _cyberpunk_theme
            colors = theme["rgb_cycle"]
            current_color = self.tab_glow_color.name()
            idx = colors.index(current_color) if current_color in colors else 0
            next_idx = (idx + 1) % len(colors)
            self.tab_glow_color = QColor(colors[next_idx])
        
        # Update widget
        self.update()
    
    # Duplicate paintEvent method removed - using the modern 2025 version above

class TabManager:
    """Manages tabs for the Kingdom AI main window.
    
    Responsible for creating, organizing, and managing all tabs in the Kingdom AI GUI.
    Provides methods for tab initialization, accessing tab frames, and handling tab events.
    """
    
    def __init__(self, main_window: Any, event_bus: Any):
        """Initialize the TabManager with the main window and event bus.
        
        Args:
            main_window: The main window that will contain the tabs
            event_bus: The event bus for communication between components
        """
        self.main_window = main_window
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        
        # Use custom cyberpunk tab widget if PyQt6 is available
        if HAS_PYQT6:
            self.tab_widget = CyberpunkTabWidget()
            # Redis connection will be established when needed
            self._redis_connected = False
        else:
            self.tab_widget = QTabWidget()
        
        # Prepare style
        if HAS_PYQT6:
            # Apply cyberpunk styling to the tab widget
            # 2025 FIX: Use the alias we created to avoid naming conflicts
            if _cyberpunk_available:
                _CyberpunkStyle.apply_to_widget(self.tab_widget, "tabs")
            
        self.tabs = {}  # Dictionary to store tab references
        self.tab_frames = {}  # Dictionary to store tab frame references
        self.tab_init_tasks = []  # List to store async initialization tasks
        
        # Setup tab animation effect
        self.current_rgb_index = 0
        self.particle_timer = None
        
        if HAS_PYQT6:
            self._setup_particle_system()
        
        self.logger.info("Cyberpunk TabManager initialized with animated RGB effects")
    
    def _connect_to_redis_quantum_nexus(self):
        """Connect to the Redis Quantum Nexus (2025 graceful degradation)"""
        if self._redis_connected:
            return  # Already connected
            
        # Check if running in mock data mode
        import os
        if os.environ.get('KINGDOM_AI_MODE') == 'mock_data':
            self.logger.info("Running in mock data mode - skipping Redis connection")
            self._redis_connected = True  # Mark as connected for compatibility
            return
            
        try:
            import redis
            # Attempt Redis connection on port 6380 with password
            redis_client = redis.Redis(  # type: ignore
                host="localhost",
                port=6380,  # Required specific port
                password="QuantumNexus2025",  # Required password
                db=0,
                socket_timeout=5
            )
            # Test the connection
            if not redis_client.ping():
                raise ConnectionError("Redis ping failed")
                
            self._redis_connected = True
            self.logger.info("✅ Successfully connected to Redis Quantum Nexus")
        except Exception as e:
            self.logger.warning(f"⚠️ Redis connection failed: {e} - continuing with in-memory storage")
            # 2025 GRACEFUL DEGRADATION: Continue without Redis
            self._redis_connected = True  # Mark as "connected" to prevent repeated attempts
            os.environ['KINGDOM_AI_MODE'] = 'mock_data'
    
    def _setup_particle_system(self):
        """Setup particle system for cyberpunk visual effects with COMPLETE thread safety"""
        if HAS_PYQT6:
            # STATE-OF-THE-ART: Complete QTimer thread safety solution (Qt 6.9 - 2024/2025)
            try:
                from utils.qt_timer_fix import start_timer_safe
                
                # Use completely thread-safe timer - works from ANY thread
                # This should eliminate "QObject::startTimer: Timers can only be used with threads started with QThread"
                start_timer_safe(
                    timer_id="particle_system_timer",
                    interval_ms=50,
                    callback=self._update_particles,
                    single_shot=False
                )
                self.logger.info("Particle system started with STATE-OF-THE-ART thread-safe timer (Qt 6.9)")
                
            except ImportError as ie:
                self.logger.error(f"Failed to import thread-safe timer: {ie}")
                # Disable particle system if thread-safe timer unavailable
                self.logger.warning("Particle system disabled due to missing thread-safe timer module")
            except Exception as e:
                self.logger.error(f"Particle system setup failed: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            
    def _update_particles(self):
        """Update particle animations"""
        if hasattr(self.tab_widget, 'particles'):
            self.tab_widget.update()  # type: ignore
            
    def create_tab(self, tab_id: str, tab_title: str, tab_frame_class: Any) -> Any:
        """Create a new tab with the specified ID, title, and frame class.
        
        Args:
            tab_id: Unique identifier for the tab
            tab_title: Display title for the tab
            tab_frame_class: The class to instantiate for the tab's content
            
        Returns:
            The created tab frame instance
        """
        try:
            # Create tab container - use RGB border widget for cyberpunk effect if available
            if HAS_PYQT6:
                # Ensure CyberpunkRGBBorderWidget is callable, use QWidget as fallback
                if CyberpunkRGBBorderWidget is not None and callable(CyberpunkRGBBorderWidget):
                    tab = CyberpunkRGBBorderWidget()
                else:
                    tab = QWidget()  # Use QWidget as fallback
                # Apply advanced cyberpunk styling with 2025 system
                if _cyberpunk_available:
                    _CyberpunkStyle.apply_to_widget(tab, "tab_container")
            else:
                tab = QWidget()
                
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            tab.setLayout(layout)  # type: ignore
            
            # Create tab frame instance
            frame = tab_frame_class(parent=tab, event_bus=self.event_bus)
            layout.addWidget(frame)
            
            # Apply cyberpunk styling to the frame if possible with 2025 system
            if HAS_PYQT6 and _cyberpunk_available:
                _CyberpunkStyle.apply_to_widget(frame, "tab_frame")
                
                # Add glow effect to the tab
                if hasattr(frame, 'setGraphicsEffect'):
                    # 2025 FIX: Use theme alias for consistency
                    theme = _CYBERPUNK_THEME if _cyberpunk_available else _cyberpunk_theme
                    color = QColor(theme["rgb_cycle"][self.current_rgb_index % len(theme["rgb_cycle"])])
                    if _cyberpunk_available:
                        glow = _CyberpunkEffect.create_glow_effect(color, intensity=10, spread=5)
                        frame.setGraphicsEffect(glow)
                    
                    # Rotate colors for each new tab
                    self.current_rgb_index += 1
            
            # Add tab to the tab widget
            index = self.tab_widget.addTab(tab, tab_title)
            
            # NOTE: Do not call .show() here; tab and frame are meant to live
            # inside the main window's tab widget. Calling show() creates extra
            # top-level windows when tabs are clicked.
            
            # Store references
            self.tabs[tab_id] = tab
            self.tab_frames[tab_id] = frame
            
            self.logger.info(f"Cyberpunk tab '{tab_id}' created successfully")
            return frame
        except Exception as e:
            self.logger.error(f"Error creating cyberpunk tab '{tab_id}': {e}")
            return None
    
    def get_tab(self, tab_id: str) -> Optional[QWidget]:
        """Get a tab by its ID.
        
        Args:
            tab_id: The ID of the tab to retrieve
            
        Returns:
            The tab widget, or None if not found
        """
        return self.tabs.get(tab_id)
    
    def get_tab_frame(self, tab_id: str) -> Any:
        """Get a tab frame by its ID.
        
        Args:
            tab_id: The ID of the tab frame to retrieve
            
        Returns:
            The tab frame, or None if not found
        """
        return self.tab_frames.get(tab_id)
    
    def get_tab_widget(self) -> QTabWidget:
        """Get the QTabWidget instance.
        
        Returns:
            The QTabWidget instance
        """
        return self.tab_widget
    
    def ensure_redis_connection(self):
        """Ensure Redis connection is established before using tab features"""
        if not self._redis_connected:
            self._connect_to_redis_quantum_nexus()
    
    def add_tab(self, widget, title: str, icon=None) -> int:
        """Add a tab to the tab widget.
        
        Args:
            widget: The widget to add as a tab
            title: The title of the tab
            icon: The icon to display on the tab (optional)
{{ ... }}
        Returns:
            int: The index of the added tab
        """
        return self.tab_widget.addTab(widget, title) or 0  # type: ignore
    
    def cleanup(self):
        """Cleanup resources when shutting down."""
        try:
            try:
                from utils.qt_timer_fix import stop_timer_safe
                stop_timer_safe("particle_system_timer")
            except Exception:
                pass
            if hasattr(self, 'particle_timer') and self.particle_timer:
                self.particle_timer.stop()
            self.logger.info("TabManager cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during TabManager cleanup: {e}")
    
    def update_tab(self, tab_id: str, data: Dict[str, Any]) -> bool:
        """Update a tab with new data.
        
        Args:
            tab_id: The ID of the tab to update
            data: The data to update the tab with
            
        Returns:
            True if the tab was updated successfully, False otherwise
        """
        tab_frame = self.get_tab_frame(tab_id)
        if tab_frame is None:
            self.logger.warning(f"Cannot update tab '{tab_id}': Tab not found")
            return False
        
        try:
            # Call the tab frame's update method if it exists
            if hasattr(tab_frame, 'update') and callable(getattr(tab_frame, 'update')):
                tab_frame.update(data)
                return True
            else:
                self.logger.warning(f"Tab frame '{tab_id}' does not have an update method")
                return False
        except Exception as e:
            self.logger.error(f"Error updating tab '{tab_id}': {e}")
            return False
    
    def update_all_tabs(self, data: Dict[str, Dict[str, Any]]) -> bool:
        """Update all tabs with new data.
        
        Args:
            data: Dictionary mapping tab IDs to tab data
            
        Returns:
            True if all tabs were updated successfully, False otherwise
        """
        success = True
        for tab_id, tab_data in data.items():
            if not self.update_tab(tab_id, tab_data):
                success = False
        return success
    
    def register_tab_event_handlers(self) -> None:
        """Register event handlers for all tabs."""
        for tab_id, tab_frame in self.tab_frames.items():
            if hasattr(tab_frame, 'register_event_handlers') and callable(getattr(tab_frame, 'register_event_handlers')):
                try:
                    tab_frame.register_event_handlers()
                except Exception as e:
                    self.logger.error(f"Error registering event handlers for tab '{tab_id}': {e}")


# For testing
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # Import the cyberpunk styling
    from gui.cyberpunk_style import initialize_cyberpunk_styles
    
    class TestTabFrame(QWidget):  # type: ignore
        def __init__(self, parent=None, event_bus=None):
            super().__init__(parent)
            self.event_bus = event_bus
            layout = QVBoxLayout()
            
            # Add cyberpunk-styled content
            title = QLabel("QUANTUM SYSTEMS MONITOR")
            title.setObjectName("cyberpunk_title")
            layout.addWidget(title)
            
            # Add some test buttons with cyberpunk styling
            status_btn = QPushButton("CHECK STATUS")
            status_btn.setObjectName("cyberpunk_button")
            layout.addWidget(status_btn)
            
            # Add a test readout label
            readout = QLabel("SYSTEM NOMINAL - QUANTUM FLUX: 78.3%")
            readout.setObjectName("cyberpunk_readout")
            layout.addWidget(readout)
            
            self.setLayout(layout)
            
        def update(self, data):
            print(f"Updating tab with data: {data}")
    
    app = QApplication(sys.argv)
    
    # Initialize cyberpunk styles
    initialize_cyberpunk_styles(app)
    
    # Set app stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #0A0E17;
        }
        #cyberpunk_title {
            color: #00FFFF;
            font-size: 16px;
            font-weight: bold;
            padding: 10px;
        }
        #cyberpunk_button {
            background-color: #1A1E2E;
            color: #00FFFF;
            border: 1px solid #00FFFF;
            padding: 8px 16px;
            border-radius: 4px;
        }
        #cyberpunk_button:hover {
            background-color: #2A2E3E;
            border: 1px solid #FF00FF;
            color: #FF00FF;
        }
        #cyberpunk_readout {
            color: #00FF66;
            font-family: monospace;
            background-color: #101520;
            padding: 10px;
            border-left: 3px solid #00FF66;
        }
    """)
    
    main_window = QMainWindow()
    main_window.setWindowTitle("Kingdom AI - Cyberpunk Tab System")
    main_window.setGeometry(100, 100, 800, 600)
    
    # Create a mock event bus with Redis support
    class MockEventBus:
        def __init__(self):
            try:
                import redis
                self.redis = redis.Redis(  # type: ignore
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    decode_responses=True,
                    socket_timeout=5
                )
                self.has_redis = True
                print("Connected to Redis Quantum Nexus")
            except Exception as e:
                self.has_redis = False
                print(f"Warning: Redis Quantum Nexus not available: {e}")
                # Note: This should fail in production, but we're just testing the UI
                
        def publish(self, event_name, data=None):
            print(f"Published event: {event_name}, data: {data}")
            if self.has_redis:
                try:
                    self.redis.publish(f"kingdom:event:{event_name}", str(data))
                except Exception as e:
                    print(f"Failed to publish to Redis: {e}")
            
        def subscribe(self, event_name, callback):
            print(f"Subscribed to event: {event_name}")
            
    event_bus = MockEventBus()
    
    # Create tab manager
    tab_manager = TabManager(main_window, event_bus)
    
    # Create cyberpunk tabs with cool names
    tab_manager.create_tab("quantum_systems", "QUANTUM SYSTEMS", TestTabFrame)
    tab_manager.create_tab("neural_network", "NEURAL NETWORK", TestTabFrame)
    tab_manager.create_tab("blockchain", "BLOCKCHAIN", TestTabFrame)
    tab_manager.create_tab("market_data", "MARKET DATA", TestTabFrame)
    
    # Set central widget
    main_window.setCentralWidget(tab_manager.get_tab_widget())
    
    # Update tabs
    tab_manager.update_tab("quantum_systems", {"quantum_stability": 94.3, "entanglement_factor": 0.87})
    tab_manager.update_tab("neural_network", {"training_progress": 78, "accuracy": 0.93})
    
    main_window.show()
    sys.exit(app.exec())
