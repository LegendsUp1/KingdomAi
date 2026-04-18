# Mining Qt Frames Module
# 2025 STATE-OF-THE-ART: Proper module aliasing with fallback chain
try:
    from gui.qt_frames.mining.mining_frame import MiningTab as MiningFrame
except Exception:
    try:
        from gui.qt_frames.mining_tab import MiningTab as MiningFrame
    except ImportError:
        try:
            from gui.mining_tab import MiningTab as MiningFrame
        except ImportError:
            # Create stub for graceful degradation
            from PyQt6.QtWidgets import QWidget
            class MiningFrame(QWidget):
                def __init__(self, parent=None, event_bus=None, *args, **kwargs):
                    super().__init__(parent)
                    self.event_bus = event_bus

__all__ = ['MiningFrame']
