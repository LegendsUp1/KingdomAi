#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR Gesture Controls Widget

This module provides gesture recognition and mapping controls for the VR system.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QSlider, QGroupBox, QFormLayout, QScrollArea, QFrame,
    QSizePolicy, QToolButton, QMenu, QListWidget, QListWidgetItem,
    QAbstractItemView, QStyledItemDelegate, QStyle, QInputDialog, QLineEdit
)

logger = logging.getLogger(__name__)

class GestureMappingItem(QWidget):
    """Widget representing a single gesture mapping."""
    
    def __init__(self, gesture_id: str, action_name: str, parent=None):
        super().__init__(parent)
        self.gesture_id = gesture_id
        self.action_name = action_name
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the gesture mapping item UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Gesture icon and name
        self.gesture_icon = QLabel()
        self.gesture_icon.setFixedSize(32, 32)
        self.gesture_icon.setStyleSheet("""
            QLabel {
                border: 1px solid #444444;
                border-radius: 4px;
                background: #2A2A2A;
            }
        """)
        
        # Gesture name
        self.gesture_label = QLabel(self.gesture_id.replace("_", " ").title())
        self.gesture_label.setStyleSheet("font-weight: bold;")
        
        # Action name
        self.action_label = QLabel(self.action_name)
        
        # Map/Unmap button
        self.map_button = QPushButton("Map")
        self.map_button.setCheckable(True)
        self.map_button.setFixedWidth(80)
        
        # Add widgets to layout
        layout.addWidget(self.gesture_icon)
        layout.addWidget(self.gesture_label)
        layout.addStretch()
        layout.addWidget(self.action_label)
        layout.addWidget(self.map_button)
        
        # Set up initial state
        self.update_ui()
    
    def update_ui(self):
        """Update the UI based on current state."""
        is_mapped = bool(self.action_name)
        self.map_button.setChecked(is_mapped)
        self.map_button.setText("Mapped" if is_mapped else "Map")
        
        # Update style based on mapping state
        if is_mapped:
            self.setStyleSheet("background-color: #1E3A1E; border-radius: 4px;")
        else:
            self.setStyleSheet("")

