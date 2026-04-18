#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Codebase Indexer for ThothAI

This module provides codebase indexing and querying capabilities so that
ThothAI can understand and answer questions about its own codebase.

Features:
- Indexes all Python files in the Kingdom AI project
- Extracts classes, functions, and their docstrings
- Provides semantic search over the codebase
- Enables hot reload detection for code changes
- Integrates with Redis Quantum Nexus for caching
"""

import os
import ast
import json
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger('KingdomAI.CodebaseIndexer')

# Redis connection for caching
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - codebase index will not be persisted")


@dataclass
class CodeElement:
    """Represents a code element (class, function, etc.)"""
    name: str
    element_type: str  # 'class', 'function', 'method', 'module'
    file_path: str
    line_number: int
    docstring: Optional[str]
    signature: Optional[str]
    parent_class: Optional[str]
    decorators: List[str]
    imports: List[str]
    last_modified: float


@dataclass
class FileIndex:
    """Index for a single file"""
    file_path: str
    file_hash: str
    last_indexed: float
    elements: List[CodeElement]
    module_docstring: Optional[str]
    imports: List[str]
    classes: List[str]
    functions: List[str]


class CodebaseIndexer:
    """
    Indexes the Kingdom AI codebase for ThothAI to query.
    
    Provides semantic search and code analysis capabilities
    so the AI can answer questions about its own codebase.
    """
    
    # Directories to skip during indexing
    SKIP_DIRS = {
        '__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules',
        '.idea', '.vscode', 'build', 'dist', 'egg-info', '.eggs',
        'creation_env', 'kingdom_ai/venv', '.cursor'
    }
    
    # File patterns to skip
    SKIP_FILES = {
        '__init__.py',  # Usually empty or just imports
    }
    
    def __init__(self, project_root: str = None, event_bus=None):
        """Initialize the codebase indexer.
        
        Args:
            project_root: Root directory of the project to index
            event_bus: Event bus for publishing updates
        """
        self.project_root = project_root or self._find_project_root()
        self.event_bus = event_bus
        self.index: Dict[str, FileIndex] = {}
        self.element_index: Dict[str, List[CodeElement]] = {}  # name -> elements
        self.redis_client = None
        self._last_full_index = 0
        self._watching = False
        
        # Connect to Redis for caching
        self._init_redis()
        
        logger.info(f"CodebaseIndexer initialized for: {self.project_root}")
    
    def _find_project_root(self) -> str:
        """Find the Kingdom AI project root directory."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.isdir(repo_root):
            return repo_root
        return os.getcwd()
    
    def _init_redis(self):
        """Initialize Redis connection for caching the index."""
        if not REDIS_AVAILABLE:
            return
            
        try:
            redis_password = (
                os.getenv('REDIS_PASSWORD') or 
                os.getenv('REDIS_QUANTUM_NEXUS_PASSWORD') or 
                'QuantumNexus2025'
            )
            
            self.redis_client = redis.Redis(
                host='localhost',
                port=6380,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("✅ Connected to Redis Quantum Nexus for codebase index caching")
            
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} - using in-memory index only")
            self.redis_client = None
    
    def _compute_file_hash(self, file_path: str) -> str:
        """Compute hash of file contents for change detection."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _should_skip_path(self, path: str) -> bool:
        """Check if a path should be skipped during indexing."""
        path_parts = Path(path).parts
        
        for skip_dir in self.SKIP_DIRS:
            if skip_dir in path_parts:
                return True
        
        return False
    
    def _extract_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature from AST node."""
        args = []
        
        # Regular arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except:
                    pass
            args.append(arg_str)
        
        # *args
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        
        # **kwargs
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        
        # Return type
        return_type = ""
        if node.returns:
            try:
                return_type = f" -> {ast.unparse(node.returns)}"
            except:
                pass
        
        return f"def {node.name}({', '.join(args)}){return_type}"
    
    def _extract_decorators(self, node) -> List[str]:
        """Extract decorator names from a node."""
        decorators = []
        for dec in node.decorator_list:
            try:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        decorators.append(dec.func.id)
                    elif isinstance(dec.func, ast.Attribute):
                        decorators.append(dec.func.attr)
            except:
                pass
        return decorators
    
    def _parse_file(self, file_path: str) -> Optional[FileIndex]:
        """Parse a Python file and extract code elements."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            elements = []
            imports = []
            classes = []
            functions = []
            module_docstring = ast.get_docstring(tree)
            
            rel_path = os.path.relpath(file_path, self.project_root)
            file_mtime = os.path.getmtime(file_path)
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            
            # Extract top-level classes and functions
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    class_element = CodeElement(
                        name=node.name,
                        element_type='class',
                        file_path=rel_path,
                        line_number=node.lineno,
                        docstring=ast.get_docstring(node),
                        signature=f"class {node.name}",
                        parent_class=None,
                        decorators=self._extract_decorators(node),
                        imports=imports,
                        last_modified=file_mtime
                    )
                    elements.append(class_element)
                    
                    # Extract methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_element = CodeElement(
                                name=item.name,
                                element_type='method',
                                file_path=rel_path,
                                line_number=item.lineno,
                                docstring=ast.get_docstring(item),
                                signature=self._extract_signature(item),
                                parent_class=node.name,
                                decorators=self._extract_decorators(item),
                                imports=[],
                                last_modified=file_mtime
                            )
                            elements.append(method_element)
                
                elif isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                    func_element = CodeElement(
                        name=node.name,
                        element_type='function',
                        file_path=rel_path,
                        line_number=node.lineno,
                        docstring=ast.get_docstring(node),
                        signature=self._extract_signature(node),
                        parent_class=None,
                        decorators=self._extract_decorators(node),
                        imports=imports,
                        last_modified=file_mtime
                    )
                    elements.append(func_element)
            
            return FileIndex(
                file_path=rel_path,
                file_hash=self._compute_file_hash(file_path),
                last_indexed=time.time(),
                elements=elements,
                module_docstring=module_docstring,
                imports=imports,
                classes=classes,
                functions=functions
            )
            
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error parsing {file_path}: {e}")
            return None
    
    def index_project(self, force: bool = False) -> Dict[str, Any]:
        """Index the entire project.
        
        Args:
            force: Force re-indexing even if cache is valid
            
        Returns:
            dict: Index statistics
        """
        start_time = time.time()
        files_indexed = 0
        files_skipped = 0
        total_elements = 0
        
        logger.info(f"Starting codebase indexing of {self.project_root}")
        
        for root, dirs, files in os.walk(self.project_root):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            
            if self._should_skip_path(root):
                continue
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                    
                if file in self.SKIP_FILES:
                    files_skipped += 1
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_root)
                
                # Check if file needs re-indexing
                if not force and rel_path in self.index:
                    current_hash = self._compute_file_hash(file_path)
                    if self.index[rel_path].file_hash == current_hash:
                        files_skipped += 1
                        continue
                
                # Parse and index file
                file_index = self._parse_file(file_path)
                if file_index:
                    self.index[rel_path] = file_index
                    files_indexed += 1
                    total_elements += len(file_index.elements)
                    
                    # Update element index for fast lookups
                    for element in file_index.elements:
                        if element.name not in self.element_index:
                            self.element_index[element.name] = []
                        self.element_index[element.name].append(element)
        
        self._last_full_index = time.time()
        elapsed = time.time() - start_time
        
        stats = {
            'files_indexed': files_indexed,
            'files_skipped': files_skipped,
            'total_files': len(self.index),
            'total_elements': total_elements,
            'elapsed_seconds': elapsed
        }
        
        logger.info(f"✅ Codebase indexed: {files_indexed} files, {total_elements} elements in {elapsed:.2f}s")
        
        # Cache to Redis
        self._cache_to_redis()
        
        # Publish update event
        if self.event_bus:
            self.event_bus.publish('codebase.indexed', stats)
        
        return stats
    
    def _cache_to_redis(self):
        """Cache the index to Redis."""
        if not self.redis_client:
            return
            
        try:
            # Store index metadata
            index_data = {
                'last_indexed': self._last_full_index,
                'total_files': len(self.index),
                'project_root': self.project_root
            }
            self.redis_client.hset('kingdom:codebase:metadata', mapping=index_data)
            
            # Store element count for quick stats
            element_count = sum(len(fi.elements) for fi in self.index.values())
            self.redis_client.set('kingdom:codebase:element_count', element_count)
            
            logger.debug("Codebase index cached to Redis")
            
        except Exception as e:
            logger.warning(f"Failed to cache index to Redis: {e}")
    
    def search(self, query: str, element_type: str = None, limit: int = 20) -> List[CodeElement]:
        """Search the codebase index.
        
        Args:
            query: Search query (searches names and docstrings)
            element_type: Filter by element type ('class', 'function', 'method')
            limit: Maximum number of results
            
        Returns:
            List of matching CodeElement objects
        """
        results = []
        query_lower = query.lower()
        
        for file_index in self.index.values():
            for element in file_index.elements:
                # Filter by type if specified
                if element_type and element.element_type != element_type:
                    continue
                
                # Check name match
                if query_lower in element.name.lower():
                    results.append((2, element))  # Higher score for name match
                    continue
                
                # Check docstring match
                if element.docstring and query_lower in element.docstring.lower():
                    results.append((1, element))  # Lower score for docstring match
        
        # Sort by score and return elements
        results.sort(key=lambda x: x[0], reverse=True)
        return [elem for _, elem in results[:limit]]
    
    def find_element(self, name: str) -> List[CodeElement]:
        """Find elements by exact name.
        
        Args:
            name: Exact name to find
            
        Returns:
            List of matching elements
        """
        return self.element_index.get(name, [])
    
    def get_class_info(self, class_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a class.
        
        Args:
            class_name: Name of the class
            
        Returns:
            Dictionary with class details or None
        """
        elements = self.find_element(class_name)
        class_elements = [e for e in elements if e.element_type == 'class']
        
        if not class_elements:
            return None
        
        element = class_elements[0]
        
        # Find all methods of this class
        methods = []
        for file_index in self.index.values():
            for elem in file_index.elements:
                if elem.parent_class == class_name:
                    methods.append({
                        'name': elem.name,
                        'signature': elem.signature,
                        'docstring': elem.docstring,
                        'decorators': elem.decorators,
                        'line_number': elem.line_number
                    })
        
        return {
            'name': element.name,
            'file_path': element.file_path,
            'line_number': element.line_number,
            'docstring': element.docstring,
            'decorators': element.decorators,
            'methods': methods,
            'method_count': len(methods)
        }
    
    def get_file_summary(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get summary of a file.
        
        Args:
            file_path: Relative path to the file
            
        Returns:
            Dictionary with file summary or None
        """
        file_index = self.index.get(file_path)
        if not file_index:
            return None
        
        return {
            'file_path': file_index.file_path,
            'module_docstring': file_index.module_docstring,
            'imports': file_index.imports,
            'classes': file_index.classes,
            'functions': file_index.functions,
            'element_count': len(file_index.elements),
            'last_indexed': datetime.fromtimestamp(file_index.last_indexed).isoformat()
        }
    
    def get_project_stats(self) -> Dict[str, Any]:
        """Get overall project statistics.
        
        Returns:
            Dictionary with project stats
        """
        total_classes = 0
        total_functions = 0
        total_methods = 0
        
        for file_index in self.index.values():
            for element in file_index.elements:
                if element.element_type == 'class':
                    total_classes += 1
                elif element.element_type == 'function':
                    total_functions += 1
                elif element.element_type == 'method':
                    total_methods += 1
        
        return {
            'project_root': self.project_root,
            'total_files': len(self.index),
            'total_classes': total_classes,
            'total_functions': total_functions,
            'total_methods': total_methods,
            'total_elements': total_classes + total_functions + total_methods,
            'last_indexed': datetime.fromtimestamp(self._last_full_index).isoformat() if self._last_full_index else None
        }
    
    def get_context_for_query(self, query: str, max_context_size: int = 4000) -> str:
        """Get relevant code context for an AI query about the codebase.
        
        Args:
            query: The user's query about the codebase
            max_context_size: Maximum characters to return
            
        Returns:
            Formatted context string for the AI
        """
        # Search for relevant elements
        results = self.search(query, limit=10)
        
        if not results:
            return f"No code elements found matching '{query}'. The Kingdom AI codebase has {len(self.index)} files indexed."
        
        context_parts = [f"## Kingdom AI Codebase - Relevant Code for '{query}'\n"]
        context_parts.append(f"Project: {self.project_root}\n")
        context_parts.append(f"Total indexed files: {len(self.index)}\n\n")
        
        current_size = sum(len(p) for p in context_parts)
        
        for element in results:
            element_context = f"""### {element.element_type.title()}: {element.name}
File: {element.file_path} (line {element.line_number})
Signature: {element.signature or 'N/A'}
{f'Parent class: {element.parent_class}' if element.parent_class else ''}
{f'Decorators: {", ".join(element.decorators)}' if element.decorators else ''}

Docstring:
{element.docstring or 'No docstring available'}

---
"""
            if current_size + len(element_context) > max_context_size:
                break
            
            context_parts.append(element_context)
            current_size += len(element_context)
        
        return ''.join(context_parts)


# Global singleton instance
_indexer_instance: Optional[CodebaseIndexer] = None


def get_codebase_indexer(project_root: str = None, event_bus=None) -> CodebaseIndexer:
    """Get or create the global codebase indexer instance.
    
    Args:
        project_root: Root directory of the project
        event_bus: Event bus for publishing updates
        
    Returns:
        CodebaseIndexer instance
    """
    global _indexer_instance
    
    if _indexer_instance is None:
        _indexer_instance = CodebaseIndexer(project_root, event_bus)
    
    return _indexer_instance
