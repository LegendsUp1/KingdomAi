#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Code Generator Tab for Kingdom AI

PyQt6 implementation of the Code Generator tab with unified brain integration,
WSL-aware Ollama URL, Redis Quantum Nexus, and full event bus support.
"""

import os
import sys
import re
import json
import logging
import asyncio
import uuid
import time
import subprocess
import importlib.util
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union

# SOTA 2026: Consumer/Creator mode + Code Sandbox for safe execution
_KINGDOM_APP_MODE = os.environ.get("KINGDOM_APP_MODE", "consumer").lower()
_IS_CONSUMER = _KINGDOM_APP_MODE != "creator"

try:
    from core.code_sandbox import CodeSandbox, ASTMalwareScanner
    HAS_CODE_SANDBOX = True
except ImportError:
    HAS_CODE_SANDBOX = False

# PyQt6 imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTextEdit, QComboBox, QMessageBox, QSplitter, QGroupBox, QStatusBar,
    QApplication, QHeaderView, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QProgressBar, QToolBar, QSizePolicy, QPlainTextEdit,
    QFileDialog, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, QSize, QObject, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtGui import QIcon, QColor, QFont, QPixmap, QPainter, QTextCharFormat, QSyntaxHighlighter, QAction

# Application imports
from core.redis_quantum_nexus import RedisQuantumNexus
from core.ollama_config import get_ollama_base_url  # WSL-aware Ollama URL
from gui.qt_styles import get_style_sheet
from gui.qt_utils import get_icon, async_slot, Worker, WorkerSignals

logger = logging.getLogger("KingdomAI.CodeGeneratorQt")

# Syntax highlighting support
try:
    from PyQt6.Qsci import QsciScintilla, QsciLexerPython, QsciLexerCPP, QsciLexerJava, QsciLexerJavaScript
    HAS_SCINTILLA = True
except ImportError:
    HAS_SCINTILLA = False
    logger.warning("QsciScintilla not available, using plain text editor")


class CodeGeneratorQt(QWidget):
    """
    Code Generator Tab for Kingdom AI
    
    PyQt6 implementation with unified brain integration, WSL-aware Ollama URL,
    Redis Quantum Nexus, and full event bus support.
    """
    
    # Signals for thread-safe UI updates
    code_response_signal = pyqtSignal(dict)
    execution_result_signal = pyqtSignal(dict)
    
    def __init__(self, parent=None, event_bus=None, config=None):
        """Initialize the Code Generator Tab
        
        Args:
            parent: Parent widget
            event_bus: Event bus for inter-component communication
            config: Configuration dictionary
        """
        super().__init__(parent)
        self.setObjectName("CodeGeneratorQt")
        
        # Initialize properties
        self.event_bus = event_bus
        self.config = config or {}
        self.redis_nexus = None
        self.is_generating = False
        self.is_executing = False
        
        # SOTA 2026: Consumer sandboxed execution
        self.is_consumer = _IS_CONSUMER
        self._sandbox = None
        if self.is_consumer and HAS_CODE_SANDBOX:
            self._sandbox = CodeSandbox(user_id="consumer_default", event_bus=event_bus)
            logger.info("🛡️ Code Generator: Consumer mode — sandboxed execution (AST scan + restricted builtins)")
        self.current_language = "python"
        self.last_generated_code = ""
        self.current_request_id = None
        
        # Pending requests for unified brain responses
        self._pending_requests: Dict[str, Dict[str, Any]] = {}
        
        # WSL-aware Ollama URL (CRITICAL FIX)
        self.ollama_base_url = get_ollama_base_url()
        logger.info(f"✅ Code Generator using WSL-aware Ollama URL: {self.ollama_base_url}")
        
        # Model fallback chain for Ollama
        self.ollama_models = [
            "codellama:latest",
            "codellama",
            "llama3:latest",
            "llama3.2:latest",
            "llama3",
            "llama3.2",
            "deepseek-coder:latest",
            "deepseek-coder"
        ]
        
        # Initialize UI
        self._setup_ui()
        
        # Initialize components
        self._initialize_components()
        
        # Connect signals for thread-safe updates
        self.code_response_signal.connect(self._process_code_response_in_main_thread)
        self.execution_result_signal.connect(self._process_execution_result_in_main_thread)
        
    def _setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Create toolbar
        self._create_toolbar(main_layout)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Code editor
        self._create_code_editor_panel(splitter)
        
        # Right panel: Output and controls
        self._create_output_panel(splitter)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        main_layout.addWidget(self.status_bar)
        
        # Apply styles
        self.setStyleSheet(get_style_sheet())
        
    def _create_toolbar(self, parent_layout):
        """Create the toolbar with controls."""
        toolbar = QToolBar("Code Generator Toolbar")
        
        # Language selection
        lang_label = QLabel("Language:")
        toolbar.addWidget(lang_label)
        
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "python", "javascript", "typescript", "java", "cpp", "c", "rust",
            "go", "ruby", "php", "swift", "kotlin", "dart", "html", "css"
        ])
        self.language_combo.setCurrentText("python")
        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        toolbar.addWidget(self.language_combo)
        
        toolbar.addSeparator()
        
        # Generate button
        self.generate_button = QPushButton("🚀 Generate Code")
        self.generate_button.clicked.connect(self._on_generate_code)
        toolbar.addWidget(self.generate_button)
        
        # Execute button
        self.execute_button = QPushButton("▶ Execute")
        self.execute_button.clicked.connect(self._on_execute_code)
        self.execute_button.setEnabled(False)
        toolbar.addWidget(self.execute_button)
        
        # Save button
        save_button = QPushButton("💾 Save")
        save_button.clicked.connect(self._on_save_code)
        toolbar.addWidget(save_button)
        
        # Load button
        load_button = QPushButton("📂 Load")
        load_button.clicked.connect(self._on_load_code)
        toolbar.addWidget(load_button)
        
        # Browse Workspace button - access Kingdom AI codebase
        browse_button = QPushButton("🗂 Browse Workspace")
        browse_button.clicked.connect(self._on_browse_workspace)
        toolbar.addWidget(browse_button)
        
        toolbar.addSeparator()
        
        # Hot Reload button - apply code changes to running system
        self.hot_reload_button = QPushButton("🔄 Hot Reload")
        self.hot_reload_button.clicked.connect(self.apply_hot_reload)
        self.hot_reload_button.setToolTip("Apply code changes to running Kingdom AI system")
        toolbar.addWidget(self.hot_reload_button)
        
        # Self-Diagnostics button
        diagnostics_button = QPushButton("🔍 Diagnostics")
        diagnostics_button.clicked.connect(self._run_self_diagnostics)
        diagnostics_button.setToolTip("Run system self-diagnostics")
        toolbar.addWidget(diagnostics_button)
        
        toolbar.addSeparator()
        
        # Clear button
        clear_button = QPushButton("🗑 Clear")
        clear_button.clicked.connect(self._on_clear)
        toolbar.addWidget(clear_button)
        
        # Copy button
        copy_button = QPushButton("📋 Copy")
        copy_button.clicked.connect(self._on_copy_code)
        toolbar.addWidget(copy_button)
        
        parent_layout.addWidget(toolbar)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        parent_layout.addWidget(self.progress_bar)
        
    def _create_code_editor_panel(self, parent_splitter):
        """Create the code editor panel."""
        editor_group = QGroupBox("Code Editor")
        editor_layout = QVBoxLayout(editor_group)
        
        # Prompt input
        prompt_label = QLabel("Prompt:")
        editor_layout.addWidget(prompt_label)
        
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter code generation prompt...")
        self.prompt_input.returnPressed.connect(self._on_generate_code)
        editor_layout.addWidget(self.prompt_input)
        
        # Code editor
        if HAS_SCINTILLA:
            self.code_editor = QsciScintilla()
            # Configure lexer based on language
            self._setup_syntax_highlighter()
        else:
            self.code_editor = QPlainTextEdit()
            self.code_editor.setFont(QFont("Consolas", 10))
        
        self.code_editor.setReadOnly(False)
        editor_layout.addWidget(self.code_editor)
        
        parent_splitter.addWidget(editor_group)
        
    def _create_output_panel(self, parent_splitter):
        """Create the output panel."""
        output_group = QGroupBox("Output & Logs")
        output_layout = QVBoxLayout(output_group)
        
        # Output text area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 9))
        output_layout.addWidget(self.output_text)
        
        parent_splitter.addWidget(output_group)
        
    def _setup_syntax_highlighter(self):
        """Set up syntax highlighting for code editor."""
        if not HAS_SCINTILLA:
            return
            
        lang_map = {
            "python": QsciLexerPython,
            "cpp": QsciLexerCPP,
            "c": QsciLexerCPP,
            "java": QsciLexerJava,
            "javascript": QsciLexerJavaScript,
            "typescript": QsciLexerJavaScript,
        }
        
        lexer_class = lang_map.get(self.current_language)
        if lexer_class:
            lexer = lexer_class(self.code_editor)
            self.code_editor.setLexer(lexer)  # type: ignore[attr-defined]
            
    def _initialize_components(self):
        """Initialize Redis and event bus subscriptions."""
        # SOTA 2026: Defer Redis init until event loop is ready (prevents "no running event loop")
        # Schedule Redis initialization after GUI is fully loaded
        QTimer.singleShot(2000, self._init_redis_deferred)
            
        # Subscribe to event bus events
        if self.event_bus:
            QTimer.singleShot(1000, self._subscribe_to_backend_events)
    
    def _init_redis_deferred(self):
        """Initialize Redis after event loop is ready."""
        try:
            self.redis_nexus = RedisQuantumNexus()
            # Check connection - try multiple attribute names
            is_connected = (
                getattr(self.redis_nexus, 'is_connected', False) or
                getattr(self.redis_nexus, '_connected', False) or
                getattr(self.redis_nexus, 'connected', False)
            )
            if is_connected:
                logger.info("✅ Code Generator connected to Redis Quantum Nexus")
            else:
                # SOTA 2026 FIX: Downgrade to debug - Redis connection is optional
                # and will retry automatically when needed
                logger.debug("ℹ️ Code Generator: Redis Quantum Nexus connection pending")
        except Exception as e:
            logger.debug(f"ℹ️ Code Generator Redis initialization deferred: {e}")
            self.redis_nexus = None
            
    def _subscribe_to_backend_events(self):
        """Subscribe to backend events."""
        if not self.event_bus:
            return
            
        try:
            # Subscribe to unified brain responses (CRITICAL FIX)
            self.event_bus.subscribe("ai.response.unified", self._handle_brain_code_response)
            self.event_bus.subscribe("brain.response", self._handle_brain_code_response)  # Fallback
            self.event_bus.subscribe("codegen.code_generated", self._handle_code_generated)
            self.event_bus.subscribe("codegen.execution_result", self._handle_execution_result)
            
            logger.info("✅ Code Generator subscribed to unified brain responses")
        except Exception as e:
            logger.error(f"❌ Code Generator subscription error: {e}")
            
    def _on_language_changed(self, language: str):
        """Handle language selection change."""
        self.current_language = language
        self._setup_syntax_highlighter()
        logger.info(f"Language changed to: {language}")
        
    def _on_generate_code(self):
        """Handle generate code button click."""
        prompt = self.prompt_input.text().strip()
        if not prompt:
            QMessageBox.warning(self, "Warning", "Please enter a prompt")
            return
            
        if self.is_generating:
            QMessageBox.information(self, "Info", "Code generation in progress...")
            return
            
        # Start generation
        self.is_generating = True
        self.generate_button.setEnabled(False)
        self.generate_button.setText("⏳ Generating...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Generating code...")
        
        # Use unified brain system (CRITICAL FIX)
        # Properly handle event loop for asyncio in Qt context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._async_generate_code(prompt))
            else:
                # No running loop - run synchronously via event loop
                loop.run_until_complete(self._async_generate_code(prompt))
        except RuntimeError:
            # No event loop exists - create one and run
            asyncio.run(self._async_generate_code(prompt))
        
    async def _async_generate_code(self, prompt: str):
        """Generate code using unified Ollama brain system."""
        try:
            # Generate request ID
            request_id = f"codegen_{int(time.time() * 1000)}"
            self.current_request_id = request_id
            
            # Build code generation prompt
            system_prompt = (
                f"You are an expert {self.current_language} developer. "
                "Generate clean, production-ready code with proper error handling and comments. "
                "Provide ONLY the code, no explanations or markdown formatting."
            )
            
            # Publish ai.request to unified brain system (CRITICAL FIX)
            if self.event_bus:
                self.event_bus.publish("ai.request", {
                    "request_id": request_id,
                    "prompt": f"Generate {self.current_language} code for: {prompt}",
                    "domain": "code",
                    "source_tab": "code_generator",
                    "system_prompt": system_prompt,
                    "speak": False,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Store request for response matching
                self._pending_requests[request_id] = {
                    "prompt": prompt,
                    "language": self.current_language,
                    "timestamp": time.time()
                }
                
                logger.info(f"✅ Published ai.request for code generation (ID: {request_id})")
                
                # Update progress
                self.progress_bar.setValue(50)
                
                # Set timeout for response (30 seconds)
                QTimer.singleShot(30000, lambda: self._handle_generation_timeout(request_id))
                
            else:
                # Fallback: Direct Ollama call with WSL-aware URL
                logger.warning("⚠️ Event bus not available, using direct Ollama fallback")
                code = await self._generate_code_with_ollama_fallback(prompt)
                self.code_response_signal.emit({
                    "code": code,
                    "language": self.current_language,
                    "message": "Code generated using Ollama fallback"
                })
                
        except Exception as e:
            logger.error(f"❌ Code generation failed: {e}", exc_info=True)
            self._handle_generation_error(str(e))
            
    async def _generate_code_with_ollama_fallback(self, prompt: str) -> str:
        """Fallback: Generate code using Ollama directly with WSL-aware URL."""
        try:
            import aiohttp
            
            # Use WSL-aware Ollama URL (CRITICAL FIX)
            ollama_url = f"{self.ollama_base_url}/api/generate"
            
            # Try models in fallback chain
            for model in self.ollama_models:
                try:
                    async with aiohttp.ClientSession() as session:
                        payload = {
                            "model": model,
                            "prompt": f"Generate {self.current_language} code for: {prompt}\n\nProvide ONLY the code, no explanations:",
                            "stream": False
                        }
                        
                        async with session.post(
                            ollama_url,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                generated_code = result.get('response', '')
                                
                                # Clean up the response
                                if generated_code:
                                    # Remove markdown code blocks
                                    generated_code = re.sub(r'```[\w]*\n', '', generated_code)
                                    generated_code = re.sub(r'```$', '', generated_code)
                                    generated_code = re.sub(r'^```', '', generated_code)
                                    return generated_code.strip()
                                    
                            elif response.status == 404:
                                logger.warning(f"Model {model} not found, trying next...")
                                continue
                            else:
                                logger.warning(f"Ollama API returned status {response.status} for {model}")
                                continue
                                
                except Exception as e:
                    logger.warning(f"Error with model {model}: {e}, trying next...")
                    continue
                    
            raise RuntimeError("All Ollama models failed")
            
        except Exception as e:
            logger.error(f"Ollama fallback generation failed: {e}")
            # Return template code as last resort
            return self._generate_template_code(prompt)
            
    def _generate_template_code(self, prompt: str) -> str:
        """Generate template code as last resort."""
        lang_templates = {
            "python": f"# {prompt}\n\ndef main():\n    pass\n\nif __name__ == '__main__':\n    main()\n",
            "javascript": f"// {prompt}\n\nfunction main() {{\n    // TODO: Implement\n}}\n\nmain();\n",
            "java": f"// {prompt}\n\npublic class Main {{\n    public static void main(String[] args) {{\n        // TODO: Implement\n    }}\n}}\n",
        }
        return lang_templates.get(self.current_language, f"# {prompt}\n\n# TODO: Implement\n")
        
    def _handle_brain_code_response(self, data: Dict[str, Any]) -> None:
        """Handle unified brain response for code generation."""
        try:
            if not isinstance(data, dict):
                return
                
            request_id = data.get("request_id", "")
            response_text = data.get("response") or data.get("message") or ""
            
            # Check if this is our request
            if request_id not in self._pending_requests:
                return  # Not our request
                
            pending = self._pending_requests.pop(request_id)
            
            # Extract code from response
            code = self._extract_code_from_response(response_text)
            
            # Emit signal for thread-safe UI update
            self.code_response_signal.emit({
                "code": code,
                "language": pending.get("language", self.current_language),
                "message": "Code generated using unified brain",
                "request_id": request_id
            })
            
            logger.info(f"✅ Code generated from unified brain (ID: {request_id})")
            
        except Exception as e:
            logger.error(f"❌ Error handling brain response: {e}", exc_info=True)
            self._handle_generation_error(str(e))
            
    def _handle_code_generated(self, data: Dict[str, Any]) -> None:
        """Handle code generation event from backend."""
        try:
            code = data.get("code", "")
            language = data.get("language", self.current_language)
            message = data.get("message", "Code generated")
            
            self.code_response_signal.emit({
                "code": code,
                "language": language,
                "message": message
            })
        except Exception as e:
            logger.error(f"❌ Error handling code generated event: {e}", exc_info=True)
            
    def _extract_code_from_response(self, response_text: str) -> str:
        """Extract code from AI response, removing markdown and explanations."""
        code = response_text.strip()
        
        # Remove markdown code blocks
        code = re.sub(r'```[\w]*\n', '', code)
        code = re.sub(r'```$', '', code)
        code = re.sub(r'^```', '', code)
        
        # Remove explanations (lines starting with #, //, or /*)
        lines = code.split('\n')
        code_lines = []
        in_comment_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('/*'):
                in_comment_block = True
            if in_comment_block and '*/' in stripped:
                in_comment_block = False
                continue
            if in_comment_block:
                continue
            if stripped.startswith('#') or stripped.startswith('//'):
                continue
            code_lines.append(line)
            
        code = '\n'.join(code_lines).strip()
        return code
        
    def _process_code_response_in_main_thread(self, data: Dict[str, Any]) -> None:
        """Process code generation response in Qt main thread."""
        try:
            code = data.get("code", "")
            language = data.get("language", self.current_language)
            message = data.get("message", "Code generated")
            
            # Display generated code in editor
            if code and hasattr(self, 'code_editor'):
                if HAS_SCINTILLA:
                    self.code_editor.setText(code)  # type: ignore[attr-defined]
                else:
                    self.code_editor.setPlainText(code)
                    
            # Update status
            self.status_label.setText(message)
            self.output_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
            
            # Reset generating state
            self.is_generating = False
            self.generate_button.setEnabled(True)
            self.generate_button.setText("🚀 Generate Code")
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
            
            # Enable execute button
            self.execute_button.setEnabled(True)
            self.last_generated_code = code
            
        except Exception as e:
            logger.error(f"Error processing code response: {e}", exc_info=True)
            self._handle_generation_error(str(e))
            
    def _handle_generation_timeout(self, request_id: str):
        """Handle generation timeout."""
        if request_id in self._pending_requests:
            logger.warning(f"Code generation timeout for request {request_id}")
            self._pending_requests.pop(request_id)
            self._handle_generation_error("Generation timeout (30s)")
            
    def _handle_generation_error(self, error_msg: str):
        """Handle generation error."""
        self.is_generating = False
        self.generate_button.setEnabled(True)
        self.generate_button.setText("🚀 Generate Code")
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ Error: {error_msg}")
        self.output_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {error_msg}\n")
        QMessageBox.warning(self, "Generation Error", error_msg)
        
    def _on_execute_code(self):
        """Handle execute code button click."""
        if not hasattr(self, 'code_editor'):
            return
            
        # Get code from editor
        if HAS_SCINTILLA:
            code = self.code_editor.toPlainText()
        else:
            code = self.code_editor.toPlainText()
            
        if not code.strip():
            QMessageBox.warning(self, "Warning", "No code to execute")
            return
            
        if self.is_executing:
            QMessageBox.information(self, "Info", "Code execution in progress...")
            return
            
        # Only execute Python code for safety
        if self.current_language != "python":
            QMessageBox.information(
                self, "Info",
                f"Code execution is only supported for Python. Current language: {self.current_language}"
            )
            return
            
        # Start execution
        self.is_executing = True
        self.execute_button.setEnabled(False)
        self.execute_button.setText("⏳ Executing...")
        self.status_label.setText("Executing code...")
        self.output_text.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] === Execution Started ===\n")
        
        # Execute in background thread with proper event loop handling
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._async_execute_code(code))
            else:
                loop.run_until_complete(self._async_execute_code(code))
        except RuntimeError:
            asyncio.run(self._async_execute_code(code))
        
    async def _async_execute_code(self, code: str):
        """Execute code asynchronously.
        
        SOTA 2026: Consumer code runs through CodeSandbox (AST scan + restricted builtins).
        Creator code runs via subprocess with full system access.
        """
        # SOTA 2026: Consumer mode — sandboxed execution
        if self._sandbox:
            try:
                sandbox_result = self._sandbox.execute(code)
                
                if sandbox_result.was_blocked:
                    self.execution_result_signal.emit({
                        "stdout": "",
                        "stderr": f"🛡️ SECURITY: {sandbox_result.block_reason}",
                        "returncode": -1,
                        "success": False
                    })
                    # Alert creator about the attempt
                    if self.event_bus:
                        self.event_bus.publish("security.code_blocked", {
                            "reason": sandbox_result.block_reason,
                            "threats": [t.to_dict() for t in sandbox_result.threats_found],
                            "timestamp": datetime.now().isoformat(),
                        })
                    return
                
                self.execution_result_signal.emit({
                    "stdout": sandbox_result.output,
                    "stderr": sandbox_result.error,
                    "returncode": 0 if sandbox_result.success else -1,
                    "success": sandbox_result.success,
                    "execution_time_ms": sandbox_result.execution_time_ms,
                })
                return
                
            except Exception as e:
                self.execution_result_signal.emit({
                    "stdout": "",
                    "stderr": f"Sandbox error: {e}",
                    "returncode": -1,
                    "success": False
                })
                return
        
        # Creator mode — full subprocess execution (unrestricted)
        try:
            # Create a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
                
            try:
                # Execute code
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Emit result signal
                self.execution_result_signal.emit({
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "success": result.returncode == 0
                })
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            self.execution_result_signal.emit({
                "stdout": "",
                "stderr": "Execution timeout (30s)",
                "returncode": -1,
                "success": False
            })
        except Exception as e:
            self.execution_result_signal.emit({
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "success": False
            })
            
    def _process_execution_result_in_main_thread(self, data: Dict[str, Any]) -> None:
        """Process execution result in Qt main thread."""
        try:
            stdout = data.get("stdout", "")
            stderr = data.get("stderr", "")
            returncode = data.get("returncode", -1)
            success = data.get("success", False)
            
            # Display output
            if stdout:
                self.output_text.append(stdout)
            if stderr:
                self.output_text.append(f"ERROR: {stderr}")
                
            # Update status
            if success:
                self.status_label.setText("✅ Execution completed")
            else:
                self.status_label.setText(f"❌ Execution failed (code: {returncode})")
                
            self.output_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] === Execution Finished ===\n")
            
            # Reset executing state
            self.is_executing = False
            self.execute_button.setEnabled(True)
            self.execute_button.setText("▶ Execute")
            
        except Exception as e:
            logger.error(f"Error processing execution result: {e}", exc_info=True)
            self.is_executing = False
            self.execute_button.setEnabled(True)
            self.execute_button.setText("▶ Execute")
            
    def _handle_execution_result(self, data: Dict[str, Any]) -> None:
        """Handle execution result event from backend."""
        self.execution_result_signal.emit(data)
        
    def _on_save_code(self):
        """Handle save code button click."""
        if not hasattr(self, 'code_editor'):
            return
            
        # Get code from editor
        if HAS_SCINTILLA:
            code = self.code_editor.text()  # type: ignore[attr-defined]
        else:
            code = self.code_editor.toPlainText()
            
        if not code.strip():
            QMessageBox.warning(self, "Warning", "No code to save")
            return
            
        # Get file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Code",
            "",
            f"{self.current_language.upper()} Files (*.{self._get_file_extension()});;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                self.status_label.setText(f"✅ Code saved to {file_path}")
                QMessageBox.information(self, "Success", f"Code saved to {file_path}")
            except Exception as e:
                logger.error(f"Error saving code: {e}")
                QMessageBox.critical(self, "Error", f"Failed to save code: {e}")
                
    def _on_load_code(self):
        """Handle load code button click."""
        # Get file path
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Code",
            "",
            f"{self.current_language.upper()} Files (*.{self._get_file_extension()});;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                    
                # Detect language from extension
                ext = os.path.splitext(file_path)[1]
                lang_map = {
                    ".py": "python",
                    ".js": "javascript",
                    ".ts": "typescript",
                    ".java": "java",
                    ".cpp": "cpp",
                    ".c": "c",
                    ".rs": "rust",
                    ".go": "go",
                    ".rb": "ruby",
                    ".php": "php",
                    ".swift": "swift",
                    ".kt": "kotlin",
                    ".dart": "dart",
                    ".html": "html",
                    ".css": "css"
                }
                detected_lang = lang_map.get(ext, "python")
                if detected_lang != self.current_language:
                    self.language_combo.setCurrentText(detected_lang)
                    
                # Set code in editor
                if hasattr(self, 'code_editor'):
                    if HAS_SCINTILLA:
                        self.code_editor.setText(code)  # type: ignore[attr-defined]
                    else:
                        self.code_editor.setPlainText(code)
                        
                self.status_label.setText(f"✅ Code loaded from {file_path}")
            except Exception as e:
                logger.error(f"Error loading code: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load code: {e}")
    
    def _on_browse_workspace(self):
        """Browse Kingdom AI workspace/codebase files."""
        # Get workspace root (parent of gui folder)
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Open file dialog starting at workspace root
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Browse Kingdom AI Workspace",
            workspace_root,
            "Python Files (*.py);;JavaScript Files (*.js);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                # Detect language from extension
                ext = os.path.splitext(file_path)[1].lower()
                lang_map = {
                    ".py": "python", ".js": "javascript", ".ts": "typescript",
                    ".java": "java", ".cpp": "cpp", ".c": "c", ".rs": "rust",
                    ".go": "go", ".rb": "ruby", ".php": "php", ".swift": "swift",
                    ".kt": "kotlin", ".dart": "dart", ".html": "html", ".css": "css"
                }
                detected_lang = lang_map.get(ext, "python")
                if detected_lang != self.current_language:
                    self.language_combo.setCurrentText(detected_lang)
                
                # Set code in editor
                if hasattr(self, 'code_editor'):
                    if HAS_SCINTILLA:
                        self.code_editor.setText(code)  # type: ignore[attr-defined]
                    else:
                        self.code_editor.setPlainText(code)
                
                # Store file path for potential save-back
                self._current_file_path = file_path
                self.status_label.setText(f"✅ Loaded: {os.path.basename(file_path)}")
                self.output_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded workspace file: {file_path}\n")
                
                # Enable execute if Python
                if detected_lang == "python":
                    self.execute_button.setEnabled(True)
                    
            except Exception as e:
                logger.error(f"Error browsing workspace: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
                
    def _get_file_extension(self) -> str:
        """Get file extension for current language."""
        ext_map = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "rust": "rs",
            "go": "go",
            "ruby": "rb",
            "php": "php",
            "swift": "swift",
            "kotlin": "kt",
            "dart": "dart",
            "html": "html",
            "css": "css"
        }
        return ext_map.get(self.current_language, "txt")
        
    def _on_clear(self):
        """Handle clear button click."""
        if hasattr(self, 'code_editor'):
            if HAS_SCINTILLA:
                self.code_editor.setText("")  # type: ignore[attr-defined]
            else:
                self.code_editor.setPlainText("")
        if hasattr(self, 'output_text'):
            self.output_text.clear()
        if hasattr(self, 'prompt_input'):
            self.prompt_input.clear()
        self.status_label.setText("Cleared")
        
    def _on_copy_code(self):
        """Handle copy button click."""
        if not hasattr(self, 'code_editor'):
            return
            
        # Get code from editor
        if HAS_SCINTILLA:
            code = self.code_editor.text()  # type: ignore[attr-defined]
        else:
            code = self.code_editor.toPlainText()
            
        if code:
            clipboard = QApplication.clipboard()
            clipboard.setText(code)
            self.status_label.setText("✅ Code copied to clipboard")
        else:
            QMessageBox.warning(self, "Warning", "No code to copy")
            
    def update_status(self, message: str, status_type: str = "info"):
        """Update status label with message and type."""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
        if hasattr(self, 'output_text'):
            self.output_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
    
    def apply_hot_reload(self):
        """Apply code changes to running Kingdom AI system (hot reload).

        SOTA 2026: Uses SystemUpdater.hot_reload_module for safe reload with:
        - AST syntax validation BEFORE writing
        - Automatic file backup
        - Full module-name resolution (handles subpackages like core.code_generator)
        - Dependent-module cascade reload
        - Automatic rollback on failure
        """
        try:
            # Get code from editor
            if HAS_SCINTILLA:
                code = self.code_editor.text()  # type: ignore[attr-defined]
            else:
                code = self.code_editor.toPlainText()

            if not code.strip():
                QMessageBox.warning(self, "Warning", "No code to reload")
                return

            # Check if we have a file path to reload
            file_path = getattr(self, '_current_file_path', None)

            if not file_path:
                workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Select Target File for Hot Reload",
                    workspace_root,
                    "Python Files (*.py);;All Files (*.*)"
                )
                if not file_path:
                    return

            # Pre-validate syntax BEFORE asking for confirmation
            import ast
            try:
                ast.parse(code, filename=file_path)
            except SyntaxError as syn_err:
                QMessageBox.critical(
                    self, "Syntax Error",
                    f"Cannot hot-reload — syntax error at line {syn_err.lineno}:\n{syn_err.msg}"
                )
                return

            reply = QMessageBox.question(
                self,
                "Confirm Hot Reload",
                f"This will update:\n{file_path}\n\n"
                "The module will be reloaded in the running system.\n"
                "A backup will be created automatically.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Use SystemUpdater's safe hot-reload engine
            try:
                from core.system_updater import get_system_updater
                updater = get_system_updater(self.event_bus)
                result = updater.hot_reload_module(file_path, code)
            except ImportError:
                # Fallback: direct reload if system_updater not available
                result = self._fallback_hot_reload(file_path, code)

            ts = datetime.now().strftime('%H:%M:%S')
            if result.get("success"):
                mod_name = result.get("module", os.path.basename(file_path))
                self.output_text.append(f"[{ts}] Module '{mod_name}' hot-reloaded successfully\n")
                if result.get("backup_path"):
                    self.output_text.append(f"[{ts}] Backup: {result['backup_path']}\n")
                logger.info(f"Hot reload successful: {mod_name}")
                self.status_label.setText(f"Hot reload applied: {os.path.basename(file_path)}")
            else:
                msg = result.get("message", "Unknown error")
                rolled = " (rolled back)" if result.get("rolled_back") else ""
                self.output_text.append(f"[{ts}] Hot reload failed{rolled}: {msg}\n")
                logger.warning(f"Hot reload failed: {msg}")
                self.status_label.setText(f"Hot reload failed{rolled}")

            if self.event_bus:
                self.event_bus.publish("codegen.hot_reload", {
                    "file": file_path,
                    "success": result.get("success", False),
                    "module": result.get("module", ""),
                    "timestamp": datetime.now().isoformat()
                })

            self._current_file_path = file_path

        except Exception as e:
            logger.error(f"Hot reload failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Hot Reload Error", f"Failed to apply hot reload:\n{e}")

    def _fallback_hot_reload(self, file_path: str, code: str) -> Dict[str, Any]:
        """Fallback hot-reload when SystemUpdater is unavailable."""
        import shutil
        import importlib as _imp

        backup_path = f"{file_path}.bak.{int(time.time())}"
        if os.path.exists(file_path):
            shutil.copy2(file_path, backup_path)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        # Resolve full module name by checking sys.modules
        module_name = None
        abs_path = os.path.abspath(file_path)
        for name, mod in sys.modules.items():
            if mod and getattr(mod, '__file__', None):
                if mod.__file__ and os.path.abspath(mod.__file__) == abs_path:
                    module_name = name
                    break

        if not module_name:
            module_name = os.path.splitext(os.path.basename(file_path))[0]

        if module_name in sys.modules:
            try:
                _imp.reload(sys.modules[module_name])
                return {"success": True, "module": module_name, "message": "Reloaded", "backup_path": backup_path}
            except Exception as e:
                shutil.copy2(backup_path, file_path)
                try:
                    _imp.reload(sys.modules[module_name])
                except Exception:
                    pass
                return {"success": False, "module": module_name, "message": str(e), "rolled_back": True, "backup_path": backup_path}

        return {"success": True, "module": module_name, "message": "File saved (not yet imported)", "backup_path": backup_path}
    
    def _run_self_diagnostics(self):
        """Run self-diagnostics on Kingdom AI system components."""
        try:
            self.output_text.clear()
            self.output_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Running Kingdom AI Self-Diagnostics...\n")
            self.output_text.append("=" * 60 + "\n")
            
            diagnostics = []
            
            # 1. Check Event Bus
            if self.event_bus:
                diagnostics.append(("Event Bus", "✅ Connected", "green"))
            else:
                diagnostics.append(("Event Bus", "❌ Not Available", "red"))
            
            # 2. Check Redis Quantum Nexus
            # Note: is_connected is an attribute, not a method
            redis_connected = False
            if self.redis_nexus:
                redis_connected = getattr(self.redis_nexus, 'is_connected', False)
            if redis_connected:
                diagnostics.append(("Redis Quantum Nexus", "✅ Connected", "green"))
            else:
                diagnostics.append(("Redis Quantum Nexus", "⚠️ Not Connected", "orange"))
            
            # 3. Check Ollama URL
            # SOTA 2026 FIX: Run blocking HTTP call in background thread to prevent GUI freeze (was 5s)
            try:
                import requests
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(requests.get, f"{self.ollama_base_url}/api/tags", timeout=3)
                    try:
                        resp = future.result(timeout=4)
                        if resp.status_code == 200:
                            models = resp.json().get('models', [])
                            model_names = [m.get('name', 'unknown') for m in models[:5]]
                            diagnostics.append(("Ollama API", f"✅ Connected ({len(models)} models)", "green"))
                            diagnostics.append(("Available Models", f"  {', '.join(model_names)}", "cyan"))
                        else:
                            diagnostics.append(("Ollama API", f"⚠️ Status {resp.status_code}", "orange"))
                    except concurrent.futures.TimeoutError:
                        diagnostics.append(("Ollama API", "⚠️ Timeout (server slow)", "orange"))
            except Exception as e:
                diagnostics.append(("Ollama API", f"❌ Error: {str(e)[:50]}", "red"))
            
            # 4. Check Workspace Access
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if os.path.exists(workspace_root):
                file_count = len([f for f in os.listdir(workspace_root) if f.endswith('.py')])
                diagnostics.append(("Workspace", f"✅ Accessible ({file_count} Python files)", "green"))
            else:
                diagnostics.append(("Workspace", "❌ Not Accessible", "red"))
            
            # 5. Check Python Environment
            diagnostics.append(("Python Version", f"✅ {sys.version.split()[0]}", "green"))
            diagnostics.append(("Python Executable", f"  {sys.executable}", "cyan"))
            
            # 6. Check Syntax Highlighting
            if HAS_SCINTILLA:
                diagnostics.append(("Syntax Highlighting", "✅ QsciScintilla Available", "green"))
            else:
                diagnostics.append(("Syntax Highlighting", "⚠️ Basic (QsciScintilla not installed)", "orange"))
            
            # Display results
            for name, status, color in diagnostics:
                self.output_text.append(f"  {name}: {status}\n")
            
            self.output_text.append("\n" + "=" * 60 + "\n")
            self.output_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Diagnostics Complete\n")
            
            self.status_label.setText("✅ Diagnostics complete")
            logger.info("Self-diagnostics completed")
            
        except Exception as e:
            logger.error(f"Diagnostics failed: {e}", exc_info=True)
            self.output_text.append(f"❌ Diagnostics Error: {e}\n")
            self.status_label.setText("❌ Diagnostics failed")
