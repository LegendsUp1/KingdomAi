# Type stub for mining_tab module
from PyQt6.QtWidgets import QWidget
from typing import Optional, Any

class MiningTab(QWidget):
    event_bus: Optional[Any]
    def __init__(self, event_bus: Optional[Any] = None, parent: Optional[QWidget] = None) -> None: ...

# Alias for compatibility
MiningFrame = MiningTab

__all__ = ['MiningTab', 'MiningFrame']
