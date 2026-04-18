#!/usr/bin/env python3
"""
Kingdom AI GUI Frames Package
Contains all frame components for the Kingdom AI application.

This module provides conditional imports with graceful fallbacks for all frame components.
"""

import logging

_logger = logging.getLogger("KingdomAI.GUI.Frames")

# Import base frame class
from .base_frame import BaseFrame

# Import available frame components with safe fallbacks
from .dashboard_frame import DashboardFrame
from .trading_frame import TradingFrame
from .ai_frame import AIFrame
from .wallet_frame import WalletFrame
from .vr_frame import VRFrame
from .settings_frame import SettingsFrame
from .voice_frame import VoiceFrame
from .code_generator_frame import CodeGeneratorFrame
from .thoth_frame import ThothFrame

# Conditional import for APIKeysFrame to avoid matplotlib backend conflicts
try:
    import matplotlib
    # Use QtAgg backend for PyQt6 compatibility
    try:
        matplotlib.use("QtAgg")  # PyQt6 compatible backend
    except Exception:
        try:
            matplotlib.use("QtAgg")  # Use QtAgg for PyQt6
        except Exception:
            pass  # Use default if both fail
    from .api_keys_frame import APIKeysFrame
except Exception as e:
    _logger.warning(f"APIKeysFrame not available: {e}")
    APIKeysFrame = None

# Conditional import for CodeGeneratorQt (PyQt6 dependency)
try:
    from .code_generator_qt import CodeGeneratorQt
except Exception as e:
    _logger.warning(f"CodeGeneratorQt not available: {e}")
    CodeGeneratorQt = None

# Import DiagnosticFrame - prefer PyQt6 version
# Export BOTH names for compatibility - some code uses DiagnosticFrame, some uses DiagnosticsFrame
DiagnosticFrame = None
DiagnosticsFrame = None
try:
    from .diagnostic_frame_qt import DiagnosticsFrame
    DiagnosticFrame = DiagnosticsFrame  # Alias for backward compatibility
except ImportError:
    try:
        from .diagnostic_frame import DiagnosticsFrame
        DiagnosticFrame = DiagnosticsFrame  # Alias for backward compatibility
    except Exception as e:
        _logger.warning(f"DiagnosticFrame not available: {e}")
        DiagnosticFrame = None
        DiagnosticsFrame = None

# Conditional import for LinkFrame (has PyQt dependencies)
try:
    from .link_frame import LinkFrame
except Exception as e:
    _logger.warning(f"LinkFrame not available: {e}")
    LinkFrame = None

# Import MiningFrame from the PyQt version
try:
    from .mining_frame_pyqt import MiningFrame
except Exception as e:
    try:
        from .mining_frame_new import MiningFrame
    except Exception as e2:
        _logger.warning(f"MiningFrame not available: {e}, {e2}")
        MiningFrame = None

# Import WalletQt (PyQt6 version of wallet)
try:
    from .wallet_qt import WalletQt
except Exception as e:
    _logger.warning(f"WalletQt not available: {e}")
    WalletQt = None

# Import BaseFrameQt for PyQt6 based frames
try:
    from .base_frame_qt import BaseFrameQt
except Exception as e:
    _logger.warning(f"BaseFrameQt not available: {e}")
    BaseFrameQt = None

# Export all available classes
__all__ = [
    'BaseFrame',
    'DashboardFrame',
    'TradingFrame',
    'AIFrame',
    'WalletFrame',
    'VRFrame',
    'SettingsFrame',
    'VoiceFrame',
    'CodeGeneratorFrame',
    'ThothFrame',
]

# Conditionally add optional classes
if APIKeysFrame is not None:
    __all__.append('APIKeysFrame')
if CodeGeneratorQt is not None:
    __all__.append('CodeGeneratorQt')
if DiagnosticFrame is not None:
    __all__.append('DiagnosticFrame')
    __all__.append('DiagnosticsFrame')  # Export both names for compatibility
if LinkFrame is not None:
    __all__.append('LinkFrame')
if MiningFrame is not None:
    __all__.append('MiningFrame')
if WalletQt is not None:
    __all__.append('WalletQt')
if BaseFrameQt is not None:
    __all__.append('BaseFrameQt')