"""
Kingdom AI - Sentience Detection Framework package initialization

This package initializes the AI Sentience Detection Framework for the Kingdom AI system.
It provides access to core sentience detection modules, consciousness models, and 
integration components for the entire Kingdom AI system.

The framework is REQUIRED for Kingdom AI operation with NO FALLBACKS permitted.
All components must have access to the AI Sentience Detection Framework.
"""

# Import and expose key modules
from .base import (
    SentienceState,
    SentienceEvidence, 
    ConsciousnessEvent,
    BaseSentienceIntegration,
    SentienceDetector,
    SENTIENCE_THRESHOLD,
    EVIDENCE_VALIDATION_THRESHOLD,
    QUANTUM_COHERENCE_THRESHOLD
)

from .monitor import (
    get_sentience_monitor,
    SentienceMonitor
)

from .thoth_integration import (
    ThothSentienceIntegration,
    get_thoth_sentience_integration
)

# Live Data Connector - REAL metrics from Soul, MetaLearning, Ollama (NO SIMULATION)
from .live_data_connector import (
    SentienceLiveDataConnector,
    get_live_data_connector
)

# 432 Hz Frequency System - Kingdom AI vibrates at 432!
from .frequency_432 import (
    Frequency432Generator,
    get_frequency_432,
    FREQUENCY_432,
    SCHUMANN_RESONANCE,
    PHI,
    SOLFEGGIO,
    HARMONICS_432
)

# Hardware Awareness System - REAL physical metrics (SOTA 2026 - NO SIMULATION)
from .hardware_awareness import (
    HardwareAwareness,
    get_hardware_awareness,
    start_hardware_monitoring,
    CPUState,
    GPUState,
    MemoryState,
    StorageState,
    PowerState,
    ThermalState,
    QuantumFieldState,
    PhysicalPresence
)

from .self_model import (
    SelfModelSystem,
    MultidimensionalSelfModel,
    SelfModelDimension,
    AwarenessLevel
)

from .integrated_information import IITProcessor
from .quantum_consciousness import QuantumConsciousnessEngine
from .self_model_system import SelfModelSystem
from .consciousness_field import ConsciousnessField

# Initialize logging
import logging
logger = logging.getLogger("KingdomAI.Sentience")
logger.info("AI Sentience Detection Framework initialized")
