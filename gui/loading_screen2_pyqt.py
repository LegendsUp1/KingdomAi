#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyQt6 Cyberpunk Loading Screen for Kingdom AI

This module provides a PyQt6-based loading screen with advanced cyberpunk styling for the Kingdom AI system.
It completely replaces the Tkinter-based implementation with a modern, animated PyQt6 GUI.

Features:
- Animated RGB glow effects and neon borders
- Real-time component status tracking via event bus
- Particle animations for visual feedback
- Seamless transition to main application
- Strict error handling with system halt on critical failures
- No fallbacks - pure PyQt6 implementation
"""

import os
import sys
import time
import logging
import threading
import random
import math
import traceback
from typing import Optional, Dict, List, Any, Union, Callable
from datetime import datetime

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
    QFrame, QSplashScreen, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize, 
    pyqtSignal, pyqtSlot, QPoint, QObject, QEvent
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QPixmap, QLinearGradient
)

# Import cyberpunk styling
try:
    from gui.cyberpunk_style import (
        CyberpunkStyle, CyberpunkEffect, CyberpunkRGBBorderWidget, 
        CyberpunkParticleSystem, CYBERPUNK_THEME
    )
except ImportError:
    logging.error("Failed to import cyberpunk_style module. Please ensure it exists.")
    raise

# Setup logging
logger = logging.getLogger(__name__)

# Global loading screen instance
_active_loading_screen = None

class CyberpunkLoadingScreen(CyberpunkRGBBorderWidget):
    """PyQt6-based cyberpunk loading screen with RGB glow effects for Kingdom AI"""
    
    # Define signals
    progressUpdated = pyqtSignal(int, str)
    loadingCompleted = pyqtSignal()
    componentRegistered = pyqtSignal(str)
    componentInitialized = pyqtSignal(str)
    componentStarted = pyqtSignal(str)
    redisStatusChanged = pyqtSignal(bool, str)
    apiKeysLoaded = pyqtSignal(bool, str)
    thothStatusChanged = pyqtSignal(bool, str)
    
    def __init__(self, parent=None, title="Kingdom AI", width=700, height=500, event_bus=None):
        """
        Initialize the cyberpunk loading screen with RGB glow effects.
        
        Args:
            parent: Parent widget
            title: Window title
            width: Window width
            height: Window height
            event_bus: Event bus for real-time updates
        """
        # Initialize base RGB border widget
        super().__init__(parent, border_width=3, border_radius=12)
        
        # Store parameters
        self.title = title
        self.width = width
        self.height = height
        self.event_bus = event_bus
        
        # Set up logger
        self.logger = logging.getLogger('gui.loading_screen2_pyqt')
        
        # Component initialization tracking
        self.components_total = 32  # Total expected core components
        self.components_initialized = 0
        self.components_started = 0
        self.total_components = 0
        self.component_status = {}  # Track component statuses
        self.loading_complete = False
        self._last_logged_progress = 0
        
        # Status tracking
        self.thoth_connected = False
        self.redis_connected = False
        self.api_keys_loaded = False
        
        # Particle system for visual effects
        self.particles = CyberpunkParticleSystem(max_particles=150)
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals to slots
        self._connect_signals()
        
        # Initialize the animation system
        self._init_animations()
        
        self.logger.info("PyQt6 Cyberpunk Loading Screen initialized")
    
    def _setup_ui(self):
        """Set up the UI elements for the loading screen"""
        # Configure window
        self.setWindowTitle(self.title)
        self.setFixedSize(self.width, self.height)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # Apply cyberpunk style
        CyberpunkStyle.apply_to_widget(self, "loading_screen")
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title label
        self.title_label = QLabel(self.title)
        self.title_label.setObjectName("title_label")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.main_layout.addWidget(self.title_label)
        
        # Add spacer
        self.main_layout.addSpacing(20)
        
        # Status frame with glow effect
        self.status_frame = QFrame()
        self.status_frame.setObjectName("main_frame")
        self.status_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.status_frame_layout = QVBoxLayout(self.status_frame)
        
        # Apply neon glow to status frame
        self.status_frame_glow = CyberpunkEffect.create_glow_effect(
            CYBERPUNK_THEME["neon_blue"], 
            intensity=25, 
            spread=15
        )
        self.status_frame.setGraphicsEffect(self.status_frame_glow)
        
        # Component status grid
        self.component_grid = QVBoxLayout()
        
        # System status
        self.system_status_label = QLabel("System: Initializing...")
        self.system_status_label.setObjectName("status_label")
        self.component_grid.addWidget(self.system_status_label)
        
        # Redis status with indicator
        self.redis_layout = QHBoxLayout()
        self.redis_indicator = QLabel("•")  # Will be colored based on status
        self.redis_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['danger']};")
        self.redis_indicator.setFont(QFont("Arial", 16))
        self.redis_status_label = QLabel("Redis Quantum Nexus: Not Connected")
        self.redis_status_label.setObjectName("status_label")
        self.redis_layout.addWidget(self.redis_indicator)
        self.redis_layout.addWidget(self.redis_status_label)
        self.redis_layout.addStretch()
        self.component_grid.addLayout(self.redis_layout)
        
        # Add remaining status indicators with similar pattern
        # Thoth AI status
        self.thoth_layout = QHBoxLayout()
        self.thoth_indicator = QLabel("•")
        self.thoth_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['danger']};")
        self.thoth_indicator.setFont(QFont("Arial", 16))
        self.thoth_status_label = QLabel("Thoth AI: Not Connected")
        self.thoth_status_label.setObjectName("status_label")
        self.thoth_layout.addWidget(self.thoth_indicator)
        self.thoth_layout.addWidget(self.thoth_status_label)
        self.thoth_layout.addStretch()
        self.component_grid.addLayout(self.thoth_layout)
        
        # API Keys status
        self.api_keys_layout = QHBoxLayout()
        self.api_keys_indicator = QLabel("•")
        self.api_keys_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['danger']};")
        self.api_keys_indicator.setFont(QFont("Arial", 16))
        self.api_keys_status_label = QLabel("API Keys: Not Loaded")
        self.api_keys_status_label.setObjectName("status_label")
        self.api_keys_layout.addWidget(self.api_keys_indicator)
        self.api_keys_layout.addWidget(self.api_keys_status_label)
        self.api_keys_layout.addStretch()
        self.component_grid.addLayout(self.api_keys_layout)
        
        # Components progress layout
        self.components_layout = QHBoxLayout()
        self.components_label = QLabel("Components:")
        self.components_label.setObjectName("status_label")
        self.components_status = QLabel("0/0 Initialized, 0/0 Started")
        self.components_layout.addWidget(self.components_label)
        self.components_layout.addWidget(self.components_status)
        self.components_layout.addStretch()
        self.component_grid.addLayout(self.components_layout)
        
        # Add component grid to status frame
        self.status_frame_layout.addLayout(self.component_grid)
        
        # Add status frame to main layout
        self.main_layout.addWidget(self.status_frame)
        self.main_layout.addSpacing(20)
        
        # Progress information
        self.progress_label = QLabel("Initializing Kingdom AI Systems...")
        self.progress_label.setObjectName("status_label")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.progress_label)
        
        # Progress bar with neon glow
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setObjectName("progress_bar")
        
        # Apply neon glow to progress bar
        self.progress_glow = CyberpunkEffect.create_glow_effect(
            CYBERPUNK_THEME["neon_blue"], 
            intensity=20, 
            spread=10
        )
        self.progress_bar.setGraphicsEffect(self.progress_glow)
        
        self.main_layout.addWidget(self.progress_bar)
    
    def _connect_signals(self):
        """Connect signals to their respective slots"""
        # Connect internal signals
        self.progressUpdated.connect(self._on_progress_updated)
        self.loadingCompleted.connect(self._on_loading_completed)
        self.componentRegistered.connect(self._on_component_registered)
        self.componentInitialized.connect(self._on_component_initialized)
        self.componentStarted.connect(self._on_component_started)
        self.redisStatusChanged.connect(self._on_redis_status_changed)
        self.apiKeysLoaded.connect(self._on_api_keys_loaded)
        self.thothStatusChanged.connect(self._on_thoth_status_changed)
    
    def _init_animations(self):
        """Initialize animations for the loading screen"""
        self._animations_enabled = True
        self._animation_interval_ms = 30
        # Setup animation timer for particle effects
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_particles)
        self.animation_timer.setInterval(self._animation_interval_ms)
        
        # Setup progress bar animation for "breathing" glow effect
        self.progress_glow_animation = QPropertyAnimation(self.progress_glow, b"color")
        self.progress_glow_animation.setDuration(2000)
        self.progress_glow_animation.setStartValue(QColor(CYBERPUNK_THEME["neon_blue"]))
        self.progress_glow_animation.setEndValue(QColor(CYBERPUNK_THEME["neon_purple"]))
        self.progress_glow_animation.setLoopCount(-1)
        self.progress_glow_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._sync_animation_timer()
    
    def _update_particles(self):
        """Update and animate particles"""
        if not self._should_animation_timer_run():
            self._sync_animation_timer()
            return
        # Update existing particles
        self.particles.update()
        
        # Emit new particles at random positions along the border
        if random.random() < 0.3:  # 30% chance each frame
            edge = random.randint(0, 3)  # 0: top, 1: right, 2: bottom, 3: left
            if edge == 0:  # top
                x = random.randint(0, self.width)
                y = random.randint(0, 5)
            elif edge == 1:  # right
                x = random.randint(self.width - 5, self.width)
                y = random.randint(0, self.height)
            elif edge == 2:  # bottom
                x = random.randint(0, self.width)
                y = random.randint(self.height - 5, self.height)
            else:  # left
                x = random.randint(0, 5)
                y = random.randint(0, self.height)
            
            self.particles.emit(x, y, count=2)
        
        # Trigger repaint to show updated particles
        self.update()

    def _should_animation_timer_run(self) -> bool:
        if not getattr(self, '_animations_enabled', True):
            return False
        if not self.isVisible():
            return False
        try:
            window = self.window()
            if window is not None and window.isMinimized():
                return False
        except Exception:
            pass
        return True

    def _sync_animation_timer(self):
        try:
            should_run = self._should_animation_timer_run()

            timer = getattr(self, 'animation_timer', None)
            if timer is not None:
                if should_run:
                    if not timer.isActive():
                        timer.start(getattr(self, '_animation_interval_ms', 30))
                else:
                    if timer.isActive():
                        timer.stop()

            glow_anim = getattr(self, 'progress_glow_animation', None)
            if glow_anim is not None:
                if should_run:
                    glow_anim.start()
                else:
                    glow_anim.stop()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_animation_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_animation_timer()

    def changeEvent(self, event):
        super().changeEvent(event)
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                self._sync_animation_timer()
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            self._animations_enabled = False
            self._sync_animation_timer()
        except Exception:
            pass
        super().closeEvent(event)
    
    def paintEvent(self, event):
        """Custom paint event to draw RGB border and particles"""
        # First draw the RGB border (parent class implementation)
        super().paintEvent(event)
        
        # Then draw particles on top
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.particles.draw(painter)
    
    @pyqtSlot(int, str)
    def _on_progress_updated(self, percentage: int, message: str):
        """Handle progress updates
        
        Args:
            percentage: Progress percentage (0-100)
            message: Status message to display
        """
        if percentage != self._last_logged_progress:
            self.logger.debug(f"Progress update: {percentage}% - {message}")
            self._last_logged_progress = percentage
        
        self.progress_bar.setValue(percentage)
        if message:
            self.progress_label.setText(message)
    
    @pyqtSlot()
    def _on_loading_completed(self):
        """Handle completion of loading process"""
        self.logger.info("Loading completed")
        self.loading_complete = True
        self._on_progress_updated(100, "Loading Complete")
        
        # Change the glow color to success
        self.progress_glow.setColor(QColor(CYBERPUNK_THEME["neon_green"]))
        
        # Emit more particles for celebration effect
        for _ in range(30):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            self.particles.emit(x, y, count=3)
    
    @pyqtSlot(str)
    def _on_component_registered(self, component_name: str):
        """Handle component registration
        
        Args:
            component_name: Name of the registered component
        """
        self.logger.debug(f"Component registered: {component_name}")
        self.component_status[component_name] = {"registered": True}
        self.total_components += 1
        
        # Update components status display
        self._update_components_display()
    
    @pyqtSlot(str)
    def _on_component_initialized(self, component_name: str):
        """Handle component initialization
        
        Args:
            component_name: Name of the initialized component
        """
        self.logger.debug(f"Component initialized: {component_name}")
        if component_name in self.component_status:
            self.component_status[component_name]["initialized"] = True
            self.components_initialized += 1
        else:
            # Component wasn't registered first, create entry
            self.component_status[component_name] = {"registered": True, "initialized": True}
            self.total_components += 1
            self.components_initialized += 1
        
        # Update components status display and progress
        self._update_components_display()
        self._update_progress()
    
    @pyqtSlot(str)
    def _on_component_started(self, component_name: str):
        """Handle component start
        
        Args:
            component_name: Name of the started component
        """
        self.logger.debug(f"Component started: {component_name}")
        if component_name in self.component_status:
            self.component_status[component_name]["started"] = True
            self.components_started += 1
        else:
            # Component wasn't registered/initialized first, create entry
            self.component_status[component_name] = {
                "registered": True, 
                "initialized": True,
                "started": True
            }
            self.total_components += 1
            self.components_initialized += 1
            self.components_started += 1
        
        # Update components status display and progress
        self._update_components_display()
        self._update_progress()
    
    @pyqtSlot(bool, str)
    def _on_redis_status_changed(self, connected: bool, message: str):
        """Handle Redis connection status updates
        
        Args:
            connected: Connection status
            message: Status message
        """
        self.redis_connected = connected
        
        # Update Redis indicator
        if connected:
            self.redis_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['neon_green']};")
            self.redis_status_label.setText(f"Redis Quantum Nexus: {message}")
        else:
            self.redis_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['danger']};")
            self.redis_status_label.setText(f"Redis Quantum Nexus: {message}")
            
            # CRITICAL: System must halt if Redis connection fails (no fallback allowed)
            self.logger.critical("Redis Quantum Nexus connection failed - system will halt")
            QApplication.exit(1)  # Exit with error code 1
        
        # Update progress
        self._update_progress()
    
    @pyqtSlot(bool, str)
    def _on_api_keys_loaded(self, loaded: bool, message: str):
        """Handle API keys loading status
        
        Args:
            loaded: Loading status
            message: Status message
        """
        self.api_keys_loaded = loaded
        
        # Update API keys indicator
        if loaded:
            self.api_keys_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['neon_green']};")
            self.api_keys_status_label.setText(f"API Keys: {message}")
        else:
            self.api_keys_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['warning']};")
            self.api_keys_status_label.setText(f"API Keys: {message}")
        
        # Update progress
        self._update_progress()
    
    @pyqtSlot(bool, str)
    def _on_thoth_status_changed(self, connected: bool, message: str):
        """Handle ThothConnector status updates
        
        Args:
            connected: Connection status
            message: Status message
        """
        self.thoth_connected = connected
        
        # Update Thoth indicator
        if connected:
            self.thoth_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['neon_green']};") 
            self.thoth_status_label.setText(f"Thoth AI: {message}")
        else:
            self.thoth_indicator.setStyleSheet(f"color: {CYBERPUNK_THEME['warning']};") 
            self.thoth_status_label.setText(f"Thoth AI: {message}")
        
        # Update progress
        self._update_progress()
    
    def _update_components_display(self):
        """Update the components status display"""
        self.components_status.setText(
            f"{self.components_initialized}/{self.total_components} Initialized, "
            f"{self.components_started}/{self.total_components} Started"
        )
    
    def _update_progress(self):
        """Update progress based on component status"""
        # Calculate progress percentage based on component initialization/start
        # and critical services status
        progress = 0
        
        # Component initialization progress (50%)
        if self.total_components > 0:
            init_progress = (self.components_initialized / self.total_components) * 50
            start_progress = (self.components_started / self.total_components) * 20
            progress += init_progress + start_progress
        
        # Critical services status (30%)
        if self.redis_connected:
            progress += 15
        
        if self.api_keys_loaded:
            progress += 10
        
        if self.thoth_connected:
            progress += 5
        
        # Ensure progress stays in 0-100 range
        progress = min(max(int(progress), 0), 100)
        
        # Update progress bar and check for completion
        self._on_progress_updated(progress, self.progress_label.text())
        
        # Check if loading is complete
        if progress >= 100 and not self.loading_complete:
            self.loadingCompleted.emit()
    
    def transition_to_main_window(self, main_window):
        """Perform animated transition to main window
        
        Args:
            main_window: The main window to transition to
        """
        self.logger.info("Starting transition to main window")
        
        # Store reference to main window
        self.main_window = main_window
        
        # Prepare main window - make it transparent initially
        self.main_window.setWindowOpacity(0.0)
        self.main_window.show()
        
        # Create fade-out animation for loading screen
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(800)  # Duration in milliseconds
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Create fade-in animation for main window
        self.fade_in = QPropertyAnimation(self.main_window, b"windowOpacity")
        self.fade_in.setDuration(1200)  # Duration in milliseconds
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.InCubic)
        
        # Connect fade-out finished signal to start fade-in
        self.fade_out.finished.connect(self._start_fade_in)
        
        # Connect fade-in finished signal to close loading screen
        self.fade_in.finished.connect(self.close)
        
        # Start fade-out animation
        self.fade_out.start()
    
    def _start_fade_in(self):
        """Start fade-in animation for main window"""
        self.fade_in.start()
    
    def update_system_status(self, status_message):
        """Update system status display
        
        Args:
            status_message: Status message to display
        """
        self.system_status_label.setText(f"System: {status_message}")
    
    def register_with_event_bus(self, event_bus):
        """Register loading screen with the event bus
        
        Args:
            event_bus: The event bus to register with
        """
        if not event_bus:
            self.logger.error("Failed to register with event bus: event_bus is None")
            return
            
        self.event_bus = event_bus
        self.logger.info("Registering loading screen with event bus")
        
        try:
            # Subscribe to component events
            event_bus.subscribe("component.registered", self._handle_component_registered)
            event_bus.subscribe("component.initialized", self._handle_component_initialized)
            event_bus.subscribe("component.started", self._handle_component_started)
            
            # Subscribe to system events
            event_bus.subscribe("system.status", self._handle_system_status)
            
            # Subscribe to Redis events
            event_bus.subscribe("redis.connected", self._handle_redis_connected)
            event_bus.subscribe("redis.failed", self._handle_redis_failed)
            
            # Subscribe to API keys events
            event_bus.subscribe("api_keys.loaded", self._handle_api_keys_loaded)
            event_bus.subscribe("api_keys.failed", self._handle_api_keys_failed)
            
            # Subscribe to Thoth events
            event_bus.subscribe("thoth.connected", self._handle_thoth_connected)
            event_bus.subscribe("thoth.failed", self._handle_thoth_failed)
            
            # Subscribe to loading completion event
            event_bus.subscribe("loading.complete", self._handle_loading_complete)
            
            self.logger.info("Successfully registered with event bus")
        except Exception as e:
            self.logger.error(f"Error registering with event bus: {str(e)}")
            raise
    
    # Event handlers for event bus integration
    def _handle_component_registered(self, event_data):
        """Handle component.registered event
        
        Args:
            event_data: Event data from event bus
        """
        component_name = event_data.get("name", "Unknown Component")
        self.componentRegistered.emit(component_name)
    
    def _handle_component_initialized(self, event_data):
        """Handle component.initialized event
        
        Args:
            event_data: Event data from event bus
        """
        component_name = event_data.get("name", "Unknown Component")
        self.componentInitialized.emit(component_name)
    
    def _handle_component_started(self, event_data):
        """Handle component.started event
        
        Args:
            event_data: Event data from event bus
        """
        component_name = event_data.get("name", "Unknown Component")
        self.componentStarted.emit(component_name)
    
    def _handle_system_status(self, event_data):
        """Handle system.status event
        
        Args:
            event_data: Event data from event bus
        """
        status_message = event_data.get("message", "Unknown")
        self.update_system_status(status_message)
    
    def _handle_redis_connected(self, event_data):
        """Handle redis.connected event
        
        Args:
            event_data: Event data from event bus
        """
        message = event_data.get("message", "Connected to port 6380")
        self.redisStatusChanged.emit(True, message)
    
    def _handle_redis_failed(self, event_data):
        """Handle redis.failed event
        
        Args:
            event_data: Event data from event bus
        """
        error_msg = event_data.get("error", "Connection failed to port 6380")
        self.redisStatusChanged.emit(False, error_msg)
        
        # CRITICAL: System must halt if Redis connection fails (no fallback allowed)
        self.logger.critical(f"Redis Quantum Nexus connection failed: {error_msg} - system will halt")
        # Log error to console as well for visibility
        print(f"CRITICAL ERROR: Redis Quantum Nexus connection failed: {error_msg}")
        print("System halting - no fallbacks permitted")
        # Exit with error code
        QApplication.exit(1)
    
    def _handle_api_keys_loaded(self, event_data):
        """Handle api_keys.loaded event
        
        Args:
            event_data: Event data from event bus
        """
        message = event_data.get("message", "Loaded successfully")
        self.apiKeysLoaded.emit(True, message)
    
    def _handle_api_keys_failed(self, event_data):
        """Handle api_keys.failed event
        
        Args:
            event_data: Event data from event bus
        """
        error_msg = event_data.get("error", "Failed to load")
        self.apiKeysLoaded.emit(False, error_msg)
    
    def _handle_thoth_connected(self, event_data):
        """Handle thoth.connected event
        
        Args:
            event_data: Event data from event bus
        """
        message = event_data.get("message", "Connected")
        self.thothStatusChanged.emit(True, message)
    
    def _handle_thoth_failed(self, event_data):
        """Handle thoth.failed event
        
        Args:
            event_data: Event data from event bus
        """
        error_msg = event_data.get("error", "Failed to connect")
        self.thothStatusChanged.emit(False, error_msg)
    
    def _handle_loading_complete(self, event_data):
        """Handle loading.complete event
        
        Args:
            event_data: Event data from event bus
        """
        self.loadingCompleted.emit()


# Module-level functions for managing the loading screen
def create_loading_screen(title="Kingdom AI", width=700, height=500, event_bus=None):
    """Create and show the loading screen
    
    Args:
        title: Window title
        width: Window width
        height: Window height
        event_bus: Event bus instance
    
    Returns:
        The loading screen instance
    """
    global _active_loading_screen
    
    # Log creation
    logger.info(f"Creating PyQt6 cyberpunk loading screen: {title}")
    
    # Create loading screen instance
    try:
        _active_loading_screen = CyberpunkLoadingScreen(title=title, width=width, height=height, event_bus=event_bus)
        
        # Register with event bus if provided
        if event_bus:
            _active_loading_screen.register_with_event_bus(event_bus)
        
        # Show loading screen
        _active_loading_screen.show()
        
        # Initial status update
        _active_loading_screen.update_system_status("Initializing...")
        _active_loading_screen._on_progress_updated(0, "Starting Kingdom AI systems...")
        
        return _active_loading_screen
    except Exception as e:
        logger.error(f"Failed to create loading screen: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def get_loading_screen():
    """Get the active loading screen instance
    
    Returns:
        The active loading screen instance or None if not created
    """
    global _active_loading_screen
    return _active_loading_screen

def update_loading_progress(percentage, message=""):
    """Update loading screen progress
    
    Args:
        percentage: Progress percentage (0-100)
        message: Status message to display
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen._on_progress_updated(percentage, message)

