#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System Knowledge Loader for Kingdom AI - SOTA 2026

Loads documentation files and makes them accessible to the Ollama brain
and chat widget for contextual AI responses.

SOTA 2026 UPDATE: Now integrates with CodebaseIntrospector for full
codebase access including source files, AST analysis, and runtime editing.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Import CodebaseIntrospector for full codebase access
try:
    from core.codebase_introspector import get_codebase_introspector, CodebaseIntrospector
    CODEBASE_INTROSPECTOR_AVAILABLE = True
except ImportError:
    CODEBASE_INTROSPECTOR_AVAILABLE = False
    logger.warning("CodebaseIntrospector not available - source file access limited")

# Base path for documentation
DOCS_PATH = Path(__file__).parent.parent / "docs"


class SystemKnowledgeLoader:
    """
    Loads and provides access to system documentation for AI context.
    """
    
    # Priority documentation files
    PRIORITY_DOCS = [
        "SOTA_2026_MCP_VOICE_COMMANDS.md",
        "HOST_DEVICE_MCP_INTEGRATION.md",
        "BRIO_VOICE_VISION_INTEGRATION.md",
        "REDIS_QUANTUM_NEXUS_GLOBAL_CONFIG.md",
        "SOTA_2026_CHANGELOG.md",
        "KINGDOM_BRAIN_ORCHESTRATOR.md",
        "CHANGELOG_DEC_24_2025.md",
        "MARKDOWN_RUNTIME_ACCESSIBILITY_AUDIT.md",
        "MOCK_PLACEHOLDER_SCAN_DEC_2025.md",
        "ERROR_LOG_CORRELATION_DEC_2025.md",
        "FALLBACK_ELIMINATION_2025.md",
        "TYPE_FIXES_DEC_2025.md",
        "CODEBASE_INTROSPECTOR_SOTA_2026.md",
        # Tab dataflow documentation (Dec 2025 enumeration - ALL 10 TABS)
        "TAB_01_DASHBOARD_DATAFLOW.md",
        "TAB_03_MINING_DATAFLOW.md",
        "TAB_04_BLOCKCHAIN_DATAFLOW.md",
        "TAB_05_WALLET_DATAFLOW.md",
        "TAB_07_CODEGEN_DATAFLOW.md",
        "TAB_08_APIKEYS_DATAFLOW.md",
        "TAB_09_VR_DATAFLOW.md",
        "TAB_10_SETTINGS_DATAFLOW.md",
        "README_DATAFLOW_DOCS.md",
    ]
    
    def __init__(self, event_bus=None):
        """Initialize the knowledge loader."""
        self.event_bus = event_bus
        self._knowledge_cache: Dict[str, str] = {}
        self._loaded = False
        self._subscribed = False
        self._codebase_introspector: Optional['CodebaseIntrospector'] = None
        
        # Subscribe to knowledge requests
        if event_bus:
            event_bus.subscribe('ai.knowledge.request', self._handle_knowledge_request)
            event_bus.subscribe('ai.knowledge.list', self._handle_list_request)
            # SOTA 2026: Subscribe to source code access topics
            event_bus.subscribe('ai.source.request', self._handle_source_request)
            event_bus.subscribe('ai.source.search', self._handle_source_search)
            event_bus.subscribe('ai.source.edit', self._handle_source_edit)
            event_bus.subscribe('ai.context.full', self._handle_full_context_request)
            self._subscribed = True
        
        # Load priority docs on init
        self._load_priority_docs()
        
        # Initialize codebase introspector for source file access
        self._init_codebase_introspector()
        
        logger.info("✅ System Knowledge Loader initialized with full codebase access")
    
    def _load_priority_docs(self):
        """Load priority documentation files into cache."""
        for doc_name in self.PRIORITY_DOCS:
            try:
                doc_path = DOCS_PATH / doc_name
                if doc_path.exists():
                    with open(doc_path, 'r', encoding='utf-8') as f:
                        self._knowledge_cache[doc_name] = f.read()
                    logger.info(f"📚 Loaded documentation: {doc_name}")
            except Exception as e:
                logger.warning(f"Failed to load {doc_name}: {e}")
        
        self._loaded = True
    
    def get_command_reference(self) -> str:
        """Get the voice/MCP command reference for AI context."""
        doc = self._knowledge_cache.get("SOTA_2026_MCP_VOICE_COMMANDS.md", "")
        if doc:
            # Extract just the command reference section
            lines = doc.split('\n')
            in_commands = False
            command_lines = []
            for line in lines:
                if '## 📋 Complete Command Reference' in line:
                    in_commands = True
                elif in_commands and line.startswith('## ') and 'Command Reference' not in line:
                    break
                elif in_commands:
                    command_lines.append(line)
            return '\n'.join(command_lines) if command_lines else doc[:2000]
        return ""
    
    def get_quick_reference(self) -> str:
        """Get a concise command quick reference for chat context."""
        return """## SOTA 2026 Voice & Text Commands

### Device Control
- "scan devices" - Scan all host devices
- "list devices" - Show connected devices

### Software Automation
- "list windows" - List open windows
- "connect to [app]" - Set active software target
- "send keys [text]" - Send keystrokes
- "click at X, Y" - Click at coordinates

### Trading
- "buy/sell [amount] [symbol]" - Place order
- "show portfolio" - View holdings
- "check price [symbol]" - Get price

### Mining
- "start mining [coin]" - Start mining
- "stop mining" - Stop mining
- "show hashrate" - View stats

### Quantum Computing
- "show quantum status" - Check quantum provider status
- "detect quantum hardware" - Scan for available QPUs
- "start quantum mining" - Start quantum-enhanced mining
- "stop quantum mining" - Stop quantum mining
- "list quantum backends" - Show IBM Quantum backends
- "is quantum hardware available" - Check real QPU availability
- "show quantum capabilities" - Explain quantum features
- "submit quantum job to IBM" - Run circuit on IBM Quantum
- "submit quantum job to OpenQuantum" - Run on OpenQuantum

### Quantum Trading (Real-Time)
- "optimize portfolio" - QAOA portfolio optimization on real QPU
- "find arbitrage" - Quantum search for arbitrage opportunities
- "risk analysis" - Quantum-enhanced VaR calculation
- "enable quantum trading" - Enable quantum for all trading ops

### Wallet
- "show balance" - View balances
- "send [amount] [token] to [address]" - Send crypto

### Navigation
- "go to [tab]" - Navigate to tab
- "scroll up/down" - Scroll view
- "fullscreen" - Toggle fullscreen

### Codebase Access (SOTA 2026)
- "list files" - List indexed source files
- "codebase status" - Show index status
- "read file [path]" - View source file content
- "search [query]" - Search codebase for text
- "find function [name]" - Find function definitions
- "find class [name]" - Find class definitions
- "codebase context" - Get full repo context for AI
- "edit file [path]" - Modify source files directly

### Full System Control (SOTA 2026)
- "scan devices" - Scan all host system devices
- "list windows" - List all open windows on host
- "connect to [app]" - Set target application for automation
- "send keys [text]" - Send keystrokes to active window
- "click at X, Y" - Click at screen coordinates
- "run command [cmd]" - Execute shell command on host
- "list processes" - Show running processes
- "kill process [name]" - Terminate a process
- "screenshot" - Capture screen
- "record screen" - Start screen recording
- "control mouse" - Direct mouse control
- "system info" - Get host system information

### Hardware Control
- "list gpus" - Show available GPUs
- "gpu status" - GPU utilization and temps
- "list cameras" - Show available cameras
- "enable camera [id]" - Activate camera
- "list microphones" - Show audio input devices
- "enable microphone [id]" - Activate microphone
- "vr status" - VR headset status
- "connect vr" - Connect to VR device

### Documentation
- "docs" - List available documentation
- "doc [name]" - Show specific documentation
- "help" - Show this command reference

**Kingdom AI has FULL CONTROL of the host system and all components!**
Type any command naturally - the AI Command Router will execute it!
"""
    
    def get_full_documentation(self, doc_name: str) -> Optional[str]:
        """Get full documentation by name."""
        if doc_name in self._knowledge_cache:
            return self._knowledge_cache[doc_name]
        
        # Try to load it
        try:
            doc_path = DOCS_PATH / doc_name
            if doc_path.exists():
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self._knowledge_cache[doc_name] = content
                    return content
        except Exception as e:
            logger.warning(f"Failed to load {doc_name}: {e}")
        
        return None
    
    def list_available_docs(self) -> List[str]:
        """List all available documentation files."""
        docs = []
        if DOCS_PATH.exists():
            for f in DOCS_PATH.glob("*.md"):
                docs.append(f.name)
        return docs
    
    def _handle_knowledge_request(self, payload: Dict[str, Any]):
        """Handle EventBus request for knowledge."""
        doc_name = payload.get("doc_name", "")
        request_id = payload.get("request_id", "")
        
        if doc_name == "commands" or doc_name == "quick_reference":
            content = self.get_quick_reference()
        elif doc_name == "full_commands":
            content = self.get_command_reference()
        else:
            content = self.get_full_documentation(doc_name)
        
        if self.event_bus and content:
            self.event_bus.publish('ai.knowledge.response', {
                'request_id': request_id,
                'doc_name': doc_name,
                'content': content,
            })
    
    def _handle_list_request(self, payload: Dict[str, Any]):
        """Handle EventBus request for documentation list."""
        if self.event_bus:
            self.event_bus.publish('ai.knowledge.list.response', {
                'docs': self.list_available_docs(),
            })
    
    # ==================== SOTA 2026: CODEBASE INTROSPECTION ====================
    
    def _init_codebase_introspector(self):
        """Initialize the codebase introspector for source file access."""
        if not CODEBASE_INTROSPECTOR_AVAILABLE:
            logger.warning("CodebaseIntrospector not available")
            return
        
        try:
            self._codebase_introspector = get_codebase_introspector(self.event_bus)
            # CRITICAL FIX: Build index in BACKGROUND THREAD - don't block startup
            import threading
            def _build_index_background():
                try:
                    self._codebase_introspector.build_index()
                    logger.info("✅ CodebaseIntrospector index built (background)")
                except Exception as e:
                    logger.warning(f"Background index build failed: {e}")
            
            index_thread = threading.Thread(target=_build_index_background, daemon=True)
            index_thread.start()
            logger.info("✅ CodebaseIntrospector initialized - index building in background")
        except Exception as e:
            logger.warning(f"Failed to initialize CodebaseIntrospector: {e}")
    
    def get_source_file(self, file_path: str, line_start: int = None, 
                       line_end: int = None) -> Optional[Dict[str, Any]]:
        """Get source file content with optional line range."""
        if not self._codebase_introspector:
            return None
        return self._codebase_introspector.read_file(file_path, line_start, line_end)
    
    def search_codebase(self, query: str, file_pattern: str = "*.py") -> List[Dict[str, Any]]:
        """Search the codebase for text."""
        if not self._codebase_introspector:
            return []
        return self._codebase_introspector.search_text(query, file_pattern)
    
    def search_symbols(self, name: str, symbol_type: str = None) -> List[Dict[str, Any]]:
        """Search for code symbols (functions, classes, etc.)."""
        if not self._codebase_introspector:
            return []
        return self._codebase_introspector.search_symbol(name, symbol_type)
    
    def get_file_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all symbols in a file."""
        if not self._codebase_introspector:
            return []
        result = self._codebase_introspector.get_file_context(file_path)
        return result.get('symbols', []) if result.get('success') else []
    
    def get_full_codebase_context(self, focus_files: List[str] = None) -> str:
        """Get repository-level context for LLM consumption."""
        if not self._codebase_introspector:
            return "CodebaseIntrospector not available"
        return self._codebase_introspector.get_repository_context(focus_files)
    
    def apply_code_edit(self, file_path: str, old_text: str, new_text: str, create_backup: bool = False) -> Dict[str, Any]:
        """Apply a safe code edit with automatic backup."""
        if not self._codebase_introspector:
            return {'success': False, 'error': 'CodebaseIntrospector not available'}
        return self._codebase_introspector.apply_edit(file_path, old_text, new_text, create_backup=create_backup)
    
    def preview_code_edit(self, file_path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """Preview a code edit without applying it."""
        if not self._codebase_introspector:
            return {'success': False, 'error': 'CodebaseIntrospector not available'}
        return self._codebase_introspector.preview_edit(file_path, old_text, new_text)
    
    def list_source_files(self, pattern: str = "") -> List[Dict[str, Any]]:
        """List source files matching a pattern."""
        if not self._codebase_introspector:
            return []
        return self._codebase_introspector.search_files(pattern)
    
    def get_codebase_status(self) -> Dict[str, Any]:
        """Get codebase index status."""
        if not self._codebase_introspector:
            return {'available': False}
        status = self._codebase_introspector.get_index_status()
        status['available'] = True
        return status
    
    # ==================== EVENT HANDLERS FOR SOURCE ACCESS ====================
    
    def _handle_source_request(self, payload: Dict[str, Any]):
        """Handle EventBus request for source file."""
        file_path = payload.get('file_path', '')
        line_start = payload.get('line_start')
        line_end = payload.get('line_end')
        request_id = payload.get('request_id', '')
        
        result = self.get_source_file(file_path, line_start, line_end)
        if result:
            result['request_id'] = request_id
        else:
            result = {'success': False, 'error': 'Introspector not available', 'request_id': request_id}
        
        if self.event_bus:
            self.event_bus.publish('ai.source.response', result)
    
    def _handle_source_search(self, payload: Dict[str, Any]):
        """Handle EventBus request for codebase search."""
        query = payload.get('query', '')
        search_type = payload.get('search_type', 'text')  # 'text', 'symbol', 'file'
        file_pattern = payload.get('file_pattern', '*.py')
        symbol_type = payload.get('symbol_type')
        request_id = payload.get('request_id', '')
        
        if search_type == 'symbol':
            results = self.search_symbols(query, symbol_type)
        elif search_type == 'file':
            results = self.list_source_files(query)
        else:
            results = self.search_codebase(query, file_pattern)
        
        if self.event_bus:
            self.event_bus.publish('ai.source.search.response', {
                'success': True,
                'results': results,
                'query': query,
                'search_type': search_type,
                'request_id': request_id
            })
    
    def _handle_source_edit(self, payload: Dict[str, Any]):
        """Handle EventBus request for code editing."""
        file_path = payload.get('file_path', '')
        old_text = payload.get('old_text', '')
        new_text = payload.get('new_text', '')
        preview_only = payload.get('preview_only', False)
        create_backup = payload.get('create_backup', False)
        request_id = payload.get('request_id', '')
        
        if preview_only:
            result = self.preview_code_edit(file_path, old_text, new_text)
        else:
            result = self.apply_code_edit(file_path, old_text, new_text, create_backup=create_backup)
        
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('ai.source.edit.response', result)
    
    def _handle_full_context_request(self, payload: Dict[str, Any]):
        """Handle EventBus request for full codebase context."""
        focus_files = payload.get('focus_files', [])
        request_id = payload.get('request_id', '')
        
        context = self.get_full_codebase_context(focus_files)
        
        if self.event_bus:
            self.event_bus.publish('ai.context.full.response', {
                'success': True,
                'context': context,
                'request_id': request_id
            })


# Singleton instance
_knowledge_loader_instance: Optional[SystemKnowledgeLoader] = None


def get_knowledge_loader(event_bus=None) -> SystemKnowledgeLoader:
    """Get or create the singleton SystemKnowledgeLoader instance."""
    global _knowledge_loader_instance
    if _knowledge_loader_instance is None:
        _knowledge_loader_instance = SystemKnowledgeLoader(event_bus)
    elif event_bus is not None and getattr(_knowledge_loader_instance, 'event_bus', None) is None:
        try:
            _knowledge_loader_instance.event_bus = event_bus
        except Exception:
            pass
        try:
            event_bus.subscribe('ai.knowledge.request', _knowledge_loader_instance._handle_knowledge_request)
            event_bus.subscribe('ai.knowledge.list', _knowledge_loader_instance._handle_list_request)
            setattr(_knowledge_loader_instance, '_subscribed', True)
        except Exception:
            pass
    return _knowledge_loader_instance


def get_command_reference() -> str:
    """Convenience function to get command reference."""
    loader = get_knowledge_loader()
    return loader.get_quick_reference()
