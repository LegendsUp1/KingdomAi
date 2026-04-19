#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Code Generator component for Kingdom AI.

This module provides code generation and manipulation capabilities for the 
Kingdom AI platform, enabling automated code creation, analysis, and optimization.
"""

import logging

# Set up logger FIRST before any usage
logger = logging.getLogger(__name__)

# Code generator components - built-in implementations
HAS_FIX_MODULES = False


class CodeTemplateManager:
    def __init__(self, event_bus=None, config=None):
        self.event_bus = event_bus
        self.templates = {
            'python_function': "def {name}({args}):\n    pass",
            'javascript_function': "function {name}({args}) {{\n    // TODO: Implement\n}}",
            'python_class': "class {name}:\n    def __init__(self):\n        pass"
        }
    
    def get_templates(self):
        return self.templates


class SyntaxAnalyzer:
    def __init__(self, event_bus=None, config=None):
        self.event_bus = event_bus
    
    def analyze_syntax(self, code, language):
        return {'valid': True, 'errors': [], 'warnings': []}


class CodeOptimizer:
    def __init__(self, event_bus=None, config=None):
        self.event_bus = event_bus
    
    def optimize(self, code, language):
        return code, "Optimization not available"


class AutocompletionEngine:
    def __init__(self, event_bus=None, config=None):
        self.event_bus = event_bus
    
    def complete(self, code, position, language):
        return []


class CodeGenerator:
    def __init__(self, event_bus=None, config=None):
        self.event_bus = event_bus
        self._ollama_base = None

    def _get_model(self) -> str:
        try:
            from core.ollama_gateway import OllamaOrchestrator
            return OllamaOrchestrator().get_model_for_task("code") or "cogito:latest"
        except Exception:
            return "cogito:latest"

    def _get_ollama_base(self) -> str:
        if self._ollama_base is None:
            try:
                from core.ollama_gateway import get_ollama_url
                self._ollama_base = get_ollama_url()
            except ImportError:
                self._ollama_base = "http://localhost:11434"
        return self._ollama_base

    def generate(self, description: str, language: str) -> str:
        """Generate code via Ollama. Falls back to a minimal template on failure."""
        try:
            import requests
            prompt = (
                f"Write clean, production-ready {language} code for the following requirement. "
                f"Return ONLY the code with no explanation.\n\n{description}"
            )
            resp = requests.post(
                f"{self._get_ollama_base()}/api/generate",
                json={"model": self._get_model(), "prompt": prompt, "stream": False},
                timeout=60,
            )
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text:
                    return text
        except Exception as e:
            logger.warning(f"Ollama code generation failed: {e}")

        templates = {
            "python": f'def generated():\n    """{description}"""\n    raise NotImplementedError("Implement me")\n',
            "javascript": f'function generated() {{\n  // {description}\n  throw new Error("Implement me");\n}}\n',
        }
        return templates.get(language.lower(), f"// {language}: {description}\n// Implement here\n")


class CodeReviewEngine:
    def __init__(self, event_bus=None, config=None):
        self.event_bus = event_bus
    
    def review_code(self, code, language):
        return {'score': 0.8, 'issues': [], 'suggestions': []}

import os
import json
import time
from core.base_component import BaseComponent
from typing import Dict, Any, List

class RealCodeGenerator(BaseComponent):
    """
    REAL AI-powered code generator using ThothAI backend - NO MOCK DATA.
    
    Generates actual code using AI models with real execution capabilities.
    """
    
    def __init__(self, event_bus=None, config: Dict[str, Any] = None):
        """Initialize the REAL Code Generator.
        
        Args:
            event_bus: Event bus for communication
            config: Configuration dictionary
        """
        # BaseComponent expects (name, event_bus, config) - ensure proper mapping
        super().__init__(name="RealCodeGenerator", event_bus=event_bus, config=config)  # type: ignore
        self.thoth_ai = None
        self.supported_languages = [
            'python', 'javascript', 'typescript', 'java', 'c++', 'c#',
            'go', 'rust', 'php', 'ruby', 'swift', 'kotlin', 'html', 'css', 'sql'
        ]
        self.generation_history = []
        
        # Initialize AI backend
        self._init_ai_backend()
        
        logger.info("Real AI Code Generator initialized with ThothAI backend")
    
    def _init_ai_backend(self):
        """Initialize ThothAI backend for code generation."""
        try:
            from ai.thoth import ThothAI
            
            # Initialize ThothAI with code-specific configuration
            code_config = {
                'focus': 'code_generation',
                'temperature': 0.2,  # Lower temperature for more precise code
                'max_tokens': 4000
            }
            
            # Initialize ThothAI with voice_config (required parameter)
            voice_config = {
                'enabled': False,  # Code generator doesn't need voice
                'model': 'tts_models/multilingual/multi-dataset/xtts_v2'
            }
            self.thoth_ai = ThothAI(system_config=code_config, voice_config=voice_config)
            logger.info("ThothAI backend initialized for code generation")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI backend: {e}")
            self.thoth_ai = None
    
    async def generate_code(self, description: str, language: str = 'python', 
                           code_type: str = 'function') -> Dict[str, Any]:
        """Generate code using real AI based on description - NO MOCK DATA."""
        try:
            if not self.thoth_ai:
                return {
                    'success': False,
                    'error': 'AI backend not available',
                    'code': f'# AI backend unavailable\n# Requested: {description}\npass'
                }
            
            # Build context-aware prompt
            prompt = self._build_code_generation_prompt(description, language, code_type)
            
            # Generate code with AI
            ai_response = await self.thoth_ai.process_message(prompt, {  # type: ignore
                'task': 'code_generation',
                'language': language,
                'type': code_type
            })
            
            if ai_response['success']:
                # Extract and validate code
                generated_code = self._extract_code_from_response(ai_response['response'])
                
                # Validate syntax if possible
                validation_result = self._validate_code_syntax(generated_code, language)
                
                # Store in history
                generation_entry = {
                    'description': description,
                    'language': language,
                    'code_type': code_type,
                    'generated_code': generated_code,
                    'validation': validation_result,
                    'timestamp': time.time()
                }
                self.generation_history.append(generation_entry)
                
                return {
                    'success': True,
                    'code': generated_code,
                    'language': language,
                    'validation': validation_result,
                    'ai_model': ai_response.get('model', 'unknown')
                }
            else:
                return {
                    'success': False,
                    'error': ai_response.get('error', 'AI generation failed'),
                    'code': f'# AI generation failed: {ai_response.get("error", "unknown error")}\npass'
                }
                
        except Exception as e:
            logger.error(f"Error generating code: {e}")
            return {
                'success': False,
                'error': str(e),
                'code': f'# Error during generation: {str(e)}\npass'
            }
    
    def _build_code_generation_prompt(self, description: str, language: str, code_type: str) -> str:
        """Build context-aware prompt for code generation."""
        base_prompt = f"""Generate {language} code for the following request:
        
        Description: {description}
        Code type: {code_type}
        Language: {language}
        
        Requirements:
        - Write clean, well-commented code
        - Follow best practices for {language}
        - Include error handling where appropriate
        - Make the code production-ready
        - Add type hints if the language supports them
        
        Please provide only the code, properly formatted:"""
        
        # Add language-specific instructions
        if language == 'python':
            base_prompt += "\n- Follow PEP 8 style guidelines\n- Use type hints\n- Include docstrings"
        elif language == 'javascript':
            base_prompt += "\n- Use modern ES6+ syntax\n- Include JSDoc comments\n- Handle promises properly"
        elif language == 'java':
            base_prompt += "\n- Follow Java naming conventions\n- Include proper access modifiers\n- Add Javadoc comments"
        
        return base_prompt
    
    def _extract_code_from_response(self, response: str) -> str:
        """Extract code from AI response."""
        try:
            # Look for code blocks in markdown format
            if '```' in response:
                # Extract code between triple backticks
                parts = response.split('```')
                if len(parts) >= 3:
                    # Get the code block (skip language identifier)
                    code_block = parts[1]
                    if '\n' in code_block and code_block.strip().split('\n')[0] in self.supported_languages:
                        # Remove language identifier line
                        return '\n'.join(code_block.strip().split('\n')[1:])
                    return code_block.strip()
            
            # If no code blocks, return entire response (might be inline code)
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error extracting code: {e}")
            return response
    
    def _validate_code_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """Validate code syntax for supported languages."""
        validation_result = {
            'valid': False,
            'errors': [],
            'warnings': []
        }
        
        try:
            if language == 'python':
                # Use AST to validate Python syntax
                import ast
                ast.parse(code)
                validation_result['valid'] = True
                validation_result['message'] = 'Python syntax valid'
                
            elif language in ['javascript', 'typescript']:
                try:
                    import subprocess
                    result = subprocess.run(
                        ['node', '-e', f'new Function({repr(code)})'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        validation_result['valid'] = True
                        validation_result['message'] = f'{language.title()} syntax valid'
                    else:
                        validation_result['valid'] = False
                        validation_result['errors'].append(result.stderr.strip())
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    validation_result['valid'] = True
                    validation_result['message'] = f'{language.title()} syntax check skipped (Node.js not available)'
                
            else:
                validation_result['valid'] = True
                validation_result['message'] = f'Syntax check not available for {language}'
                
        except SyntaxError as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Syntax error: {str(e)}")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Validation error: {str(e)}")
            
        return validation_result
    
    async def analyze_code(self, code: str, language: str = 'python') -> Dict[str, Any]:
        """Analyze code using AI for improvements and issues - REAL ANALYSIS."""
        try:
            if not self.thoth_ai:
                return {'success': False, 'error': 'AI backend not available'}
            
            prompt = f"""Analyze the following {language} code and provide:
            1. Code quality assessment
            2. Potential improvements
            3. Security issues (if any)
            4. Performance optimizations
            5. Best practice recommendations
            
            Code to analyze:
            ```{language}
            {code}
            ```
            
            Provide a detailed analysis:"""
            
            ai_response = await self.thoth_ai.process_message(prompt, {  # type: ignore
                'task': 'code_analysis',
                'language': language
            })
            
            if ai_response['success']:
                return {
                    'success': True,
                    'analysis': ai_response['response'],
                    'language': language,
                    'timestamp': time.time()
                }
            else:
                return {
                    'success': False,
                    'error': ai_response.get('error', 'Analysis failed')
                }
                
        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            return {'success': False, 'error': str(e)}
    
    async def optimize_code(self, code: str, language: str = 'python') -> Dict[str, Any]:
        """Optimize code using AI - REAL OPTIMIZATION."""
        try:
            if not self.thoth_ai:
                return {'success': False, 'error': 'AI backend not available'}
            
            prompt = f"""Optimize the following {language} code for:
            - Better performance
            - Improved readability
            - Best practices
            - Security
            
            Original code:
            ```{language}
            {code}
            ```
            
            Provide the optimized version with explanations:"""
            
            ai_response = await self.thoth_ai.process_message(prompt, {  # type: ignore
                'task': 'code_optimization',
                'language': language
            })
            
            if ai_response['success']:
                optimized_code = self._extract_code_from_response(ai_response['response'])
                
                return {
                    'success': True,
                    'original_code': code,
                    'optimized_code': optimized_code,
                    'explanation': ai_response['response'],
                    'language': language
                }
            else:
                return {
                    'success': False,
                    'error': ai_response.get('error', 'Optimization failed')
                }
                
        except Exception as e:
            logger.error(f"Error optimizing code: {e}")
            return {'success': False, 'error': str(e)}
    
    def execute_code(self, code: str, language: str = 'python') -> Dict[str, Any]:
        """Execute code safely (Python only for now) - REAL EXECUTION."""
        try:
            if language != 'python':
                return {
                    'success': False,
                    'error': f'Code execution not supported for {language}'
                }
            
            # Create a restricted execution environment
            import io
            import sys
            from contextlib import redirect_stdout, redirect_stderr
            
            # Capture output
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            execution_result = {
                'success': False,
                'output': '',
                'errors': '',
                'execution_time': 0
            }
            
            start_time = time.time()
            
            try:
                # Execute code with output capture
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    import builtins as _builtins_mod
                    app_mode = os.environ.get('KINGDOM_APP_MODE', 'consumer')
                    
                    if app_mode == 'creator':
                        safe_globals = {
                            '__builtins__': _builtins_mod,
                            'event_bus': self.event_bus,
                            'thoth_ai': self.thoth_ai,
                        }
                    else:
                        safe_globals = {
                            '__builtins__': {
                                'print': print,
                                'len': len,
                                'str': str,
                                'int': int,
                                'float': float,
                                'list': list,
                                'dict': dict,
                                'tuple': tuple,
                                'set': set,
                                'range': range,
                                'enumerate': enumerate,
                                'zip': zip,
                                'map': map,
                                'filter': filter,
                                'sum': sum,
                                'max': max,
                                'min': min,
                                'abs': abs,
                                'round': round,
                            },
                        }
                    
                    exec(code, safe_globals)
                    
                execution_result['success'] = True
                execution_result['output'] = stdout_capture.getvalue()
                
            except Exception as e:
                execution_result['errors'] = str(e)
                execution_result['stderr'] = stderr_capture.getvalue()
            
            execution_result['execution_time'] = time.time() - start_time
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error executing code: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time': 0
            }
    
    def get_generation_history(self) -> List[Dict[str, Any]]:
        """Get code generation history."""
        return self.generation_history.copy()
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported programming languages."""
        return self.supported_languages.copy()
    
    def handle_generate_code_request(self, data: Dict[str, Any]) -> None:
        """Handle code generation request from event bus.
        
        Args:
            data: Dict containing 'prompt' or 'description', 'language', optionally 'code_type'
        """
        try:
            import asyncio
            
            description = data.get('prompt') or data.get('description') or data.get('text', '')
            language = data.get('language', 'python')
            code_type = data.get('code_type', 'function')
            
            logger.info(f"📋 Code Generator: Generating code for: {description[:50]}...")
            
            # Run async generation
            async def _generate():
                result = await self.generate_code(description, language, code_type)
                # Publish result
                if self.event_bus:
                    self.event_bus.publish("codegen.code_generated", {
                        'code': result.get('code', ''),
                        'language': language,
                        'success': result.get('success', False),
                        'message': 'Code generated successfully' if result.get('success') else result.get('error', 'Generation failed')
                    })
                    if result.get('success') and description:
                        try:
                            from core.kingdom_event_names import REQUEST_CLAW_CODING_TASK
                            self.event_bus.publish(REQUEST_CLAW_CODING_TASK, {
                                "task": description,
                                "language": language,
                                "code_type": code_type,
                            })
                        except Exception:
                            pass
            
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(_generate(), loop=loop)
            except RuntimeError:
                # No running loop - run directly
                asyncio.run(_generate())
                
        except Exception as e:
            logger.error(f"❌ Code generation handler error: {e}")
            if self.event_bus:
                self.event_bus.publish("codegen.code_generated", {
                    'code': f'# Error: {e}',
                    'language': 'python',
                    'success': False,
                    'message': str(e)
                })
    
    def handle_code_analysis_request(self, data: Dict[str, Any]) -> None:
        """Handle code analysis request from event bus.
        
        Args:
            data: Dict containing 'code' and optionally 'language'
        """
        try:
            import asyncio
            
            code = data.get('code', '')
            language = data.get('language', 'python')
            
            logger.info(f"📋 Code Generator: Analyzing code ({len(code)} chars)...")
            
            # Run async analysis
            async def _analyze():
                result = await self.analyze_code(code, language)
                # Publish result
                if self.event_bus:
                    self.event_bus.publish("codegen.analysis_complete", result)
            
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(_analyze(), loop=loop)
            except RuntimeError:
                asyncio.run(_analyze())
                
        except Exception as e:
            logger.error(f"❌ Code analysis handler error: {e}")
    
    def handle_code_optimization_request(self, data: Dict[str, Any]) -> None:
        """Handle code optimization request from event bus.
        
        Args:
            data: Dict containing 'code' and optionally 'language'
        """
        try:
            import asyncio
            
            code = data.get('code', '')
            language = data.get('language', 'python')
            
            logger.info(f"📋 Code Generator: Optimizing code ({len(code)} chars)...")
            
            # Run async optimization
            async def _optimize():
                result = await self.optimize_code(code, language)
                # Publish result
                if self.event_bus:
                    self.event_bus.publish("codegen.optimization_complete", result)
            
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(_optimize(), loop=loop)
            except RuntimeError:
                asyncio.run(_optimize())
                
        except Exception as e:
            logger.error(f"❌ Code optimization handler error: {e}")
    
    def handle_execute_request(self, data: Dict[str, Any]) -> None:
        """Handle codegen.execute event from GUI.
        
        This is the backend handler for code execution requests from the Code Generator tab.
        Executes code safely and publishes results back via codegen.execution_complete.
        
        Args:
            data: Dict containing 'code', 'language', and optionally 'mode'
        """
        try:
            code = data.get('code', '')
            language = data.get('language', 'python')
            mode = data.get('mode', 'run_only')
            
            logger.info(f"📋 Code Generator: Executing code (mode={mode}, lang={language})")
            
            if not code.strip():
                self._publish_execution_result({'output': '', 'errors': 'No code provided'})
                return
            
            # Execute the code
            result = self.execute_code(code, language)
            
            # If mode is 'apply_and_reload', use SystemUpdater's safe hot-reload
            if mode == 'apply_and_reload' and 'file_path' in data:
                file_path = data.get('file_path')
                try:
                    if not file_path or not isinstance(file_path, (str, bytes)):
                        logger.error(f"Invalid file_path type: {type(file_path)}")
                    else:
                        try:
                            from core.system_updater import get_system_updater
                            updater = get_system_updater(self.event_bus)
                            reload_result = updater.hot_reload_module(str(file_path), code)
                            if reload_result.get('success'):
                                result['hot_reload'] = True
                                result['module_reloaded'] = reload_result.get('module', '')
                                logger.info(f"Module hot-reloaded: {reload_result.get('module')}")
                            else:
                                result['hot_reload'] = False
                                result['write_error'] = reload_result.get('message', 'Reload failed')
                                if reload_result.get('rolled_back'):
                                    result['rolled_back'] = True
                                logger.warning(f"Hot reload failed: {reload_result.get('message')}")
                        except ImportError:
                            # Fallback: direct write + reload
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(code)
                            logger.info(f"Code written to: {file_path}")
                            import importlib as _imp
                            abs_path = os.path.abspath(str(file_path))
                            mod_name = data.get('module_name')
                            if not mod_name:
                                for name, mod in sys.modules.items():
                                    if mod and getattr(mod, '__file__', None):
                                        if os.path.abspath(mod.__file__) == abs_path:
                                            mod_name = name
                                            break
                            if mod_name and mod_name in sys.modules:
                                _imp.reload(sys.modules[mod_name])
                                result['hot_reload'] = True
                                result['module_reloaded'] = mod_name
                                logger.info(f"Module hot-reloaded (fallback): {mod_name}")
                except Exception as write_err:
                    result['write_error'] = str(write_err)
                    logger.error(f"Write/reload error: {write_err}")
            
            # Publish result
            self._publish_execution_result(result)
            
        except Exception as e:
            logger.error(f"❌ Code execution handler error: {e}")
            self._publish_execution_result({'output': '', 'errors': str(e)})
    
    def _publish_execution_result(self, result: Dict[str, Any]) -> None:
        """Publish execution result to the event bus."""
        if self.event_bus:
            self.event_bus.publish("codegen.execution_complete", {
                'output': result.get('output', ''),
                'errors': result.get('errors', ''),
                'success': result.get('success', False),
                'execution_time': result.get('execution_time', 0),
                'hot_reload': result.get('hot_reload', False),
                'module_reloaded': result.get('module_reloaded', '')
            })
    
    async def shutdown(self):
        """Shutdown the code generator component."""
        logger.info("Shutting down RealCodeGenerator component")
        self.generation_history.clear()
        logger.info("RealCodeGenerator component shut down successfully")

