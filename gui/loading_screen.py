#!/usr/bin/env python3
"""
Kingdom AI Loading Screen - Real-Time Progress Display

Shows ACTUAL component loading progress with real timing.
Does NOT use fake timers - updates come from LoadingOrchestrator.
"""
import sys
import os
import time
import logging
from typing import List, Optional, Dict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComponentStatusWidget(QFrame):
    """Widget showing status of a single loading component."""
    
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.start_time = 0.0
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame { 
                background-color: #2a2a2a; 
                border-radius: 5px; 
                padding: 5px;
                margin: 2px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.status_icon = QLabel("⏳")
        self.status_icon.setFixedWidth(25)
        layout.addWidget(self.status_icon)
        
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        layout.addWidget(self.name_label, stretch=1)
        
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.time_label.setFixedWidth(60)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.time_label)
        
    def set_loading(self):
        self.status_icon.setText("⏳")
        self.name_label.setStyleSheet("color: #00ffff; font-size: 12px; font-weight: bold;")
        self.start_time = time.time()
        
    def set_completed(self, duration: float = 0):
        self.status_icon.setText("✅")
        self.name_label.setStyleSheet("color: #00ff00; font-size: 12px;")
        if duration > 0:
            if duration < 1:
                self.time_label.setText(f"{duration*1000:.0f}ms")
            else:
                self.time_label.setText(f"{duration:.1f}s")
                
    def set_failed(self, error: str = ""):
        self.status_icon.setText("❌")
        self.name_label.setStyleSheet("color: #ff4444; font-size: 12px;")
        if error:
            self.name_label.setToolTip(error)
            
    def set_skipped(self):
        self.status_icon.setText("⏭️")
        self.name_label.setStyleSheet("color: #888888; font-size: 12px;")


