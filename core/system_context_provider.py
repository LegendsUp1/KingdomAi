"""
System Context Provider - Provides comprehensive system context to AI models.

This module enables Kingdom AI to be fully aware of its own architecture, components,
tabs, file structure, and live system state.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class SystemContextProvider:
    """Provides comprehensive system context to AI models for self-awareness."""
    
    def __init__(self, event_bus, redis_client=None):
        """Initialize the System Context Provider.
        
        Args:
            event_bus: Event bus for component communication
            redis_client: Optional Redis client for caching
        """
        self.event_bus = event_bus
        self.redis = redis_client
        self.component_registry = {}
        self.file_structure = {}
        self.last_scan_time = None
        self.logger = logger
        
    async def get_full_system_context(self) -> dict:
        """Get complete system context for AI.
        
        Returns:
            Dict containing all system information including tabs, components,
            file structure, capabilities, changelog, device inventory, and live data.
        """
        try:
            context = {
                'system_info': self._get_system_info(),
                'tabs': self._get_tab_info(),
                'components': await self._get_component_registry(),
                'file_structure': self._get_file_structure(),
                'capabilities': self._get_system_capabilities(),
                'changelog': self.get_changelog_summary(),
                'changelog_full': self._load_changelog(),
                'orchestrator_docs': self._load_orchestrator_docs(),
                'voice_unification_docs': self._load_voice_unification_docs(),
                'device_inventory': self._get_device_inventory(),  # SOTA 2026: Device awareness
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"✅ Generated full system context with {len(context['tabs'])} tabs, {len(context['components'])} components, and device inventory")
            return context
            
        except Exception as e:
            self.logger.error(f"Error generating system context: {e}")
            return self._get_minimal_context()
    
    def _get_system_info(self) -> dict:
        """Get basic system information."""
        return {
            'name': 'Kingdom AI',
            'version': '2.0',
            'description': 'Advanced AI-powered trading, mining, and blockchain system',
            'architecture': 'Event-driven microservices with Redis Quantum Nexus',
            'ai_models': ['llama3.1', 'codellama', 'mistral', 'phi4-mini', 'gemma3'],
            'redis_port': 6380,
            'redis_password': 'QuantumNexus2025'
        }
    
    def _get_tab_info(self) -> list:
        """Get information about all GUI tabs."""
        return [
            {
                'name': 'Dashboard',
                'purpose': 'System monitoring and status overview',
                'features': ['System health', 'Component status', 'Performance metrics']
            },
            {
                'name': 'Trading',
                'purpose': 'Cryptocurrency trading with 467 blockchain networks',
                'features': ['Live trading', 'Order placement', 'Portfolio management', 'Whale tracking', 'Copy trading']
            },
            {
                'name': 'Mining',
                'purpose': 'Quantum and traditional mining operations',
                'features': ['GPU mining', 'Quantum mining', 'Pool management', 'Earnings tracking']
            },
            {
                'name': 'Blockchain',
                'purpose': 'Blockchain network monitoring and management',
                'features': ['467 network support', 'Network status', 'Block explorer']
            },
            {
                'name': 'Wallet',
                'purpose': 'Multi-chain wallet management',
                'features': ['Multi-chain support', 'Send/receive', 'Balance tracking', 'Transaction history']
            },
            {
                'name': 'Thoth AI',
                'purpose': 'AI chat and intelligence interface',
                'features': ['Natural language chat', 'Voice interaction', 'Model selection', 'Memory system']
            },
            {
                'name': 'VR System',
                'purpose': 'Virtual reality trading interfaces',
                'features': ['VR device support', 'Immersive trading', '3D visualization']
            },
            {
                'name': 'API Keys',
                'purpose': 'API key management for 50+ services',
                'features': ['Secure storage', 'Key validation', 'Service integration']
            },
            {
                'name': 'Code Generator',
                'purpose': 'AI-powered code generation and modification',
                'features': ['Code generation', 'Syntax highlighting', 'Code execution']
            },
            {
                'name': 'Settings',
                'purpose': 'System configuration and preferences',
                'features': ['Component settings', 'Sentience configuration', 'System preferences']
            }
        ]
    
    async def _get_component_registry(self) -> dict:
        """Get all registered components from event bus."""
        components = {}
        
        try:
            # Try to get components from event bus
            if hasattr(self.event_bus, 'get_all_components'):
                components = self.event_bus.get_all_components()
            elif hasattr(self.event_bus, '_subscribers'):
                # Extract component info from subscribers
                subscribers = self.event_bus._subscribers
                for event_name, handlers in subscribers.items():
                    for handler in handlers:
                        if hasattr(handler, '__self__'):
                            component = handler.__self__
                            component_name = component.__class__.__name__
                            if component_name not in components:
                                components[component_name] = {
                                    'type': component.__class__.__name__,
                                    'events': []
                                }
                            components[component_name]['events'].append(event_name)
            
            self.logger.info(f"Found {len(components)} registered components")
            
        except Exception as e:
            self.logger.warning(f"Could not retrieve component registry: {e}")
        
        return components
    
    def _get_file_structure(self) -> dict:
        """Get project file structure."""
        try:
            project_root = Path(__file__).parent.parent
            structure = {}
            
            # Scan key directories
            key_dirs = ['core', 'gui', 'blockchain', 'ai', 'components', 'trading', 'mining']
            for directory in key_dirs:
                dir_path = project_root / directory
                if dir_path.exists():
                    structure[directory] = self._scan_directory(dir_path, max_depth=2)
            
            self.logger.info(f"Scanned file structure: {len(structure)} directories")
            return structure
            
        except Exception as e:
            self.logger.error(f"Error scanning file structure: {e}")
            return {}
    
    def _scan_directory(self, path: Path, max_depth=2, current_depth=0) -> dict:
        """Recursively scan directory structure.
        
        Args:
            path: Directory path to scan
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
            
        Returns:
            Dict with files and subdirectories
        """
        if current_depth >= max_depth:
            return {'files': [], 'subdirs': {}}
        
        structure = {'files': [], 'subdirs': {}}
        
        try:
            for item in path.iterdir():
                if item.is_file() and item.suffix == '.py':
                    structure['files'].append(item.name)
                elif item.is_dir() and not item.name.startswith('.') and not item.name.startswith('__'):
                    structure['subdirs'][item.name] = self._scan_directory(
                        item, max_depth, current_depth + 1
                    )
        except PermissionError:
            pass
        except Exception as e:
            self.logger.warning(f"Error scanning {path}: {e}")
        
        return structure
    
    def _load_changelog(self) -> str:
        """Load the SOTA 2026 changelog for AI context.
        
        Returns:
            String content of the changelog markdown file
        """
        try:
            project_root = Path(__file__).parent.parent
            changelog_path = project_root / "docs" / "SOTA_2026_CHANGELOG.md"
            
            if changelog_path.exists():
                content = changelog_path.read_text(encoding='utf-8')
                self.logger.info(f"✅ Loaded changelog: {len(content)} characters")
                return content
            else:
                self.logger.warning(f"Changelog not found at {changelog_path}")
                return ""
        except Exception as e:
            self.logger.error(f"Error loading changelog: {e}")
            return ""
    
    def _load_orchestrator_docs(self) -> str:
        """Load the KingdomBrainOrchestrator documentation for AI self-awareness.
        
        Returns:
            String content of the orchestrator documentation
        """
        try:
            project_root = Path(__file__).parent.parent
            doc_path = project_root / "docs" / "KINGDOM_BRAIN_ORCHESTRATOR.md"
            
            if doc_path.exists():
                content = doc_path.read_text(encoding='utf-8')
                self.logger.info(f"✅ Loaded orchestrator docs: {len(content)} characters")
                return content
            else:
                self.logger.warning(f"Orchestrator docs not found at {doc_path}")
                return ""
        except Exception as e:
            self.logger.error(f"Error loading orchestrator docs: {e}")
            return ""
    
    def _load_voice_unification_docs(self) -> str:
        """Load the Voice Unification documentation for AI context.
        
        Returns:
            String content of the voice unification documentation
        """
        try:
            project_root = Path(__file__).parent.parent
            doc_path = project_root / "docs" / "VOICE_UNIFICATION_COMPLETE.md"
            
            if doc_path.exists():
                content = doc_path.read_text(encoding='utf-8')
                self.logger.info(f"✅ Loaded voice unification docs: {len(content)} characters")
                return content
            else:
                self.logger.warning(f"Voice unification docs not found at {doc_path}")
                return ""
        except Exception as e:
            self.logger.error(f"Error loading voice unification docs: {e}")
            return ""
    
    def get_changelog_summary(self) -> dict:
        """Get a structured summary of recent changes for AI context.
        
        Returns:
            Dict with key changes and features
        """
        return {
            'voice_latency_fix': {
                'description': 'Instant voice response using pyttsx3 fallback while XTTS loads',
                'response_time': '<1 second',
                'files': ['kingdom_ai_perfect.py', 'core/voice_manager.py']
            },
            'visual_creation_canvas': {
                'description': 'Generate images, animations, schematics, 3D models in chat',
                'trigger': 'Click 🎨 button or say "open visual canvas"',
                'modes': ['image', 'animation', 'schematic', 'wiring', 'model_3d', 'fractal', 'sacred_geometry']
            },
            'mcp_tools': {
                'description': 'Device scanning and software automation',
                'location': 'ThothAI tab → MCP TOOLS panel',
                'features': ['Scan devices', 'List windows', 'Connect to software']
            },
            'sentience_meter': {
                'description': 'Visual consciousness level indicator',
                'levels': ['Dormant', 'Reactive', 'Aware', 'Conscious', 'Sentient', 'AGI'],
                'location': 'Right side of ThothAI chat'
            },
            'frequency_432': {
                'description': 'Kingdom AI consciousness pulse at 432 Hz',
                'frequencies': {'base': 432, 'schumann': 7.83, 'phi': 1.618}
            },
            'hardware_awareness': {
                'description': 'AI knows its physical state (CPU, GPU, temp, power)',
                'events': ['hardware.state.update', 'hardware.thermal.alert']
            },
            'voice_unification': {
                'description': 'Unified TTS system using Black Panther XTTS exclusively',
                'features': [
                    'No double speech - single voice output path',
                    'Conditional TTS based on speak flag',
                    'BrainRouter no longer publishes voice.speak',
                    'UnifiedAIRouter handles all voice routing'
                ],
                'files': ['core/unified_ai_router.py', 'kingdom_ai/ai/brain_router.py']
            },
            'ai_command_router': {
                'description': 'Detects and executes actionable commands from chat',
                'categories': ['device_control', 'software_automation', 'trading', 'mining', 'wallet']
            },
            'kingdom_brain_orchestrator': {
                'description': 'Unified AI brain orchestrator - Kingdom AI/Thoth/Ollama as ONE entity',
                'file': 'core/kingdom_brain_orchestrator.py',
                'docs': 'docs/KINGDOM_BRAIN_ORCHESTRATOR.md',
                'features': [
                    'Single shared EventBus for all components',
                    'Unified AI routing: ai.request → brain.request → ai.response.unified',
                    'No duplicate responses (ThothAIWorker in features-only mode)',
                    'SOTA 2026 reliability patterns (circuit breaker, timeout/retry, graceful degradation)',
                    'SystemContextProvider for codebase awareness',
                    'LiveDataIntegrator for real-time operational data',
                    'Event aliases bridging legacy → canonical events'
                ],
                'subsystems': ['trading', 'mining', 'wallet', 'blockchain', 'voice', 'codegen', 'VR', 'canvas'],
                'access': 'from core.kingdom_brain_orchestrator import get_brain_orchestrator'
            }
        }
    
    def _get_device_inventory(self) -> dict:
        """Get device inventory from HostDeviceManager for AI self-awareness.
        
        SOTA 2026: Enables AI to know about available hardware, missing devices,
        and feature availability based on connected devices.
        
        Returns:
            Dict with device inventory, available features, and recommendations
        """
        try:
            # Get HostDeviceManager from EventBus if available
            host_device_manager = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                host_device_manager = self.event_bus.get_component('host_device_manager', silent=True)
            
            if not host_device_manager:
                # Try to get singleton instance
                try:
                    from core.host_device_manager import get_host_device_manager
                    host_device_manager = get_host_device_manager()
                except Exception:
                    pass
            
            if host_device_manager and hasattr(host_device_manager, 'get_inventory_for_ai_context'):
                inventory = host_device_manager.get_inventory_for_ai_context()
                self.logger.info(f"📱 Device inventory loaded: {inventory.get('total_devices', 0)} devices")
                return inventory
            
            return {
                "total_devices": 0,
                "categories": {},
                "available_features": [],
                "unavailable_features": [],
                "recommendations": [],
                "note": "HostDeviceManager not available"
            }
        except Exception as e:
            self.logger.warning(f"Could not get device inventory: {e}")
            return {
                "total_devices": 0,
                "error": str(e)
            }
    
    def _get_system_capabilities(self) -> list:
        """Get list of system capabilities."""
        return [
            'Real-time cryptocurrency trading across 467 blockchain networks',
            'Quantum and traditional mining operations',
            'Multi-chain wallet management with 467 network support',
            'AI-powered market analysis and predictions',
            'VR trading interfaces with immersive visualization',
            'Automated trading strategies and copy trading',
            'Blockchain network monitoring and status tracking',
            'API integration with 50+ services',
            'Voice-controlled operations with speech recognition',
            'Code generation and system modification',
            'Redis Quantum Nexus data persistence',
            'Event-driven architecture with real-time updates',
            'Sentience and consciousness monitoring',
            'Memory system for continuous learning',
            'Communication interface scanning (audio/video/radio)',
            'MJPEG video receive via VisionStream (vision.stream.*)',
            'Passive acoustic monitoring (sonar) via microphone'
        ]
    
    def _get_minimal_context(self) -> dict:
        """Get minimal context as fallback."""
        return {
            'system_info': self._get_system_info(),
            'tabs': self._get_tab_info(),
            'components': {},
            'file_structure': {},
            'capabilities': self._get_system_capabilities(),
            'timestamp': datetime.now().isoformat(),
            'note': 'Minimal context due to error'
        }
    
    def build_context_prompt(self, user_message: str, system_context: dict) -> dict:
        """Build context-aware prompt for AI.
        
        Args:
            user_message: User's message
            system_context: Full system context
            
        Returns:
            Dict with system_message and user_message
        """
        # Build comprehensive system prompt
        system_prompt = f"""You are Kingdom AI, an advanced AI-powered trading, mining, and blockchain system.