class GestureRecognitionPreview(QWidget):
    """Widget for previewing gesture recognition."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        
        # Gesture data
        self.current_gesture = None
        self.gesture_confidence = 0.0
        
        # Animation timer
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_value = 0
    
    def set_gesture(self, gesture_id: str, confidence: float):
        """Set the current gesture being recognized."""
        self.current_gesture = gesture_id
        self.gesture_confidence = confidence
        
        # Start/stop animation based on confidence
        if confidence > 0.5:
            if not self.animation_timer.isActive():
                self.animation_timer.start(50)  # 20 FPS
        else:
            self.animation_timer.stop()
            self.animation_value = 0
        
        self.update()
    
    def update_animation(self):
        """Update the animation state."""
        self.animation_value = (self.animation_value + 0.1) % 1.0
        self.update()
    
    def paintEvent(self, event):
        """Paint the gesture preview."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        
        # Draw border
        pen = QPen(QColor(60, 60, 60), 2)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        
        # Draw gesture visualization
        if self.current_gesture and self.gesture_confidence > 0.1:
            # Draw confidence ring
            center = self.rect().center()
            radius = min(self.width(), self.height()) * 0.4
            
            # Outer ring (background)
            pen = QPen(QColor(60, 60, 60), 4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)
            
            # Confidence arc
            pen = QPen(QColor(0, 200, 0), 6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            
            start_angle = 90 * 16  # 0 degrees (in 1/16th of a degree)
            span_angle = -int(self.gesture_confidence * 360 * 16)  # 0-360 degrees
            
            rect = center.x() - radius, center.y() - radius, radius * 2, radius * 2
            painter.drawArc(*rect, start_angle, span_angle)
            
            # Draw gesture icon/text
            font = QFont("Arial", 12, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.white)
            
            text = self.current_gesture.replace("_", "\n")
            text_rect = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
            
            # Draw confidence percentage
            if self.animation_timer.isActive():
                # Pulsing effect when active
                alpha = int(128 + 127 * (0.5 + 0.5 * self.animation_value))
                color = QColor(0, 255, 0, alpha)
                pen = QPen(color, 2)
                painter.setPen(pen)
                
                # Draw a pulsing circle
                pulse_radius = radius * (0.8 + 0.2 * self.animation_value)
                painter.drawEllipse(center, pulse_radius, pulse_radius)

class VRGestureControls(QWidget):
    """Widget for managing gesture recognition and mappings."""
    
    # Signals
    gesture_mapping_changed = pyqtSignal(str, str)  # gesture_id, action_name
    gesture_recording_changed = pyqtSignal(bool)    # is_recording
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_gesture_mappings()
    
    def setup_ui(self):
        """Set up the gesture controls UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # Gesture preview
        self.gesture_preview = GestureRecognitionPreview()
        
        # Recording controls
        self.record_button = QPushButton("Start Recording Gesture")
        self.record_button.setCheckable(True)
        # Use a safe icon that exists in PyQt6
        try:
            # Try SP_MediaPlay as fallback for record button
            icon_pixmap = QStyle.StandardPixmap.SP_MediaPlay
        except AttributeError:
            # Fallback to a simple dialog icon if media icons don't exist
            icon_pixmap = QStyle.StandardPixmap.SP_DialogApplyButton
        
        self.record_button.setIcon(self.style().standardIcon(icon_pixmap))
        self.record_button.toggled.connect(self.on_record_toggled)
        
        # Gesture mappings list
        self.mappings_group = QGroupBox("Gesture Mappings")
        mappings_layout = QVBoxLayout()
        
        # Filter box
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter gestures...")
        self.filter_edit.textChanged.connect(self.filter_mappings)
        
        # Mappings list
        self.mappings_list = QListWidget()
        self.mappings_list.setItemDelegate(GestureMappingDelegate())
        self.mappings_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.mappings_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # Add widgets to layout
        mappings_layout.addWidget(self.filter_edit)
        mappings_layout.addWidget(self.mappings_list)
        self.mappings_group.setLayout(mappings_layout)
        
        # Add widgets to main layout
        main_layout.addWidget(self.gesture_preview, 1)
        main_layout.addWidget(self.record_button)
        main_layout.addWidget(self.mappings_group, 2)
    
    def setup_gesture_mappings(self):
        """Set up the default gesture mappings."""
        # This would be loaded from configuration in a real app
        self.gesture_mappings = {
            "point": "Select",
            "grab": "Grab",
            "pinch": "Click",
            "thumbs_up": "Confirm",
            "thumbs_down": "Cancel",
            "open_hand": "Menu",
            "fist": "Back"
        }
        
        self.update_mappings_list()
    
    def update_mappings_list(self, filter_text: str = ""):
        """Update the mappings list with current mappings."""
        self.mappings_list.clear()
        
        # Add all available gestures
        for gesture_id, action_name in sorted(self.gesture_mappings.items()):
            if filter_text and filter_text.lower() not in gesture_id.lower():
                continue
                
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 50))  # Fixed height for each item
            
            widget = GestureMappingItem(gesture_id, action_name)
            widget.map_button.clicked.connect(
                lambda checked, g=gesture_id: self.on_map_gesture(g)
            )
            
            self.mappings_list.addItem(item)
            self.mappings_list.setItemWidget(item, widget)
    
    def filter_mappings(self, text: str):
        """Filter the mappings list based on text."""
        self.update_mappings_list(text)
    
    def on_record_toggled(self, checked: bool):
        """Handle record button toggled."""
        if checked:
            self.record_button.setText("Recording...")
            self.record_button.setStyleSheet("""
                QPushButton {
                    background-color: #7D1E1E;
                    color: white;
                    font-weight: bold;
                    border: 1px solid #FF4444;
                    padding: 5px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #8D2E2E;
                }
                QPushButton:pressed {
                    background-color: #6D0E0E;
                }
            """)
        else:
            self.record_button.setText("Start Recording Gesture")
            self.record_button.setStyleSheet("")
        
        self.gesture_recording_changed.emit(checked)
    
    def on_map_gesture(self, gesture_id: str):
        """Handle mapping a gesture to an action."""
        # In a real app, this would show a dialog to select an action
        current_action = self.gesture_mappings.get(gesture_id, "")
        
        # Show input dialog to get action name
        action_name, ok = QInputDialog.getText(
            self,
            "Map Gesture",
            f"Enter action name for {gesture_id}:",
            text=current_action
        )
        
        if ok and action_name:
            self.gesture_mappings[gesture_id] = action_name
            self.gesture_mapping_changed.emit(gesture_id, action_name)
            self.update_mappings_list(self.filter_edit.text())
    
    def update_gesture_status(self, gesture_data: Dict[str, Any]):
        """Update the gesture recognition status."""
        gesture_id = gesture_data.get('gesture_id')
        confidence = gesture_data.get('confidence', 0.0)
        
        if gesture_id and confidence > 0.1:  # Only update for confident detections
            self.gesture_preview.set_gesture(gesture_id, confidence)

class GestureMappingDelegate(QStyledItemDelegate):
    """Custom delegate for gesture mapping items."""
    
    def sizeHint(self, option, index):
        """Return the size hint for items."""
        return QSize(0, 50)  # Fixed height for all items