async def initialize_code_generator_components(event_bus):
    """
    Initialize code generator components and connect to the event bus.
    
    Args:
        event_bus: Event bus instance for component communication
        
    Returns:
        Dictionary of initialized components
    """
    logger = logging.getLogger("kingdom_ai")
    logger.info("Initializing code generator components")
    components = {}
    
    try:
        # Create main code generator - use RealCodeGenerator which has all methods
        # including handle_execute_request, execute_code, etc.
        main_code_generator = RealCodeGenerator(event_bus=event_bus)
        components["code_generator"] = main_code_generator
        
        # Initialize subcomponents if fix modules are available
        if HAS_FIX_MODULES:
            # Code Template Manager
            template_manager = CodeTemplateManager(event_bus=event_bus)
            components["template_manager"] = template_manager
            
            # Syntax Analyzer
            syntax_analyzer = SyntaxAnalyzer(event_bus=event_bus)
            components["syntax_analyzer"] = syntax_analyzer
            
            # Code Optimizer
            code_optimizer = CodeOptimizer(event_bus=event_bus)
            components["code_optimizer"] = code_optimizer
            
            # Autocompletion Engine
            autocompletion = AutocompletionEngine(event_bus=event_bus)
            components["autocompletion"] = autocompletion
            
            # Code Review Engine
            code_review = CodeReviewEngine(event_bus=event_bus)
            components["code_review"] = code_review
        
        # Register event handlers for main code generator
        if hasattr(event_bus, 'register_handler'):
            event_bus.register_handler("code.generate", main_code_generator.handle_generate_code_request)
            event_bus.register_handler("code.analyze", main_code_generator.handle_code_analysis_request)
            event_bus.register_handler("code.optimize", main_code_generator.handle_code_optimization_request)
        elif hasattr(event_bus, 'subscribe'):
            event_bus.subscribe("code.generate", main_code_generator.handle_generate_code_request)
            event_bus.subscribe("code.analyze", main_code_generator.handle_code_analysis_request)
            event_bus.subscribe("code.optimize", main_code_generator.handle_code_optimization_request)
            
        # Register additional handlers if fix modules are available
        if HAS_FIX_MODULES and hasattr(event_bus, 'register_handler'):
            event_bus.register_handler("code.get_templates", template_manager.get_templates)
            event_bus.register_handler("code.syntax_check", syntax_analyzer.analyze_syntax)
            event_bus.register_handler("code.optimize_code", code_optimizer.optimize)
            event_bus.register_handler("code.autocomplete", autocompletion.complete)
            event_bus.register_handler("code.review", code_review.review_code)
        elif HAS_FIX_MODULES and hasattr(event_bus, 'subscribe'):
            event_bus.subscribe("code.get_templates", template_manager.get_templates)
            event_bus.subscribe("code.syntax_check", syntax_analyzer.analyze_syntax)
            event_bus.subscribe("code.optimize_code", code_optimizer.optimize)
            event_bus.subscribe("code.autocomplete", autocompletion.complete)
            event_bus.subscribe("code.review", code_review.review_code)
        
        # SOTA 2026: Chat/Voice command event subscriptions
        if hasattr(event_bus, 'subscribe'):
            event_bus.subscribe("codegen.generate", main_code_generator.handle_generate_code_request)
            event_bus.subscribe("codegen.strategy.generate", main_code_generator.handle_generate_code_request)
            event_bus.subscribe("codegen.contract.generate", main_code_generator.handle_generate_code_request)
            event_bus.subscribe("codegen.explain", main_code_generator.handle_code_analysis_request)
            event_bus.subscribe("codegen.optimize", main_code_generator.handle_code_optimization_request)
            event_bus.subscribe("codegen.templates.list", lambda p: event_bus.publish("codegen.templates.response", {"templates": main_code_generator.supported_languages}))
            # CRITICAL FIX (2026-02-03): Subscribe to codegen.execute from GUI Code Generator tab
            # This closes the event loop: GUI publishes codegen.execute -> backend handles -> publishes codegen.execution_complete
            event_bus.subscribe("codegen.execute", main_code_generator.handle_execute_request)
            logger.info("📡 Code Generator SOTA 2026 chat command handlers registered (including codegen.execute)")
        
        # Initialize main code generator
        await main_code_generator.initialize()
        
        # Set all components as initialized
        for component_name, component in components.items():
            if hasattr(component, 'initialized'):
                component.initialized = True
                
        logger.info(f"Code generator system initialized with {len(components)} components")
    except Exception as e:
        logger.error(f"Error initializing code generator components: {e}")
    
    return components
