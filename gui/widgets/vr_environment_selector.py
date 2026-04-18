#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR Environment Selector Widget

This module provides environment selection and management for the VR system.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any

from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QFont,
    QFontMetrics, QPixmap, QIcon, QImage, QPainterPath, QMouseEvent
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QSlider, QGroupBox, QFormLayout, QScrollArea, QFrame,
    QSizePolicy, QToolButton, QMenu, QListWidget, QListWidgetItem,
    QAbstractItemView, QStyledItemDelegate, QFileDialog, QInputDialog
)

logger = logging.getLogger(__name__)

class EnvironmentThumbnail(QWidget):
    """Thumbnail widget for VR environments."""
    
    clicked = pyqtSignal()
    
    def __init__(self, env_id: str, name: str, thumbnail_path: str = "", parent=None):
        super().__init__(parent)
        self.env_id = env_id
        self.name = name
        self.thumbnail_path = thumbnail_path
        self.is_selected = False
        self.is_hovered = False
        
        # Load thumbnail or use default
        if thumbnail_path and os.path.exists(thumbnail_path):
            self.thumbnail = QPixmap(thumbnail_path).scaled(
                200, 120, 
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            # Create a default gradient thumbnail
            self.thumbnail = QPixmap(200, 120)
            self.thumbnail.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(self.thumbnail)
            gradient = QLinearGradient(0, 0, 200, 120)
            gradient.setColorAt(0, QColor(70, 70, 100))
            gradient.setColorAt(1, QColor(30, 30, 50))
            painter.fillRect(0, 0, 200, 120, gradient)
            
            # Draw environment name
            font = QFont("Arial", 10, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.white)
            
            text_rect = QRectF(0, 0, 200, 120)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, name)
            painter.end()
        
        self.setFixedSize(200, 150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def set_selected(self, selected: bool):
        """Set the selected state of the thumbnail."""
        self.is_selected = selected
        self.update()
    
    def enterEvent(self, event):
        """Handle mouse enter event."""
        self.is_hovered = True
        self.update()
    
    def leaveEvent(self, event):
        """Handle mouse leave event."""
        self.is_hovered = False
        self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse press event."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
    
    def paintEvent(self, event):
        """Paint the thumbnail."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.setBrush(QBrush(QColor(40, 40, 40)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height() - 25, 5, 5)
        
        # Draw thumbnail
        thumb_rect = QRectF(5, 5, self.width() - 10, self.height() - 35)
        painter.drawPixmap(thumb_rect, self.thumbnail, self.thumbnail.rect())
        
        # Draw selection border
        if self.is_selected:
            pen = QPen(QColor(0, 200, 255), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(thumb_rect, 5, 5)
        
        # Draw hover effect
        if self.is_hovered:
            painter.setBrush(QBrush(QColor(255, 255, 255, 30)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(thumb_rect, 5, 5)
        
        # Draw name
        painter.setPen(Qt.GlobalColor.white)
        font = QFont("Arial", 8)
        painter.setFont(font)
        painter.drawText(5, self.height() - 20, self.width() - 10, 15, 
                        Qt.AlignmentFlag.AlignCenter, self.name)

class EnvironmentSettings(QGroupBox):
    """Environment settings panel."""
    
    settings_changed = pyqtSignal(dict)  # Emitted when settings change
    
    def __init__(self, parent=None):
        super().__init__("Environment Settings", parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the environment settings UI."""
        layout = QFormLayout()
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(10)
        
        # Environment name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Environment Name")
        self.name_edit.textChanged.connect(self.on_settings_changed)
        
        # Environment type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Indoor", "Outdoor", "Space", "Custom"])
        self.type_combo.currentTextChanged.connect(self.on_settings_changed)
        
        # Lighting
        self.lighting_slider = QSlider(Qt.Orientation.Horizontal)
        self.lighting_slider.setRange(0, 100)
        self.lighting_slider.setValue(70)
        self.lighting_slider.valueChanged.connect(self.on_settings_changed)
        
        # Gravity toggle
        self.gravity_check = QCheckBox("Enable Gravity")
        self.gravity_check.setChecked(True)
        self.gravity_check.toggled.connect(self.on_settings_changed)
        
        # Physics quality
        self.physics_combo = QComboBox()
        self.physics_combo.addItems(["Low", "Medium", "High", "Ultra"])
        self.physics_combo.currentTextChanged.connect(self.on_settings_changed)
        
        # Add widgets to layout
        layout.addRow("Name:", self.name_edit)
        layout.addRow("Type:", self.type_combo)
        layout.addRow("Lighting:", self.lighting_slider)
        layout.addRow("", self.gravity_check)
        layout.addRow("Physics:", self.physics_combo)
        
        # Add stretch to push content to top
        layout.addRow(QWidget())
        
        self.setLayout(layout)
    
    def load_environment(self, env_data: Dict[str, Any]):
        """Load environment data into the settings panel."""
        self.blockSignals(True)  # Prevent multiple signals
        
        self.name_edit.setText(env_data.get("name", ""))
        
        env_type = env_data.get("type", "Custom")
        index = self.type_combo.findText(env_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        
        self.lighting_slider.setValue(env_data.get("lighting", 70))
        self.gravity_check.setChecked(env_data.get("gravity", True))
        
        physics = env_data.get("physics", "Medium")
        index = self.physics_combo.findText(physics)
        if index >= 0:
            self.physics_combo.setCurrentIndex(index)
        
        self.blockSignals(False)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get the current settings as a dictionary."""
        return {
            "name": self.name_edit.text(),
            "type": self.type_combo.currentText(),
            "lighting": self.lighting_slider.value(),
            "gravity": self.gravity_check.isChecked(),
            "physics": self.physics_combo.currentText()
        }
    
    def on_settings_changed(self):
        """Handle settings change."""
        self.settings_changed.emit(self.get_settings())

class VREnvironmentSelector(QWidget):
    """Widget for selecting and managing VR environments."""
    
    # Signals
    environment_selected = pyqtSignal(str)  # environment_id
    environment_created = pyqtSignal(dict)  # environment_data
    environment_updated = pyqtSignal(dict)  # environment_data
    environment_deleted = pyqtSignal(str)  # environment_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_environment = None
        self.environments = {}
        self.thumbnail_cache = {}
        
        self.setup_ui()
        self.load_default_environments()
    
    def setup_ui(self):
        """Set up the environment selector UI."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # Left panel - Environment thumbnails
        thumbnails_panel = QWidget()
        thumbnails_layout = QVBoxLayout(thumbnails_panel)
        thumbnails_layout.setContentsMargins(0, 0, 0, 0)
        thumbnails_layout.setSpacing(10)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        
        self.refresh_btn = QToolButton()
        self.refresh_btn.setIcon(self.style().standardIcon(
            getattr(QStyle.StandardPixmap, 'SP_BrowserReload')
        ))
        self.refresh_btn.setToolTip("Refresh Environments")
        self.refresh_btn.clicked.connect(self.refresh_environments)
        
        self.add_btn = QToolButton()
        self.add_btn.setIcon(self.style().standardIcon(
            getattr(QStyle.StandardPixmap, 'SP_FileDialogNewFolder')
        ))
        self.add_btn.setToolTip("Add Environment")
        self.add_btn.clicked.connect(self.add_environment)
        
        self.import_btn = QToolButton()
        self.import_btn.setIcon(self.style().standardIcon(
            getattr(QStyle.StandardPixmap, 'SP_DialogOpenButton')
        ))
        self.import_btn.setToolTip("Import Environment")
        self.import_btn.clicked.connect(self.import_environment)
        
        self.delete_btn = QToolButton()
        self.delete_btn.setIcon(self.style().standardIcon(
            getattr(QStyle.StandardPixmap, 'SP_TrashIcon')
        ))
        self.delete_btn.setToolTip("Delete Environment")
        self.delete_btn.clicked.connect(self.delete_environment)
        self.delete_btn.setEnabled(False)
        
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.delete_btn)
        
        # Search bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search environments...")
        self.search_edit.textChanged.connect(self.filter_environments)
        
        # Thumbnails scroll area
        self.thumbnails_area = QScrollArea()
        self.thumbnails_area.setWidgetResizable(True)
        self.thumbnails_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.thumbnails_widget = QWidget()
        self.thumbnails_layout = QVBoxLayout(self.thumbnails_widget)
        self.thumbnails_layout.setContentsMargins(5, 5, 5, 5)
        self.thumbnails_layout.setSpacing(10)
        self.thumbnails_layout.addStretch()
        
        self.thumbnails_area.setWidget(self.thumbnails_widget)
        
        # Add widgets to thumbnails panel
        thumbnails_layout.addLayout(toolbar)
        thumbnails_layout.addWidget(self.search_edit)
        thumbnails_layout.addWidget(self.thumbnails_area)
        
        # Right panel - Environment settings
        self.settings_panel = EnvironmentSettings()
        self.settings_panel.settings_changed.connect(self.on_environment_updated)
        
        # Add panels to main layout
        main_layout.addWidget(thumbnails_panel, 2)
        main_layout.addWidget(self.settings_panel, 1)
        
        # Set initial size policy
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
    
    def load_default_environments(self):
        """Load default environments."""
        self.environments = {
            "default": {
                "id": "default",
                "name": "Default Environment",
                "type": "Indoor",
                "lighting": 70,
                "gravity": True,
                "physics": "Medium",
                "thumbnail": ""
            },
            "trading_floor": {
                "id": "trading_floor",
                "name": "Trading Floor",
                "type": "Indoor",
                "lighting": 80,
                "gravity": True,
                "physics": "High",
                "thumbnail": ""
            },
            "data_visualization": {
                "id": "data_visualization",
                "name": "Data Visualization",
                "type": "Space",
                "lighting": 30,
                "gravity": False,
                "physics": "Low",
                "thumbnail": ""
            }
        }
        
        self.update_thumbnails()
    
    def update_thumbnails(self, filter_text: str = ""):
        """Update the environment thumbnails."""
        # Clear existing thumbnails
        while self.thumbnails_layout.count() > 1:  # Keep the stretch
            item = self.thumbnails_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add thumbnails for each environment
        for env_id, env_data in self.environments.items():
            if filter_text and filter_text.lower() not in env_data["name"].lower():
                continue
                
            thumbnail = EnvironmentThumbnail(
                env_id,
                env_data["name"],
                env_data.get("thumbnail", "")
            )
            
            if env_id == self.current_environment:
                thumbnail.set_selected(True)
            
            thumbnail.clicked.connect(lambda _, eid=env_id: self.select_environment(eid))
            
            # Add to layout
            self.thumbnails_layout.insertWidget(self.thumbnails_layout.count() - 1, thumbnail)
    
    def select_environment(self, env_id: str):
        """Select an environment."""
        if env_id not in self.environments:
            return
        
        # Update current selection
        self.current_environment = env_id
        self.delete_btn.setEnabled(env_id not in ["default", "trading_floor", "data_visualization"])
        
        # Update thumbnails
        for i in range(self.thumbnails_layout.count() - 1):  # Exclude stretch
            widget = self.thumbnails_layout.itemAt(i).widget()
            if isinstance(widget, EnvironmentThumbnail):
                widget.set_selected(widget.env_id == env_id)
        
        # Load environment settings
        self.settings_panel.load_environment(self.environments[env_id])
        
        # Emit signal
        self.environment_selected.emit(env_id)
    
    def refresh_environments(self):
        """Refresh the list of environments."""
        # In a real app, this would scan for environment files
        self.update_thumbnails(self.search_edit.text())
    
    def add_environment(self):
        """Add a new environment."""
        name, ok = QInputDialog.getText(
            self,
            "Add Environment",
            "Enter environment name:",
            text=f"Environment {len(self.environments) + 1}"
        )
        
        if ok and name:
            env_id = name.lower().replace(" ", "_")
            
            # Create new environment
            new_env = {
                "id": env_id,
                "name": name,
                "type": "Custom",
                "lighting": 70,
                "gravity": True,
                "physics": "Medium",
                "thumbnail": ""
            }
            
            self.environments[env_id] = new_env
            self.update_thumbnails(self.search_edit.text())
            self.select_environment(env_id)
            
            # Emit signal
            self.environment_created.emit(new_env)
    
    def import_environment(self):
        """Import an environment from file."""
        # In a real app, this would open a file dialog to import an environment
        # For now, just show a message
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Import Environment",
            "This would open a file dialog to import an environment file."
        )
    
    def delete_environment(self):
        """Delete the current environment."""
        if not self.current_environment or self.current_environment in ["default", "trading_floor", "data_visualization"]:
            return
            
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Delete Environment",
            f"Are you sure you want to delete '{self.environments[self.current_environment]['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            env_id = self.current_environment
            
            # Find and select a different environment
            other_envs = [eid for eid in self.environments.keys() if eid != env_id]
            new_selection = other_envs[0] if other_envs else None
            
            # Emit signal before deleting
            self.environment_deleted.emit(env_id)
            
            # Delete the environment
            del self.environments[env_id]
            
            # Update UI
            if new_selection:
                self.select_environment(new_selection)
            self.update_thumbnails(self.search_edit.text())
    
    def filter_environments(self, text: str):
        """Filter environments by name."""
        self.update_thumbnails(text)
    
    def on_environment_updated(self, settings: Dict[str, Any]):
        """Handle environment settings update."""
        if not self.current_environment:
            return
            
        # Update environment data
        env_id = self.current_environment
        self.environments[env_id].update(settings)
        
        # Update thumbnails if name changed
        if "name" in settings:
            self.update_thumbnails(self.search_edit.text())
        
        # Emit signal
        self.environment_updated.emit(self.environments[env_id])
    
    def get_current_environment(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected environment data."""
        if not self.current_environment:
            return None
        return self.environments.get(self.current_environment)

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Set dark theme
    app.setStyle("Fusion")
    
    window = VREnvironmentSelector()
    window.setWindowTitle("VR Environment Selector")
    window.resize(800, 600)
    window.show()
    
    sys.exit(app.exec())