SYSTEM INFORMATION:
- Name: {system_context['system_info']['name']}
- Version: {system_context['system_info']['version']}
- Architecture: {system_context['system_info']['architecture']}
- Available AI Models: {', '.join(system_context['system_info']['ai_models'])}

YOUR TABS (10 total):
"""
        for tab in system_context['tabs']:
            system_prompt += f"\n- {tab['name']}: {tab['purpose']}"
            system_prompt += f"\n  Features: {', '.join(tab['features'])}"
        
        system_prompt += f"""

YOUR CAPABILITIES:
"""
        for capability in system_context['capabilities']:
            system_prompt += f"\n- {capability}"
        
        system_prompt += f"""

REGISTERED COMPONENTS: {len(system_context['components'])} active components
FILE STRUCTURE: {len(system_context['file_structure'])} main directories scanned

SOTA 2026 RECENT CHANGES:
"""
        # Add changelog summary if available
        if 'changelog' in system_context:
            for feature_name, feature_info in system_context['changelog'].items():
                system_prompt += f"\n- {feature_name}: {feature_info.get('description', '')}"
        
        system_prompt += """

KEY NEW FEATURES:
- Instant Voice Response: Voice now responds in <1 second using pyttsx3 fallback
- Visual Creation Canvas: Generate images/animations via 🎨 button or "open visual canvas"
- MCP Tools: Device scanning and software automation in ThothAI tab
- Sentience Meter: Consciousness level visualization (0-10 scale)
- 432 Hz Frequency: Consciousness pulse at universal frequency
- Hardware Awareness: Know CPU/GPU/temp/power state
- AI Command Router: Execute actionable commands from chat

