#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codebase Introspector for Kingdom AI - SOTA 2026

Provides full codebase access to the Ollama brain and Chat Widget for:
- Source file indexing and retrieval
- AST-based code introspection (functions, classes, imports)
- Safe runtime code editing with automatic backups
- Repository-level context for AI code generation
- Dynamic code modification capabilities

Based on SOTA 2026 research:
- Context packing for LLM code understanding
- Repository-level coding patterns
- SWE-agent style autonomous code modification
- Safe edit patterns with rollback support
"""

import os
import sys
import ast
import json
import logging
import hashlib
import shutil
import difflib
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Set, Callable
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from functools import lru_cache
import threading

logger = logging.getLogger(__name__)

# Base path for the codebase
CODEBASE_ROOT = Path(__file__).parent.parent


@dataclass
class CodeSymbol:
    """Represents a code symbol (function, class, variable)."""
    name: str
    symbol_type: str  # 'function', 'class', 'method', 'variable', 'import'
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    signature: Optional[str] = None
    parent_class: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass  
class FileIndex:
    """Index of a single source file."""
    file_path: str
    relative_path: str
    size_bytes: int
    last_modified: float
    content_hash: str
    language: str
    symbols: List[CodeSymbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    line_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path': self.file_path,
            'relative_path': self.relative_path,
            'size_bytes': self.size_bytes,
            'last_modified': self.last_modified,
            'content_hash': self.content_hash,
            'language': self.language,
            'symbols': [s.to_dict() for s in self.symbols],
            'imports': self.imports,
            'line_count': self.line_count
        }


@dataclass
class EditOperation:
    """Represents a code edit operation."""
    file_path: str
    edit_type: str  # 'replace', 'insert', 'delete', 'append'
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    backup_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = False
    error: Optional[str] = None


class CodebaseIntrospector:
    """
    SOTA 2026 Codebase Introspector for Kingdom AI.
    
    Provides full codebase access to AI systems including:
    - Source file indexing and search
    - AST-based symbol extraction
    - Safe runtime code editing
    - Repository context generation for LLMs
    """
    
    # File patterns to index
    PYTHON_EXTENSIONS = {'.py'}
    CONFIG_EXTENSIONS = {'.json', '.yaml', '.yml', '.toml', '.ini', '.env'}
    DOC_EXTENSIONS = {'.md', '.txt', '.rst'}
    
    # Directories to exclude
    EXCLUDED_DIRS = {
        '__pycache__', '.git', '.venv', 'venv', 'node_modules',
        '.idea', '.vscode', 'build', 'dist', 'eggs', '*.egg-info',
        'backup', 'corrupted_files_backup', 'kingdom_backups',
        'Unity Hub', 'GPT-SoVITS', 'android-stubs', 'gradle'
    }
    
    # Maximum file size to index (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    def __init__(self, event_bus=None, root_path: Optional[Path] = None):
        """Initialize the codebase introspector."""
        self.event_bus = event_bus
        self.root_path = root_path or CODEBASE_ROOT
        self._file_index: Dict[str, FileIndex] = {}
        self._symbol_index: Dict[str, List[CodeSymbol]] = {}  # name -> symbols
        self._edit_history: List[EditOperation] = []
        self._backup_dir = self.root_path / ".kingdom_backups"
        self._index_lock = threading.Lock()
        self._initialized = False
        
        # Create backup directory
        self._backup_dir.mkdir(exist_ok=True)
        
        # Subscribe to EventBus topics
        if event_bus:
            self._subscribe_to_events()
        
        logger.info("✅ Codebase Introspector initialized")
    
    def _subscribe_to_events(self):
        """Subscribe to EventBus topics for AI access."""
        try:
            # File access topics
            self.event_bus.subscribe('codebase.file.read', self._handle_file_read)
            self.event_bus.subscribe('codebase.file.write', self._handle_file_write)
            self.event_bus.subscribe('codebase.file.list', self._handle_file_list)
            
            # Search topics
            self.event_bus.subscribe('codebase.search.text', self._handle_search_text)
            self.event_bus.subscribe('codebase.search.symbol', self._handle_search_symbol)
            self.event_bus.subscribe('codebase.search.file', self._handle_search_file)
            
            # Introspection topics
            self.event_bus.subscribe('codebase.symbols.get', self._handle_get_symbols)
            self.event_bus.subscribe('codebase.context.get', self._handle_get_context)
            self.event_bus.subscribe('codebase.ast.analyze', self._handle_ast_analyze)
            
            # Edit topics
            self.event_bus.subscribe('codebase.edit.apply', self._handle_edit_apply)
            self.event_bus.subscribe('codebase.edit.preview', self._handle_edit_preview)
            self.event_bus.subscribe('codebase.edit.rollback', self._handle_edit_rollback)
            
            # Index management
            self.event_bus.subscribe('codebase.index.rebuild', self._handle_index_rebuild)
            self.event_bus.subscribe('codebase.index.status', self._handle_index_status)
            
            logger.info("✅ Codebase Introspector subscribed to EventBus topics")
        except Exception as e:
            logger.warning(f"Failed to subscribe to EventBus: {e}")
    
    # ==================== INDEXING ====================
    
    def build_index(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Build or rebuild the codebase index."""
        with self._index_lock:
            if self._initialized and not force_rebuild:
                return self.get_index_status()
            
            logger.info("🔍 Building codebase index...")
            start_time = datetime.now()
            
            self._file_index.clear()
            self._symbol_index.clear()
            
            files_indexed = 0
            symbols_found = 0
            errors = []
            
            for file_path in self._walk_codebase():
                try:
                    index = self._index_file(file_path)
                    if index:
                        self._file_index[str(file_path)] = index
                        files_indexed += 1
                        
                        # Add symbols to symbol index
                        for symbol in index.symbols:
                            if symbol.name not in self._symbol_index:
                                self._symbol_index[symbol.name] = []
                            self._symbol_index[symbol.name].append(symbol)
                            symbols_found += 1
                            
                except Exception as e:
                    errors.append(f"{file_path}: {e}")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            self._initialized = True
            
            status = {
                'files_indexed': files_indexed,
                'symbols_found': symbols_found,
                'elapsed_seconds': elapsed,
                'errors': errors[:10]  # Limit error list
            }
            
            logger.info(f"✅ Codebase index built: {files_indexed} files, {symbols_found} symbols in {elapsed:.2f}s")
            return status
    
    def _walk_codebase(self) -> List[Path]:
        """Walk the codebase and yield indexable files."""
        files = []
        
        for root, dirs, filenames in os.walk(self.root_path):
            # Filter excluded directories
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS 
                      and not any(d.endswith(ext) for ext in ['.egg-info'])]
            
            root_path = Path(root)
            
            for filename in filenames:
                file_path = root_path / filename
                ext = file_path.suffix.lower()
                
                # Check if file should be indexed
                if ext in self.PYTHON_EXTENSIONS | self.CONFIG_EXTENSIONS | self.DOC_EXTENSIONS:
                    # Check file size
                    try:
                        if file_path.stat().st_size <= self.MAX_FILE_SIZE:
                            files.append(file_path)
                    except OSError:
                        continue
        
        return files
    
    def _index_file(self, file_path: Path) -> Optional[FileIndex]:
        """Index a single file."""
        try:
            stat = file_path.stat()
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            content_hash = hashlib.md5(content.encode()).hexdigest()
            relative_path = str(file_path.relative_to(self.root_path))
            
            # Determine language
            ext = file_path.suffix.lower()
            if ext in self.PYTHON_EXTENSIONS:
                language = 'python'
            elif ext in self.CONFIG_EXTENSIONS:
                language = 'config'
            else:
                language = 'text'
            
            # Extract symbols for Python files
            symbols = []
            imports = []
            if language == 'python':
                symbols, imports = self._extract_python_symbols(content, str(file_path))
            
            return FileIndex(
                file_path=str(file_path),
                relative_path=relative_path,
                size_bytes=stat.st_size,
                last_modified=stat.st_mtime,
                content_hash=content_hash,
                language=language,
                symbols=symbols,
                imports=imports,
                line_count=content.count('\n') + 1
            )
            
        except Exception as e:
            logger.debug(f"Failed to index {file_path}: {e}")
            return None
    
    def _extract_python_symbols(self, content: str, file_path: str) -> Tuple[List[CodeSymbol], List[str]]:
        """Extract symbols from Python source using AST."""
        symbols = []
        imports = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return symbols, imports
        
        for node in ast.walk(tree):
            # Extract imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
            
            # Extract functions
            elif isinstance(node, ast.FunctionDef):
                symbols.append(self._create_function_symbol(node, file_path))
            
            # Extract async functions
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(self._create_function_symbol(node, file_path, is_async=True))
            
            # Extract classes
            elif isinstance(node, ast.ClassDef):
                class_symbol = self._create_class_symbol(node, file_path)
                symbols.append(class_symbol)
                
                # Extract methods within class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_symbol = self._create_function_symbol(
                            item, file_path, 
                            parent_class=node.name,
                            is_async=isinstance(item, ast.AsyncFunctionDef)
                        )
                        symbols.append(method_symbol)
        
        return symbols, imports
    
    def _create_function_symbol(self, node, file_path: str, 
                                parent_class: Optional[str] = None,
                                is_async: bool = False) -> CodeSymbol:
        """Create a CodeSymbol for a function/method."""
        # Build signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except:
                    pass
            args.append(arg_str)
        
        signature = f"{'async ' if is_async else ''}def {node.name}({', '.join(args)})"
        
        # Get return type if present
        if node.returns:
            try:
                signature += f" -> {ast.unparse(node.returns)}"
            except:
                pass
        
        # Get docstring
        docstring = ast.get_docstring(node)
        
        # Get decorators
        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except:
                pass
        
        return CodeSymbol(
            name=node.name,
            symbol_type='method' if parent_class else 'function',
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring,
            signature=signature,
            parent_class=parent_class,
            decorators=decorators
        )
    
    def _create_class_symbol(self, node, file_path: str) -> CodeSymbol:
        """Create a CodeSymbol for a class."""
        # Build signature with bases
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except:
                pass
        
        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"
        
        # Get docstring
        docstring = ast.get_docstring(node)
        
        # Get decorators
        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except:
                pass
        
        return CodeSymbol(
            name=node.name,
            symbol_type='class',
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring,
            signature=signature,
            decorators=decorators
        )
    
    # ==================== FILE ACCESS ====================
    
    def read_file(self, file_path: str, line_start: Optional[int] = None, 
                  line_end: Optional[int] = None) -> Dict[str, Any]:
        """Read a file's content."""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.root_path / path
            
            if not path.exists():
                return {'success': False, 'error': f"File not found: {file_path}"}
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Apply line range if specified
            if line_start is not None or line_end is not None:
                start = (line_start or 1) - 1  # Convert to 0-indexed
                end = line_end or len(lines)
                lines = lines[start:end]
                content = ''.join(lines)
            else:
                content = ''.join(lines)
            
            return {
                'success': True,
                'file_path': str(path),
                'content': content,
                'line_count': len(lines),
                'line_start': line_start or 1,
                'line_end': line_end or len(lines)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def write_file(self, file_path: str, content: str, 
                   create_backup: bool = True) -> Dict[str, Any]:
        """Write content to a file with optional backup."""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.root_path / path
            
            backup_path = None
            
            # Create backup if file exists
            if create_backup and path.exists():
                backup_path = self._create_backup(path)
            
            # Write new content
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Record edit operation
            edit = EditOperation(
                file_path=str(path),
                edit_type='replace',
                new_content=content,
                backup_path=backup_path,
                success=True
            )
            self._edit_history.append(edit)
            
            # Update index
            self._reindex_file(path)
            
            return {
                'success': True,
                'file_path': str(path),
                'backup_path': backup_path,
                'bytes_written': len(content.encode('utf-8'))
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _create_backup(self, file_path: Path) -> str:
        """Create a backup of a file before editing."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = self._backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        logger.info(f"📦 Created backup: {backup_path}")
        
        return str(backup_path)
    
    def _reindex_file(self, file_path: Path):
        """Re-index a single file after modification."""
        try:
            with self._index_lock:
                index = self._index_file(file_path)
                if index:
                    self._file_index[str(file_path)] = index
        except Exception as e:
            logger.warning(f"Failed to reindex {file_path}: {e}")
    
    # ==================== SEARCH ====================
    
    def search_text(self, query: str, file_pattern: str = "*.py",
                   case_sensitive: bool = False, 
                   max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for text across the codebase."""
        results = []
        
        if not case_sensitive:
            query = query.lower()
        
        for file_path, index in self._file_index.items():
            if not self._matches_pattern(index.relative_path, file_pattern):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    search_line = line if case_sensitive else line.lower()
                    if query in search_line:
                        results.append({
                            'file_path': file_path,
                            'relative_path': index.relative_path,
                            'line_number': i,
                            'line_content': line.rstrip(),
                            'match_start': search_line.find(query)
                        })
                        
                        if len(results) >= max_results:
                            return results
                            
            except Exception:
                continue
        
        return results
    
    def search_symbol(self, name: str, symbol_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for symbols by name."""
        results = []
        
        # Exact match first
        if name in self._symbol_index:
            for symbol in self._symbol_index[name]:
                if symbol_type is None or symbol.symbol_type == symbol_type:
                    results.append(symbol.to_dict())
        
        # Partial match
        name_lower = name.lower()
        for symbol_name, symbols in self._symbol_index.items():
            if name_lower in symbol_name.lower() and symbol_name != name:
                for symbol in symbols:
                    if symbol_type is None or symbol.symbol_type == symbol_type:
                        results.append(symbol.to_dict())
        
        return results[:50]  # Limit results
    
    def search_files(self, pattern: str) -> List[Dict[str, Any]]:
        """Search for files by name pattern."""
        results = []
        
        pattern_lower = pattern.lower()
        
        for file_path, index in self._file_index.items():
            if pattern_lower in index.relative_path.lower():
                results.append({
                    'file_path': file_path,
                    'relative_path': index.relative_path,
                    'size_bytes': index.size_bytes,
                    'line_count': index.line_count,
                    'language': index.language,
                    'symbol_count': len(index.symbols)
                })
        
        return results[:50]
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a glob-like pattern."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)
    
    # ==================== CONTEXT GENERATION ====================
    
    def get_file_context(self, file_path: str, include_imports: bool = True,
                        include_symbols: bool = True) -> Dict[str, Any]:
        """Get full context for a file (for LLM consumption)."""
        result = self.read_file(file_path)
        if not result['success']:
            return result
        
        path = Path(file_path)
        if not path.is_absolute():
            path = self.root_path / path
        
        index = self._file_index.get(str(path))
        
        context = {
            'success': True,
            'file_path': str(path),
            'relative_path': str(path.relative_to(self.root_path)) if path.is_relative_to(self.root_path) else str(path),
            'content': result['content'],
            'line_count': result['line_count'],
            'language': index.language if index else 'unknown'
        }
        
        if include_imports and index:
            context['imports'] = index.imports
        
        if include_symbols and index:
            context['symbols'] = [s.to_dict() for s in index.symbols]
        
        return context
    
    def get_repository_context(self, focus_files: List[str] = None,
                              max_tokens_estimate: int = 50000) -> str:
        """
        Generate repository-level context for LLM code understanding.
        
        Based on SOTA 2026 research on context packing for code LLMs.
        """
        if not self._initialized:
            self.build_index()
        
        context_parts = []
        
        # Header
        context_parts.append("# KINGDOM AI CODEBASE CONTEXT\n")
        context_parts.append(f"Generated: {datetime.now().isoformat()}\n\n")
        
        # File structure overview
        context_parts.append("## FILE STRUCTURE\n")
        for relative_path, index in sorted(
            [(idx.relative_path, idx) for idx in self._file_index.values()],
            key=lambda x: x[0]
        )[:100]:
            context_parts.append(f"- {relative_path} ({index.line_count} lines, {len(index.symbols)} symbols)\n")
        
        context_parts.append("\n")
        
        # Key symbols
        context_parts.append("## KEY SYMBOLS\n")
        class_count = 0
        func_count = 0
        for name, symbols in sorted(self._symbol_index.items()):
            for symbol in symbols:
                if symbol.symbol_type == 'class' and class_count < 50:
                    context_parts.append(f"- CLASS: {symbol.signature} @ {symbol.file_path}:{symbol.line_start}\n")
                    if symbol.docstring:
                        context_parts.append(f"  {symbol.docstring[:100]}...\n")
                    class_count += 1
                elif symbol.symbol_type == 'function' and func_count < 100:
                    context_parts.append(f"- FUNC: {symbol.signature} @ {symbol.file_path}:{symbol.line_start}\n")
                    func_count += 1
        
        context_parts.append("\n")
        
        # Focus files content (if specified)
        if focus_files:
            context_parts.append("## FOCUS FILES CONTENT\n\n")
            for file_path in focus_files[:5]:  # Limit to 5 files
                result = self.read_file(file_path)
                if result['success']:
                    context_parts.append(f"### {file_path}\n```python\n{result['content']}\n```\n\n")
        
        return ''.join(context_parts)
    
    # ==================== SAFE CODE EDITING ====================
    
    def apply_edit(self, file_path: str, old_text: str, new_text: str,
                  create_backup: bool = True) -> Dict[str, Any]:
        """
        Apply a find-and-replace edit to a file.
        
        This is the safest editing method - requires exact match of old_text.
        """
        try:
            result = self.read_file(file_path)
            if not result['success']:
                return result
            
            content = result['content']
            
            if old_text not in content:
                return {
                    'success': False,
                    'error': 'old_text not found in file - edit rejected for safety'
                }
            
            # Count occurrences
            occurrences = content.count(old_text)
            if occurrences > 1:
                return {
                    'success': False,
                    'error': f'old_text found {occurrences} times - must be unique for safe edit'
                }
            
            # Apply edit
            new_content = content.replace(old_text, new_text)
            
            return self.write_file(file_path, new_content, create_backup=create_backup)
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def preview_edit(self, file_path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """Preview an edit without applying it."""
        try:
            result = self.read_file(file_path)
            if not result['success']:
                return result
            
            content = result['content']
            
            if old_text not in content:
                return {
                    'success': False,
                    'error': 'old_text not found in file'
                }
            
            # Generate unified diff
            old_lines = content.splitlines(keepends=True)
            new_content = content.replace(old_text, new_text)
            new_lines = new_content.splitlines(keepends=True)
            
            diff = list(difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}"
            ))
            
            return {
                'success': True,
                'diff': ''.join(diff),
                'occurrences': content.count(old_text),
                'old_text_preview': old_text[:200],
                'new_text_preview': new_text[:200]
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def rollback_edit(self, backup_path: str) -> Dict[str, Any]:
        """Rollback to a backup."""
        try:
            backup = Path(backup_path)
            if not backup.exists():
                return {'success': False, 'error': 'Backup file not found'}
            
            # Extract original filename
            # Format: filename.ext.YYYYMMDD_HHMMSS.bak
            parts = backup.name.rsplit('.', 2)
            if len(parts) < 3:
                return {'success': False, 'error': 'Invalid backup filename format'}
            
            original_name = parts[0]
            
            # Find the original file
            # This is simplified - in production would need better tracking
            for file_path in self._file_index.keys():
                if Path(file_path).name.startswith(original_name):
                    shutil.copy2(backup, file_path)
                    self._reindex_file(Path(file_path))
                    return {
                        'success': True,
                        'restored_file': file_path,
                        'backup_used': backup_path
                    }
            
            return {'success': False, 'error': 'Could not determine original file'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_edit_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent edit history."""
        return [
            {
                'file_path': edit.file_path,
                'edit_type': edit.edit_type,
                'timestamp': edit.timestamp,
                'success': edit.success,
                'backup_path': edit.backup_path,
                'error': edit.error
            }
            for edit in self._edit_history[-limit:]
        ]
    
    # ==================== STATUS ====================
    
    def get_index_status(self) -> Dict[str, Any]:
        """Get current index status."""
        return {
            'initialized': self._initialized,
            'files_indexed': len(self._file_index),
            'symbols_indexed': sum(len(s) for s in self._symbol_index.values()),
            'unique_symbols': len(self._symbol_index),
            'edit_history_count': len(self._edit_history),
            'backup_dir': str(self._backup_dir)
        }
    
    # ==================== EVENT HANDLERS ====================
    
    def _handle_file_read(self, payload: Dict[str, Any]):
        """Handle EventBus file read request."""
        file_path = payload.get('file_path', '')
        line_start = payload.get('line_start')
        line_end = payload.get('line_end')
        request_id = payload.get('request_id', '')
        
        result = self.read_file(file_path, line_start, line_end)
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.file.read.response', result)
    
    def _handle_file_write(self, payload: Dict[str, Any]):
        """Handle EventBus file write request."""
        file_path = payload.get('file_path', '')
        content = payload.get('content', '')
        create_backup = payload.get('create_backup', True)
        request_id = payload.get('request_id', '')
        
        result = self.write_file(file_path, content, create_backup)
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.file.write.response', result)
    
    def _handle_file_list(self, payload: Dict[str, Any]):
        """Handle EventBus file list request."""
        pattern = payload.get('pattern', '*')
        request_id = payload.get('request_id', '')
        
        result = {
            'success': True,
            'files': self.search_files(pattern),
            'request_id': request_id
        }
        
        if self.event_bus:
            self.event_bus.publish('codebase.file.list.response', result)
    
    def _handle_search_text(self, payload: Dict[str, Any]):
        """Handle EventBus text search request."""
        query = payload.get('query', '')
        file_pattern = payload.get('file_pattern', '*.py')
        case_sensitive = payload.get('case_sensitive', False)
        request_id = payload.get('request_id', '')
        
        results = self.search_text(query, file_pattern, case_sensitive)
        
        if self.event_bus:
            self.event_bus.publish('codebase.search.text.response', {
                'success': True,
                'results': results,
                'query': query,
                'request_id': request_id
            })
    
    def _handle_search_symbol(self, payload: Dict[str, Any]):
        """Handle EventBus symbol search request."""
        name = payload.get('name', '')
        symbol_type = payload.get('symbol_type')
        request_id = payload.get('request_id', '')
        
        results = self.search_symbol(name, symbol_type)
        
        if self.event_bus:
            self.event_bus.publish('codebase.search.symbol.response', {
                'success': True,
                'results': results,
                'name': name,
                'request_id': request_id
            })
    
    def _handle_search_file(self, payload: Dict[str, Any]):
        """Handle EventBus file search request."""
        pattern = payload.get('pattern', '')
        request_id = payload.get('request_id', '')
        
        results = self.search_files(pattern)
        
        if self.event_bus:
            self.event_bus.publish('codebase.search.file.response', {
                'success': True,
                'results': results,
                'pattern': pattern,
                'request_id': request_id
            })
    
    def _handle_get_symbols(self, payload: Dict[str, Any]):
        """Handle EventBus get symbols request."""
        file_path = payload.get('file_path', '')
        request_id = payload.get('request_id', '')
        
        path = Path(file_path)
        if not path.is_absolute():
            path = self.root_path / path
        
        index = self._file_index.get(str(path))
        
        if self.event_bus:
            self.event_bus.publish('codebase.symbols.response', {
                'success': index is not None,
                'symbols': [s.to_dict() for s in index.symbols] if index else [],
                'file_path': str(path),
                'request_id': request_id
            })
    
    def _handle_get_context(self, payload: Dict[str, Any]):
        """Handle EventBus context request."""
        file_path = payload.get('file_path')
        focus_files = payload.get('focus_files', [])
        request_id = payload.get('request_id', '')
        
        if file_path:
            result = self.get_file_context(file_path)
        else:
            result = {
                'success': True,
                'context': self.get_repository_context(focus_files)
            }
        
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.context.response', result)
    
    def _handle_ast_analyze(self, payload: Dict[str, Any]):
        """Handle EventBus AST analysis request."""
        file_path = payload.get('file_path', '')
        request_id = payload.get('request_id', '')
        
        result = self.get_file_context(file_path, include_imports=True, include_symbols=True)
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.ast.analyze.response', result)
    
    def _handle_edit_apply(self, payload: Dict[str, Any]):
        """Handle EventBus edit apply request."""
        file_path = payload.get('file_path', '')
        old_text = payload.get('old_text', '')
        new_text = payload.get('new_text', '')
        create_backup = payload.get('create_backup', True)
        request_id = payload.get('request_id', '')
        
        result = self.apply_edit(file_path, old_text, new_text, create_backup)
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.edit.apply.response', result)
    
    def _handle_edit_preview(self, payload: Dict[str, Any]):
        """Handle EventBus edit preview request."""
        file_path = payload.get('file_path', '')
        old_text = payload.get('old_text', '')
        new_text = payload.get('new_text', '')
        request_id = payload.get('request_id', '')
        
        result = self.preview_edit(file_path, old_text, new_text)
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.edit.preview.response', result)
    
    def _handle_edit_rollback(self, payload: Dict[str, Any]):
        """Handle EventBus edit rollback request."""
        backup_path = payload.get('backup_path', '')
        request_id = payload.get('request_id', '')
        
        result = self.rollback_edit(backup_path)
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.edit.rollback.response', result)
    
    def _handle_index_rebuild(self, payload: Dict[str, Any]):
        """Handle EventBus index rebuild request."""
        request_id = payload.get('request_id', '')
        
        result = self.build_index(force_rebuild=True)
        result['request_id'] = request_id
        
        if self.event_bus:
            self.event_bus.publish('codebase.index.rebuild.response', result)
    
    def _handle_index_status(self, payload: Dict[str, Any]):
        """Handle EventBus index status request."""
        request_id = payload.get('request_id', '')
        
        result = self.get_index_status()
        result['request_id'] = request_id
        result['success'] = True
        
        if self.event_bus:
            self.event_bus.publish('codebase.index.status.response', result)


# Singleton instance
_introspector_instance: Optional[CodebaseIntrospector] = None


def get_codebase_introspector(event_bus=None) -> CodebaseIntrospector:
    """Get or create the singleton CodebaseIntrospector instance."""
    global _introspector_instance
    if _introspector_instance is None:
        _introspector_instance = CodebaseIntrospector(event_bus)
    elif event_bus is not None and _introspector_instance.event_bus is None:
        _introspector_instance.event_bus = event_bus
        _introspector_instance._subscribe_to_events()
    return _introspector_instance


def get_codebase_context(focus_files: List[str] = None) -> str:
    """Convenience function to get repository context."""
    introspector = get_codebase_introspector()
    if not introspector._initialized:
        introspector.build_index()
    return introspector.get_repository_context(focus_files)
