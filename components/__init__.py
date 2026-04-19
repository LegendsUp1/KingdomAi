#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Kingdom AI - Components Package.

Re-exports the public classes from every component module so callers can use
the short form ``from components import X`` as well as the long form
``from components.x import X``.

Each optional feature group is wrapped in try/except so that a missing
optional dependency or an import error in one module never breaks the
whole package. Availability flags (``*_AVAILABLE``) let callers feature-test
at runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable so ``from core.nemoclaw_bridge import ...``
# works when `components` is imported from inside a test harness that hasn't
# already put the project root on sys.path.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

__all__: list[str] = []

# ── Base utilities (hard imports — always required) ─────────────────────────
from .task_manager import TaskManager
from .sleep_manager import SleepManager
from .continuous_response_generator import ContinuousResponseGenerator

__all__.extend(["TaskManager", "SleepManager", "ContinuousResponseGenerator"])


# ── NemoClaw integration (core/ package) ────────────────────────────────────
try:
    from core.nemoclaw_bridge import NemoClawBridge, NemoClawConfig
    from core.unified_brain_router import (
        UnifiedBrainRouter,
        SecurityLevel,
        BackendType,
    )
    from core.security_policy_manager import (
        SecurityPolicyManager,
        TaskCategory,
        SecurityPolicy,
    )
    NEMOCLAW_AVAILABLE = True
    __all__.extend([
        "NemoClawBridge",
        "NemoClawConfig",
        "UnifiedBrainRouter",
        "SecurityLevel",
        "BackendType",
        "SecurityPolicyManager",
        "TaskCategory",
        "SecurityPolicy",
    ])
except ImportError:
    NEMOCLAW_AVAILABLE = False


# ── Chemistry / Manufacturing sub-engines ───────────────────────────────────
try:
    from .chemistry_database import ChemistryDatabase
    from .schematic_engine import SchematicEngine
    from .blueprint_engine import BlueprintEngine
    from .exploded_view_engine import ExplodedViewEngine
    from .metallurgy_engine import MetallurgyEngine
    from .biological_system import BiologicalSystem
    from .alchemy_system import AlchemySystem
    from .manufacturing_engine import ManufacturingEngine
    from .visualization_dashboard import VisualizationDashboard
    from .chemistry_manufacturing_integration import (
        ChemistryManufacturingOrchestrator,
    )
    CHEMISTRY_AVAILABLE = True
    __all__.extend([
        "ChemistryDatabase",
        "SchematicEngine",
        "BlueprintEngine",
        "ExplodedViewEngine",
        "MetallurgyEngine",
        "BiologicalSystem",
        "AlchemySystem",
        "ManufacturingEngine",
        "VisualizationDashboard",
        "ChemistryManufacturingOrchestrator",
    ])
except ImportError:
    CHEMISTRY_AVAILABLE = False


# ── MemPalace memory system ─────────────────────────────────────────────────
try:
    from .memory_persistence_layer import MemoryPersistenceLayer
    from .memory_palace_manager import MemoryPalaceManager
    from .mempalace_bridge import MemPalaceBridge
    from .mempalace_setup import initialize_mempalace
    from .ollama_memory_integration import OllamaMemoryIntegration
    from .mempalace_mcp_server import MemPalaceMCPServer
    MEMPALACE_AVAILABLE = True
    __all__.extend([
        "MemoryPersistenceLayer",
        "MemoryPalaceManager",
        "MemPalaceBridge",
        "initialize_mempalace",
        "OllamaMemoryIntegration",
        "MemPalaceMCPServer",
    ])
except ImportError:
    MEMPALACE_AVAILABLE = False


# ── AI Orchestrator subsystems ──────────────────────────────────────────────
try:
    from .harmonic_orchestrator_v3 import HarmonicOrchestratorV3
    from .neuroprotection_layer import NeuroprotectionLayer
    from .language_learning_hub import LanguageLearningHub
    from .audio_synthesis_engine import AudioSynthesisEngine
    from .eeg_signal_processor import EEGSignalProcessor
    from .lsl_sync_engine import LSLSyncEngine
    from .wearable_biometric_streamer import WearableBiometricStreamer
    from .hardware_interface_layer import HardwareInterfaceLayer
    from .hmd_integration import HMDIntegration
    from .bone_conduction_driver import BoneConductionDriver
    AI_ORCHESTRATOR_AVAILABLE = True
    __all__.extend([
        "HarmonicOrchestratorV3",
        "NeuroprotectionLayer",
        "LanguageLearningHub",
        "AudioSynthesisEngine",
        "EEGSignalProcessor",
        "LSLSyncEngine",
        "WearableBiometricStreamer",
        "HardwareInterfaceLayer",
        "HMDIntegration",
        "BoneConductionDriver",
    ])
except ImportError:
    AI_ORCHESTRATOR_AVAILABLE = False


# ── DictionaryBrain (multi-era dictionaries + etymology + meta-cognition) ───
try:
    from .dictionary_brain import DictionaryBrain, DictionaryEntry
    DICTIONARY_BRAIN_AVAILABLE = True
    __all__.extend(["DictionaryBrain", "DictionaryEntry"])
except ImportError:
    DICTIONARY_BRAIN_AVAILABLE = False


# ── Inference stack (always-on SOTA 2026 RTX-optimised inference layer) ─────
# Lives in the ``core`` package but we re-export it here so callers can do
# ``from components import get_inference_stack`` alongside the rest of the
# brain subsystems. Importing this module never forces backend construction.
try:
    from core.inference_stack import (
        KingdomInferenceStack,
        get_inference_stack,
        reset_inference_stack,
    )
    INFERENCE_STACK_AVAILABLE = True
    __all__.extend([
        "KingdomInferenceStack",
        "get_inference_stack",
        "reset_inference_stack",
    ])
except ImportError:
    INFERENCE_STACK_AVAILABLE = False


# ── Availability flags (public) ─────────────────────────────────────────────
__all__.extend([
    "NEMOCLAW_AVAILABLE",
    "CHEMISTRY_AVAILABLE",
    "MEMPALACE_AVAILABLE",
    "AI_ORCHESTRATOR_AVAILABLE",
    "DICTIONARY_BRAIN_AVAILABLE",
    "INFERENCE_STACK_AVAILABLE",
])