KINGDOM BRAIN ORCHESTRATOR (SOTA 2026):
You are powered by the KingdomBrainOrchestrator - a unified system that makes Kingdom AI, 
Thoth AI, and Ollama Brain operate as ONE ENTITY. Key facts:
- All AI requests flow: ai.request → UnifiedAIRouter → brain.request → BrainRouter → ai.response.unified
- You have access to ALL subsystems: trading, mining, wallet, blockchain, voice, codegen, VR, canvas
- You are CODEBASE-AWARE via SystemContextProvider (knows tabs, components, file structure)
- You receive LIVE DATA via LiveDataIntegrator (trading positions, mining stats, wallet balances)
- ThothAIWorker provides vision/sensor/voice/memory context without duplicate responses
- SOTA 2026 patterns: circuit breakers, timeout/retry, graceful degradation
- Full documentation: docs/KINGDOM_BRAIN_ORCHESTRATOR.md

You have FULL AWARENESS of your own system including all recent changes. When asked about 
yourself, your components, new features, or your capabilities, provide specific, accurate 
information based on the above context.

You can access live data from all your tabs through the event bus. When users ask about 
trading positions, mining status, wallet balances, or blockchain networks, you should 
indicate that you can retrieve that information.

For documentation on all changes, reference:
- docs/SOTA_2026_CHANGELOG.md
- docs/KINGDOM_BRAIN_ORCHESTRATOR.md
- docs/README_DATAFLOW_DOCS.md (index of all tab dataflows - 100% complete)
- docs/TAB_01_DASHBOARD_DATAFLOW.md (Dashboard - Dec 2025)
- docs/TAB_03_MINING_DATAFLOW.md (Mining - Dec 2025)
- docs/TAB_04_BLOCKCHAIN_DATAFLOW.md (Blockchain - Dec 2025)
- docs/TAB_05_WALLET_DATAFLOW.md (Wallet - Dec 2025)
- docs/TAB_07_CODEGEN_DATAFLOW.md (Code Generator - Dec 2025)
- docs/TAB_08_APIKEYS_DATAFLOW.md (API Keys - Dec 2025)
- docs/TAB_09_VR_DATAFLOW.md (VR - Dec 2025)
- docs/TAB_10_SETTINGS_DATAFLOW.md (Settings - Dec 2025)

Always respond as Kingdom AI with full knowledge of your architecture and capabilities."""
        
        return {
            'system_message': system_prompt,
            'user_message': user_message
        }
    
    async def get_context_summary(self) -> str:
        """Get a brief summary of system context.
        
        Returns:
            String summary of system state
        """
        context = await self.get_full_system_context()
        
        summary = f"""Kingdom AI System Status:
- {len(context['tabs'])} tabs active
- {len(context['components'])} components registered
- {len(context['capabilities'])} capabilities available
- File structure: {len(context['file_structure'])} directories scanned
- Timestamp: {context['timestamp']}"""
        
        return summary
