#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR 3D Viewer Widget
Enhanced 3D visualization system for VR environments and tracked devices.
"""

import sys
import math
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple, List

from PyQt6.QtCore import Qt, QTimer, QSize, QPoint, QRectF, QPointF
from PyQt6.QtGui import (
    QVector3D, QQuaternion, QMatrix4x4, QPainter, QColor, QPen, QBrush,
    QRadialGradient, QLinearGradient, QPainterPath, QFont, QFontMetrics
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGraphicsView,
    QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsTextItem, QGraphicsRectItem, QGraphicsPixmapItem
)
# Import OpenGL components with fallback
QOpenGLVersionProfile = None
try:
    from PyQt6.QtOpenGL import QOpenGLContext, QOpenGLWidget
except ImportError:
    # Fallback for systems without OpenGL support
    class QOpenGLContext:
        def __init__(self, *args, **kwargs): pass
        @staticmethod
        def currentContext(): return None
    class QOpenGLWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            pass

logger = logging.getLogger(__name__)

class VR3DViewer(QWidget):
    """3D visualization of VR environment and tracked devices."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Camera state
        self.camera_distance = 5.0
        self.camera_yaw = 45.0
        self.camera_pitch = 30.0
        self.camera_target = QVector3D(0, 0, 0)
        
        # Mouse interaction
        self.last_mouse_pos = None
        self.is_rotating = False
        self.is_panning = False
        self.is_zooming = False
        
        # VR tracking data
        self.devices = {}
        self.environment_bounds = {
            'min': QVector3D(-2, 0, -2),
            'max': QVector3D(2, 2, 2),
            'center': QVector3D(0, 1, 0)
        }
        
        # Visualization settings
        self.show_floor_grid = True
        self.show_room_bounds = True
        self.show_device_labels = True
        self.show_trajectories = False
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        
        # Create 3D view
        self.view = QGraphicsView()
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create scene
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        self.layout().addWidget(self.view)
        
        # Set up mouse interaction
        self.view.setMouseTracking(True)
        self.view.viewport().setMouseTracking(True)
        
        # Add floor grid
        self.draw_floor_grid()
        
        # Add room bounds
        self.draw_room_bounds()
        
        # Add coordinate axes
        self.draw_coordinate_axes()
    
    def draw_floor_grid(self):
        """Draw the floor grid."""
        if not self.show_floor_grid:
            return
            
        size = 10
        step = 0.5
        pen = QPen(QColor(100, 100, 100, 100), 1, Qt.PenStyle.DotLine)
        
        # Draw grid lines
        for i in range(-size, size + 1):
            # X lines (convert 3D to 2D by projecting onto XZ plane)
            self.scene.addLine(
                -size * step, i * step,
                size * step, i * step,
                pen
            )
            # Z lines (convert 3D to 2D by projecting onto XZ plane)
            self.scene.addLine(
                i * step, -size * step,
                i * step, size * step,
                pen
            )
    
    def draw_room_bounds(self):
        """Draw the room boundaries."""
        if not self.show_room_bounds:
            return
            
        min_pt = self.environment_bounds['min']
        max_pt = self.environment_bounds['max']
        
        pen = QPen(QColor(0, 150, 255, 150), 2)
        
        # Bottom square (project 3D to 2D by using X,Z coordinates as 2D plane)
        self.scene.addLine(min_pt.x(), min_pt.z(), max_pt.x(), min_pt.z(), pen)
        self.scene.addLine(max_pt.x(), min_pt.z(), max_pt.x(), max_pt.z(), pen)
        self.scene.addLine(max_pt.x(), max_pt.z(), min_pt.x(), max_pt.z(), pen)
        self.scene.addLine(min_pt.x(), max_pt.z(), min_pt.x(), min_pt.z(), pen)
        
        # Vertical lines (represent height as offset lines)
        self.scene.addLine(min_pt.x()-1, min_pt.z()-1, min_pt.x()+1, min_pt.z()+1, pen)
        self.scene.addLine(max_pt.x()-1, min_pt.z()-1, max_pt.x()+1, min_pt.z()+1, pen)
        self.scene.addLine(max_pt.x()-1, max_pt.z()-1, max_pt.x()+1, max_pt.z()+1, pen)
        self.scene.addLine(min_pt.x()-1, max_pt.z()-1, min_pt.x()+1, max_pt.z()+1, pen)
        
        # Top square (project 3D to 2D, offset slightly to show it's the "top")
        offset = 2
        self.scene.addLine(min_pt.x()+offset, min_pt.z()+offset, max_pt.x()+offset, min_pt.z()+offset, pen)
        self.scene.addLine(max_pt.x()+offset, min_pt.z()+offset, max_pt.x()+offset, max_pt.z()+offset, pen)
        self.scene.addLine(max_pt.x()+offset, max_pt.z()+offset, min_pt.x()+offset, max_pt.z()+offset, pen)
        self.scene.addLine(min_pt.x()+offset, max_pt.z()+offset, min_pt.x()+offset, min_pt.z()+offset, pen)
    
    def draw_coordinate_axes(self):
        """Draw coordinate axes in the corner of the view."""
        size = 0.5
        origin = QVector3D(-4, 0, -4)
        font = QFont("Arial", 8)
        
        # X axis (red) - project to 2D
        self.scene.addLine(
            origin.x(), origin.z(),
            origin.x() + size, origin.z(),
            QPen(Qt.GlobalColor.red, 2)
        )
        
        # Y axis (green) - represent as diagonal line
        self.scene.addLine(
            origin.x(), origin.z(),
            origin.x() - size/2, origin.z() - size/2,
            QPen(Qt.GlobalColor.green, 2)
        )
        
        # Z axis (blue) - project to 2D
        self.scene.addLine(
            origin.x(), origin.z(),
            origin.x(), origin.z() + size,
            QPen(Qt.GlobalColor.blue, 2)
        )
        
        # Labels
        self.scene.addSimpleText("X", font).setPos(origin.x() + size + 0.1, origin.y())
        self.scene.addSimpleText("Y", font).setPos(origin.x(), origin.y() + size + 0.1)
        self.scene.addSimpleText("Z", font).setPos(origin.x(), origin.y() - 0.2)  # Z coordinate is handled by the scene depth
    
    def update_tracking(self, data: Dict[str, Any]):
        """Update the 3D view with new tracking data.
        
        Args:
            data: Dictionary containing tracking data for VR devices
        """
        try:
            # Clear previous device visualizations
            self.clear_device_visualizations()
            
            # Process each device in the tracking data
            for device_id, device_data in data.get('devices', {}).items():
                self.update_device_visualization(device_id, device_data)
            
            # Update environment bounds if provided
            if 'environment' in data and 'bounds' in data['environment']:
                self.update_environment_bounds(data['environment']['bounds'])
            
            # Force a redraw
            self.view.viewport().update()
            
        except Exception as e:
            logger.error(f"Error updating tracking visualization: {e}")
    
    def clear_device_visualizations(self):
        """Clear all device visualizations from the scene."""
        pass  # Implement clearing of device visualizations
    
    def update_device_visualization(self, device_id: str, device_data: Dict[str, Any]):
        """Update the visualization for a single device.
        
        Args:
            device_id: Unique identifier for the device
            device_data: Dictionary containing device state and tracking data
        """
        try:
            # Extract position and rotation
            pos = device_data.get('position', {'x': 0, 'y': 0, 'z': 0})
            rot = device_data.get('rotation', {'x': 0, 'y': 0, 'z': 0, 'w': 1})
            
            # Convert to QVector3D and QQuaternion
            position = QVector3D(pos.get('x', 0), pos.get('y', 0), pos.get('z', 0))
            rotation = QQuaternion(
                rot.get('w', 1),
                rot.get('x', 0),
                rot.get('y', 0),
                rot.get('z', 0)
            )
            
            # Get device type and status
            device_type = device_data.get('type', 'unknown').lower()
            is_active = device_data.get('is_active', False)
            battery_level = device_data.get('battery_level', 1.0)
            
            # Visualize based on device type
            if 'controller' in device_type:
                self.draw_controller(position, rotation, is_active, battery_level, device_id)
            elif 'headset' in device_type:
                self.draw_headset(position, rotation, is_active, battery_level, device_id)
            elif 'tracker' in device_type:
                self.draw_tracker(position, rotation, is_active, battery_level, device_id)
            else:
                self.draw_generic_device(position, rotation, is_active, device_id)
            
        except Exception as e:
            logger.error(f"Error updating device visualization: {e}")
    
    def draw_controller(self, position: QVector3D, rotation: QQuaternion,
                       is_active: bool, battery_level: float, label: str):
        """Draw a VR controller."""
        # Controller color based on activity and battery
        if not is_active:
            color = QColor(100, 100, 100)  # Inactive
        elif battery_level < 0.2:
            color = QColor(255, 50, 50)    # Low battery
        else:
            color = QColor(50, 150, 255)   # Active
        
        # Draw controller body
        self.draw_device_shape(position, rotation, 0.1, 0.05, 0.2, color, label)
    
    def draw_headset(self, position: QVector3D, rotation: QQuaternion,
                    is_active: bool, battery_level: float, label: str):
        """Draw a VR headset."""
        color = QColor(100, 200, 100) if is_active else QColor(100, 100, 100)
        self.draw_device_shape(position, rotation, 0.15, 0.1, 0.1, color, label)
    
    def draw_tracker(self, position: QVector3D, rotation: QQuaternion,
                    is_active: bool, battery_level: float, label: str):
        """Draw a VR tracker."""
        color = QColor(200, 100, 200) if is_active else QColor(100, 100, 100)
        self.draw_device_shape(position, rotation, 0.05, 0.05, 0.05, color, label, shape='sphere')
    
    def draw_generic_device(self, position: QVector3D, rotation: QQuaternion,
                          is_active: bool, label: str):
        """Draw a generic VR device."""
        color = QColor(200, 200, 100) if is_active else QColor(100, 100, 100)
        self.draw_device_shape(position, rotation, 0.05, 0.05, 0.05, color, label, shape='cube')
    
    def draw_device_shape(self, position: QVector3D, rotation: QQuaternion,
                         width: float, height: float, depth: float,
                         color: QColor, label: str, shape: str = 'cube'):
        """Draw a 3D shape representing a device."""
        # This is a simplified 2D projection for now
        # In a full 3D implementation, we would use OpenGL or similar
        
        # Project 3D position to 2D screen space
        view_rect = self.view.viewport().rect()
        center = view_rect.center()
        
        # Simple orthographic projection for now
        scale = 100.0  # Pixels per meter
        x = center.x() + position.x() * scale
        y = center.y() - position.z() * scale  # Flip Z for screen coordinates
        
        # Draw shape
        if shape == 'sphere':
            radius = max(width, height, depth) * scale / 2
            ellipse = self.scene.addEllipse(
                x - radius, y - radius, radius * 2, radius * 2,
                QPen(color, 2),
                QBrush(color)
            )
        else:  # cube
            w = width * scale
            h = depth * scale  # Using depth for height in 2D projection
            rect = self.scene.addRect(
                x - w/2, y - h/2, w, h,
                QPen(color, 2),
                QBrush(color.lighter(150))
            )
        
        # Add label
        if self.show_device_labels and label:
            text = self.scene.addText(label, QFont("Arial", 8))
            text.setDefaultTextColor(Qt.GlobalColor.white)
            text.setPos(x - text.boundingRect().width()/2, y + h/2 + 2)
    
    def update_environment_bounds(self, bounds: Dict[str, Any]):
        """Update the environment bounds visualization.
        
        Args:
            bounds: Dictionary containing min/max bounds for the environment
        """
        try:
            min_pt = bounds.get('min', {'x': -2, 'y': 0, 'z': -2})
            max_pt = bounds.get('max', {'x': 2, 'y': 2, 'z': 2})
            
            self.environment_bounds = {
                'min': QVector3D(min_pt['x'], min_pt['y'], min_pt['z']),
                'max': QVector3D(max_pt['x'], max_pt['y'], max_pt['z']),
                'center': QVector3D(
                    (min_pt['x'] + max_pt['x']) / 2,
                    (min_pt['y'] + max_pt['y']) / 2,
                    (min_pt['z'] + max_pt['z']) / 2
                )
            }
            
            # Redraw room bounds
            self.draw_room_bounds()
            
        except Exception as e:
            logger.error(f"Error updating environment bounds: {e}")
    
    # ===== Event Handlers =====
    
    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming."""
        zoom_factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.view.scale(zoom_factor, zoom_factor)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for camera control."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_rotating = True
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = True
        self.last_mouse_pos = event.pos()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        self.is_rotating = False
        self.is_panning = False
        self.is_zooming = False
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for camera control."""
        if self.last_mouse_pos is None:
            return
            
        delta = event.pos() - self.last_mouse_pos
        
        if self.is_rotating:
            # Rotate camera
            self.camera_yaw -= delta.x() * 0.5
            self.camera_pitch = max(-89, min(89, self.camera_pitch + delta.y() * 0.5))
            self.update_camera()
        elif self.is_panning:
            # Pan camera
            move_speed = 0.01 * self.camera_distance
            self.camera_target += QVector3D(
                -delta.x() * move_speed,
                0,
                -delta.y() * move_speed
            )
            self.update_camera()
        
        self.last_mouse_pos = event.pos()
    
    def update_camera(self):
        """Update the camera position and orientation."""
        # This would update the 3D view's camera in a full 3D implementation
        pass