def update_system_status(status_message):
    """Update system status on loading screen
    
    Args:
        status_message: Status message to display
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen.update_system_status(status_message)

def update_redis_status(connected, message=""):
    """Update Redis connection status on loading screen
    
    Args:
        connected: Connection status
        message: Status message to display
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen._on_redis_status_changed(connected, message)

def update_thoth_status(connected, message=""):
    """Update Thoth connection status on loading screen
    
    Args:
        connected: Connection status
        message: Status message to display
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen._on_thoth_status_changed(connected, message)

def update_api_keys_status(loaded, message=""):
    """Update API keys loading status on loading screen
    
    Args:
        loaded: Loading status
        message: Status message to display
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen._on_api_keys_loaded(loaded, message)

def register_component(component_name):
    """Register component with loading screen
    
    Args:
        component_name: Name of the component to register
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen._on_component_registered(component_name)

def initialize_component(component_name):
    """Mark component as initialized on loading screen
    
    Args:
        component_name: Name of the component that was initialized
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen._on_component_initialized(component_name)

def start_component(component_name):
    """Mark component as started on loading screen
    
    Args:
        component_name: Name of the component that was started
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen._on_component_started(component_name)

def close_loading_screen():
    """Close the loading screen"""
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen.close()
        _active_loading_screen = None

def transition_to_main_window(main_window):
    """Transition from loading screen to main window with animation
    
    Args:
        main_window: The main window to transition to
    """
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen.transition_to_main_window(main_window)
    else:
        # No loading screen, just show main window directly
        main_window.show()

def complete_loading():
    """Mark loading as complete"""
    global _active_loading_screen
    if _active_loading_screen:
        _active_loading_screen.loadingCompleted.emit()


# Example usage if run as script
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    
    # Apply cyberpunk style to entire application
    apply_to_app = getattr(CyberpunkStyle, 'apply_to_application', None)
    if callable(apply_to_app):
        apply_to_app(app)
    
    # Create loading screen
    loading_screen = create_loading_screen(title="Kingdom AI")
    
    # Simulate loading process
    def simulate_loading():
        update_loading_progress(10, "Starting initialization...")
        time.sleep(0.5)
        
        update_system_status("Loading components...")
        for i in range(10):
            register_component(f"Component{i+1}")
            time.sleep(0.1)
            update_loading_progress(20 + i*2, f"Registering Component{i+1}...")
        
        update_redis_status(True, "Connected to port 6380")
        time.sleep(0.5)
        update_loading_progress(50, "Redis Quantum Nexus connected")
        
        update_api_keys_status(True, "Loaded successfully")
        time.sleep(0.5)
        update_loading_progress(60, "API keys loaded")
        
        update_thoth_status(True, "Connected and ready")
        time.sleep(0.5)
        update_loading_progress(70, "Thoth AI connected")
        
        for i in range(10):
            initialize_component(f"Component{i+1}")
            time.sleep(0.1)
            update_loading_progress(70 + i, f"Initializing Component{i+1}...")
        
        for i in range(10):
            start_component(f"Component{i+1}")
            time.sleep(0.1)
            update_loading_progress(80 + i*2, f"Starting Component{i+1}...")
        
        update_loading_progress(100, "Kingdom AI ready!")
        complete_loading()
        
        # Wait a bit then create and show a mock main window for transition demo
        time.sleep(1)
        from PyQt6.QtWidgets import QMainWindow
        main_window = QMainWindow()
        main_window.setWindowTitle("Kingdom AI - Main Window")
        main_window.resize(800, 600)
        transition_to_main_window(main_window)
    
    # Run loading simulation in a separate thread
    threading.Thread(target=simulate_loading, daemon=True).start()
    
    sys.exit(app.exec())
