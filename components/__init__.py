#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Components Package
"""

from .task_manager import TaskManager
from .sleep_manager import SleepManager
from .continuous_response_generator import ContinuousResponseGenerator

# NemoClaw Integration
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from core.nemoclaw_bridge import NemoClawBridge, NemoClawConfig
    from core.unified_brain_router import UnifiedBrainRouter, SecurityLevel, BackendType
    from core.security_policy_manager import SecurityPolicyManager, TaskCategory, SecurityPolicy
    NEMOCLAW_AVAILABLE = True
except ImportError:
    NEMOCLAW_AVAILABLE = False

__all__ = [
    'TaskManager',
    'SleepManager',
    'ContinuousResponseGenerator',
]

# Add NemoClaw modules if available
if NEMOCLAW_AVAILABLE:
    __all__.extend([
        'NemoClawBridge',
        'NemoClawConfig',
        'UnifiedBrainRouter',
        'SecurityLevel',
        'BackendType',
        'SecurityPolicyManager',
        'TaskCategory',
        'SecurityPolicy'
    ])
