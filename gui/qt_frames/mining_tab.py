"""
Mining Tab - Redirect to actual mining tab
This file exists to satisfy the qt_frames import requirements.
"""

from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

# Define base class for type checking
class MiningTab(QWidget):
    """Mining Tab Widget"""
    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Mining Tab - Loading..."))
        self.setLayout(layout)

# Create alias immediately for type checker
MiningFrame = MiningTab

# Try to import the actual implementation at runtime
if not TYPE_CHECKING:
    try:
        from gui.qt_frames.mining.mining_frame import MiningTab as MiningTabImpl
        MiningTab = MiningTabImpl  # type: ignore[misc,assignment]
        MiningFrame = MiningTab  # type: ignore[misc,assignment]
        print("Successfully imported MiningTab from gui.qt_frames.mining.mining_frame")
    except Exception as e:
        print(f"MiningTab import failed: {e} - using fallback")

# Export both names
__all__ = ['MiningTab', 'MiningFrame']