class StateOfTheArtLoadingScreen(QMainWindow):
    """
    Real-time loading screen that shows ACTUAL component progress.
    
    Features:
    - Shows each component as it loads
    - Displays real timing for each component
    - Overall progress bar with percentage
    - Elapsed time display
    - Only closes when ALL components are loaded
    """
    progress_updated = pyqtSignal(int, str)
    loading_completed = pyqtSignal()
    
    def __init__(self, title: str = "Kingdom AI", icon_path: Optional[str] = None, 
                 event_bus=None, width: int = 900, height: int = 650):
        super().__init__()
        self.title = title
        self.icon_path = icon_path
        self.event_bus = event_bus
        self._screen_width = width
        self._screen_height = height
        
        # Subscribe to loading progress events if event bus is available
        if self.event_bus:
            try:
                self.event_bus.subscribe('loading.progress', self._handle_loading_progress)
                logger.info("✅ Loading screen subscribed to loading.progress events")
            except Exception as e:
                logger.warning(f"Could not subscribe to loading.progress: {e}")
                
        self.start_time = time.time()
        self.orchestrator = None
        self.component_widgets: Dict[str, ComponentStatusWidget] = {}
        self.setup_ui()
        self.setup_elapsed_timer()
        self.setup_eta_timer()
        
    def setup_ui(self):
        self.setWindowTitle(self.title)
        self.setFixedSize(self._screen_width, self._screen_height)
        self.setStyleSheet("background-color: #1a1a1a;")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(40, 30, 40, 30)
        
        # Title
        title_label = QLabel("Kingdom AI")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel { 
                color: #00ffff; 
                font-size: 42px; 
                font-weight: bold; 
            }
        """)
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle = QLabel("Sequential Component Loading")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888888; font-size: 14px;")
        layout.addWidget(subtitle)
        
        # Current status
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel { 
                color: #ffffff; 
                font-size: 16px; 
                padding: 10px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet("""
            QProgressBar { 
                border: 2px solid #00ffff; 
                border-radius: 10px; 
                text-align: center; 
                font-weight: bold; 
                font-size: 14px;
                color: #ffffff; 
                background-color: #2a2a2a;
                min-height: 25px;
            } 
            QProgressBar::chunk { 
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #00ffff, stop:1 #0080ff); 
                border-radius: 8px; 
                margin: 2px; 
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Elapsed time
        self.elapsed_label = QLabel("Elapsed: 0.0s")
        self.elapsed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.elapsed_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.elapsed_label)

        self.eta_label = QLabel("ETA: --")
        self.eta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.eta_label.setStyleSheet("color: #ff00ff; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.eta_label)
        
        # Components scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: 1px solid #333333; 
                border-radius: 5px;
                background-color: #1a1a1a;
            }
        """)
        
        self.components_container = QWidget()
        self.components_layout = QVBoxLayout(self.components_container)
        self.components_layout.setSpacing(3)
        self.components_layout.setContentsMargins(5, 5, 5, 5)
        self.components_layout.addStretch()
        
        scroll.setWidget(self.components_container)
        layout.addWidget(scroll, stretch=1)
        
    def setup_elapsed_timer(self):
        """Timer to update elapsed time display."""
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed)
        self.elapsed_timer.start(100)  # Update every 100ms

    def setup_eta_timer(self):
        self.eta_timer = QTimer(self)
        self.eta_timer.timeout.connect(self._update_eta)
        self.eta_timer.start(200)
        
    def _update_elapsed(self):
        elapsed = time.time() - self.start_time
        self.elapsed_label.setText(f"Elapsed: {elapsed:.1f}s")

    def _format_eta(self, seconds: float) -> str:
        try:
            total = int(round(max(0.0, seconds)))
        except Exception:
            return "--"

        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _update_eta(self):
        eta_seconds = None
        if self.orchestrator is not None and hasattr(self.orchestrator, 'get_eta_seconds'):
            try:
                eta_seconds = self.orchestrator.get_eta_seconds()
            except Exception:
                eta_seconds = None

        if eta_seconds is None:
            self.eta_label.setText("ETA: calculating...")
            return

        self.eta_label.setText(f"ETA: {self._format_eta(eta_seconds)}")

    def set_orchestrator(self, orchestrator):
        self.orchestrator = orchestrator
        self._update_eta()
        
    @pyqtSlot(int, str, str)
    def _handle_loading_progress(self, data: Dict):
        """Handle loading.progress events from event bus."""
        if isinstance(data, dict):
            percent = data.get('percent', 0)
            message = data.get('message', '')
            component = data.get('component', '')
            self.on_progress_update(percent, message, component)
    
    def on_progress_update(self, percent: int, message: str, component: str):
        """Called by LoadingOrchestrator to update progress."""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        self._update_eta()
        
        # Update or create component widget
        if component and component != "complete":
            if component not in self.component_widgets:
                widget = ComponentStatusWidget(component)
                # Insert before the stretch
                self.components_layout.insertWidget(
                    self.components_layout.count() - 1, widget
                )
                self.component_widgets[component] = widget
                
            widget = self.component_widgets[component]
            
            if "✅" in message:
                # Extract duration from message if present
                duration = 0
                if "(" in message and ")" in message:
                    try:
                        time_str = message.split("(")[1].split(")")[0]
                        if "ms" in time_str:
                            duration = float(time_str.replace("ms", "")) / 1000
                        elif "s" in time_str:
                            duration = float(time_str.replace("s", ""))
                    except:
                        pass
                widget.set_completed(duration)
            elif "❌" in message:
                widget.set_failed(message)
            elif "⚠️" in message:
                widget.set_skipped()
            else:
                widget.set_loading()
                
        self.progress_updated.emit(percent, message)
        self.update()
        
    def set_progress(self, value: int, message: str = ""):
        """Legacy method for compatibility."""
        self.on_progress_update(value, message, "")
        
    def finish_loading(self):
        """Called when all components are loaded."""
        self.elapsed_timer.stop()
        self.eta_timer.stop()
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ Kingdom AI Ready!")
        self.status_label.setStyleSheet("""
            QLabel { 
                color: #00ff00; 
                font-size: 18px; 
                font-weight: bold;
                padding: 10px;
            }
        """)
        self.loading_completed.emit()
        # Close after brief delay to show completion
        QTimer.singleShot(1500, self.close)
        
    def start_loading(self, steps=None):
        """Legacy method - now just resets the timer."""
        self.start_time = time.time()
        self._update_eta()
        if steps:
            # Pre-populate component list
            for step in steps:
                if step not in self.component_widgets:
                    widget = ComponentStatusWidget(step)
                    self.components_layout.insertWidget(
                        self.components_layout.count() - 1, widget
                    )
                    self.component_widgets[step] = widget

MetallicKingdomLoading = StateOfTheArtLoadingScreen

def main():
    app = QApplication(sys.argv)
    loading_screen = StateOfTheArtLoadingScreen()
    loading_screen.show()
    loading_screen.start_loading()
    loading_screen.loading_completed.connect(lambda: print("Loading completed!"))
    return app.exec()

def show_loading_screen():
    app = QApplication.instance()
    if not app:
        return None
    loading_screen = MetallicKingdomLoading()
    loading_screen.show()
    return loading_screen

__all__ = ['StateOfTheArtLoadingScreen', 'MetallicKingdomLoading', 'show_loading_screen', 'main']

if __name__ == "__main__":
    sys.exit(main())
