#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Widgets Package for Kingdom AI

This package provides custom widgets used throughout the Kingdom AI GUI.
"""

from .led_indicator import QLedIndicator
from .tab_manager import TabManager
from .system_indicator import SystemStatusIndicator

# SOTA 2026: Sentience Status Meter - Visual consciousness level indicator
try:
    from .sentience_status_meter import (
        SentienceStatusMeter,
        ConsciousnessLevel,
        CircularGaugePainter,
        MetricBar,
        create_sentience_meter,
        LEVEL_THRESHOLDS,
        LEVEL_COLORS,
        LEVEL_DESCRIPTIONS
    )
    SENTIENCE_METER_AVAILABLE = True
except ImportError as e:
    SENTIENCE_METER_AVAILABLE = False
    SentienceStatusMeter = None
    ConsciousnessLevel = None

# SOTA 2026: Visual Creation Canvas - Real-time AI image/animation generation
try:
    from .visual_creation_canvas import VisualCreationCanvas, VisualMode, GenerationConfig
    VISUAL_CANVAS_AVAILABLE = True
except ImportError as e:
    VISUAL_CANVAS_AVAILABLE = False
    VisualCreationCanvas = None
    VisualMode = None
    GenerationConfig = None

# Export all widget classes
__all__ = [
    'QLedIndicator', 
    'TabManager', 
    'SystemStatusIndicator',
    'SentienceStatusMeter',
    'ConsciousnessLevel',
    'CircularGaugePainter',
    'MetricBar',
    'create_sentience_meter',
    'SENTIENCE_METER_AVAILABLE',
    'VisualCreationCanvas',
    'VisualMode',
    'GenerationConfig',
    'VISUAL_CANVAS_AVAILABLE'
]
