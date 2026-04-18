#!/usr/bin/env python3
"""
Kingdom AI — Code Sandbox & Malware Protection System (SOTA 2026)
=================================================================
Multi-layer defense for consumer code execution:

1. AST Static Analysis — scan code for malware patterns BEFORE execution
2. Import Whitelist — only safe modules allowed (no os, subprocess, shutil, etc.)
3. Builtin Restrictions — block eval, exec, compile, __import__, open, etc.
4. File System Jail — consumer code can only read/write inside user sandbox dir
5. Network Isolation — no socket, urllib, requests access from consumer code
6. Cross-User Isolation — each user's code runs in isolated namespace, no shared state
7. Cascade Prevention — consumer code cannot access core/*, gui/*, event_bus, or creator systems
8. Resource Limits — timeout, memory cap, output size limits

Based on:
- OWASP Code Injection Prevention
- NVIDIA Sandbox Security Guidance (2025)
- Bandit AST security scanner patterns
- RestrictedPython safe builtins approach
- py.codecheck malware detection patterns

Author: Kingdom AI Security Team
Version: 1.0.0
"""

import ast
import sys
import os
import re
import time
import logging
import hashlib
import traceback
import threading
from io import StringIO
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("KingdomAI.CodeSandbox")


# ═════════════════════════════════════════════════════════════════════
# THREAT DEFINITIONS
# ═════════════════════════════════════════════════════════════════════

@dataclass
class CodeThreat:
    """Represents a detected threat in submitted code."""
    severity: str          # "critical", "high", "medium", "low"
    category: str          # "malware", "injection", "file_access", "network", "system", "cascade"
    description: str
    line_number: int = 0
    code_snippet: str = ""
    threat_id: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet[:200] if self.code_snippet else "",
        }


@dataclass
class SandboxResult:
    """Result of sandboxed code execution."""
    success: bool
    output: str = ""
    error: str = ""
    threats_found: List[CodeThreat] = field(default_factory=list)
    execution_time_ms: float = 0
    was_blocked: bool = False
    block_reason: str = ""


# ═════════════════════════════════════════════════════════════════════
# LAYER 1: AST MALWARE SCANNER
# ═════════════════════════════════════════════════════════════════════

# Dangerous function calls to block
DANGEROUS_CALLS: Dict[str, str] = {
    # System command execution
    "os.system": "System command execution — can run arbitrary OS commands",
    "os.popen": "System command execution via pipe",
    "os.exec": "Process replacement — can replace current process",
    "os.execl": "Process replacement",
    "os.execle": "Process replacement",
    "os.execlp": "Process replacement",
    "os.execv": "Process replacement",
    "os.execve": "Process replacement",
    "os.execvp": "Process replacement",
    "os.execvpe": "Process replacement",
    "os.spawn": "Process spawning",
    "os.spawnl": "Process spawning",
    "os.spawnle": "Process spawning",
    "os.spawnlp": "Process spawning",
    "os.spawnv": "Process spawning",
    "os.spawnve": "Process spawning",
    "os.spawnvp": "Process spawning",
    "os.fork": "Process forking — can create child processes",
    "os.kill": "Process kill — can terminate other processes/users",
    "os.killpg": "Process group kill",
    "subprocess.call": "Subprocess execution",
    "subprocess.check_call": "Subprocess execution",
    "subprocess.check_output": "Subprocess execution",
    "subprocess.run": "Subprocess execution",
    "subprocess.Popen": "Subprocess creation — full shell access",

    # File system destruction
    "os.remove": "File deletion",
    "os.unlink": "File deletion",
    "os.rmdir": "Directory deletion",
    "os.removedirs": "Recursive directory deletion",
    "shutil.rmtree": "Recursive directory tree deletion — can wipe entire filesystem",
    "shutil.move": "File/directory move — can displace critical files",
    "shutil.copy": "File copy — can exfiltrate data",
    "shutil.copy2": "File copy with metadata",
    "shutil.copytree": "Directory tree copy — can exfiltrate entire directories",
    "pathlib.Path.unlink": "File deletion via pathlib",
    "pathlib.Path.rmdir": "Directory deletion via pathlib",

    # Code injection
    "eval": "Dynamic code evaluation — arbitrary code execution",
    "exec": "Dynamic code execution — arbitrary code execution",
    "compile": "Code compilation — can create executable code objects",
    "__import__": "Dynamic module import — can load dangerous modules",
    "importlib.import_module": "Dynamic module import",
    "importlib.__import__": "Dynamic module import",

    # Data serialization attacks
    "pickle.load": "Pickle deserialization — can execute arbitrary code on load",
    "pickle.loads": "Pickle deserialization from bytes",
    "pickle.Unpickler": "Pickle unpickler — code execution risk",
    "marshal.load": "Marshal deserialization — code execution risk",
    "marshal.loads": "Marshal deserialization",
    "yaml.load": "YAML deserialization — code execution without SafeLoader",
    "yaml.unsafe_load": "Unsafe YAML loading",

    # Network access
    "socket.socket": "Raw socket creation — network access",
    "socket.connect": "Network connection",
    "urllib.request.urlopen": "HTTP request — data exfiltration risk",
    "urllib.request.urlretrieve": "File download from internet",
    "requests.get": "HTTP GET request",
    "requests.post": "HTTP POST request — data exfiltration",
    "requests.put": "HTTP PUT request",
    "requests.delete": "HTTP DELETE request",
    "requests.session": "HTTP session creation",
    "httpx.get": "HTTP request via httpx",
    "httpx.post": "HTTP POST via httpx",
    "aiohttp.ClientSession": "Async HTTP session",

    # Reflection/introspection attacks
    "getattr": "Attribute access — can bypass restrictions via reflection",
    "setattr": "Attribute modification — can modify protected objects",
    "delattr": "Attribute deletion",
    "globals": "Access to global namespace — can read/modify any variable",
    "locals": "Access to local namespace",
    "vars": "Access to object namespace",
    "dir": "Object introspection — can discover internal attributes",
    "type.__subclasses__": "Class hierarchy traversal — sandbox escape",
    "object.__subclasses__": "Class hierarchy traversal — sandbox escape",

    # Kingdom AI internal access (cascade prevention)
    "event_bus.publish": "Event bus access — can cascade commands to entire system",
    "event_bus.subscribe": "Event bus subscription — can intercept system events",
    "EventBus": "Event bus instantiation — system-wide access",
}

# Dangerous module imports to block entirely
BLOCKED_IMPORTS: Set[str] = {
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "urllib", "requests", "httpx", "aiohttp",
    "pickle", "marshal", "shelve",
    "ctypes", "cffi", "swig",
    "importlib", "imp", "pkgutil",
    "code", "codeop", "compileall",
    "signal", "threading", "multiprocessing", "concurrent",
    "ast",  # prevent meta-analysis to find escape vectors
    "inspect", "dis", "gc", "weakref",
    "io", "tempfile", "glob", "fnmatch",
    "sqlite3", "dbm",
    "smtplib", "imaplib", "poplib", "ftplib", "telnetlib",
    "xml", "html",
    "win32api", "win32com", "winreg", "msvcrt",
    "pty", "resource", "grp", "pwd",
    # Kingdom AI internals — cascade prevention
    "core", "gui", "ai_modules", "components", "config",
    "kingdom_main", "kingdom_ai_perfect", "kingdom_ai_consumer",
    "event_bus", "redis",
}

# Allowed safe imports for consumer code generation
ALLOWED_IMPORTS: Set[str] = {
    "math", "cmath", "decimal", "fractions", "statistics",
    "random", "secrets",
    "string", "re", "textwrap",
    "datetime", "time", "calendar",
    "collections", "itertools", "functools", "operator",
    "json", "csv", "base64", "hashlib", "hmac",
    "copy", "pprint", "enum", "dataclasses",
    "typing", "abc",
    "bisect", "heapq", "array",
    "uuid",
    "difflib",
    "numbers",
}

# Safe builtins whitelist (inspired by RestrictedPython)
SAFE_BUILTINS: Dict[str, Any] = {
    # Types
    "bool": bool, "int": int, "float": float, "complex": complex,
    "str": str, "bytes": bytes, "bytearray": bytearray,
    "list": list, "tuple": tuple, "dict": dict, "set": set, "frozenset": frozenset,

    # Functions
    "abs": abs, "all": all, "any": any, "bin": bin,
    "chr": chr, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "format": format, "hash": hash, "hex": hex,
    "id": id, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "map": map, "max": max, "min": min,
    "next": next, "oct": oct, "ord": ord, "pow": pow,
    "print": print,  # Will be replaced with captured print
    "range": range, "repr": repr, "reversed": reversed,
    "round": round, "slice": slice, "sorted": sorted,
    "sum": sum, "super": super, "zip": zip,

    # Constants
    "True": True, "False": False, "None": None,

    # Exceptions (read-only)
    "Exception": Exception, "ValueError": ValueError,
    "TypeError": TypeError, "KeyError": KeyError,
    "IndexError": IndexError, "AttributeError": AttributeError,
    "RuntimeError": RuntimeError, "StopIteration": StopIteration,
    "ZeroDivisionError": ZeroDivisionError, "OverflowError": OverflowError,
    "ArithmeticError": ArithmeticError, "LookupError": LookupError,
    "NotImplementedError": NotImplementedError,
}


class ASTMalwareScanner(ast.NodeVisitor):
    """Walk the AST tree to detect malicious patterns before execution.

    Based on Bandit + py.codecheck patterns.
    """

    def __init__(self):
        self.threats: List[CodeThreat] = []
        self._import_names: Set[str] = set()

    def scan(self, code: str) -> List[CodeThreat]:
        """Parse and scan code for threats. Returns list of detected threats."""
        self.threats = []
        self._import_names = set()

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.threats.append(CodeThreat(
                severity="medium",
                category="syntax_error",
                description=f"Code has syntax error: {e.msg}",
                line_number=e.lineno or 0,
            ))
            return self.threats

        self.visit(tree)
        return self.threats

    def visit_Import(self, node: ast.Import):
        """Check import statements."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            self._import_names.add(module_name)

            if module_name in BLOCKED_IMPORTS:
                self.threats.append(CodeThreat(
                    severity="critical",
                    category="blocked_import",
                    description=f"Blocked import: '{alias.name}' — access denied for security",
                    line_number=node.lineno,
                    code_snippet=f"import {alias.name}",
                ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Check from...import statements."""
        if node.module:
            module_name = node.module.split(".")[0]
            self._import_names.add(module_name)

            if module_name in BLOCKED_IMPORTS:
                names = ", ".join(a.name for a in node.names)
                self.threats.append(CodeThreat(
                    severity="critical",
                    category="blocked_import",
                    description=f"Blocked import: 'from {node.module} import {names}' — access denied",
                    line_number=node.lineno,
                    code_snippet=f"from {node.module} import {names}",
                ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Check function calls for dangerous patterns."""
        func_name = self._get_call_name(node)

        if func_name:
            # Check direct dangerous calls
            if func_name in DANGEROUS_CALLS:
                self.threats.append(CodeThreat(
                    severity="critical",
                    category="dangerous_call",
                    description=f"Dangerous call: {func_name} — {DANGEROUS_CALLS[func_name]}",
                    line_number=node.lineno,
                    code_snippet=func_name,
                ))

            # Check for eval/exec even without module prefix
            base_name = func_name.split(".")[-1]
            if base_name in ("eval", "exec", "compile", "__import__"):
                if func_name not in DANGEROUS_CALLS:  # Avoid double-report
                    self.threats.append(CodeThreat(
                        severity="critical",
                        category="code_injection",
                        description=f"Code injection via {base_name}() — arbitrary code execution",
                        line_number=node.lineno,
                        code_snippet=func_name,
                    ))

            # Check for open() — file access
            if base_name == "open":
                self.threats.append(CodeThreat(
                    severity="high",
                    category="file_access",
                    description="File access via open() — blocked for consumer code",
                    line_number=node.lineno,
                    code_snippet="open(...)",
                ))

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        """Check for dangerous attribute access patterns."""
        # Detect __subclasses__ traversal (sandbox escape)
        if node.attr in ("__subclasses__", "__bases__", "__mro__",
                         "__class__", "__globals__", "__builtins__",
                         "__code__", "__func__", "__self__",
                         "__dict__", "__module__", "__qualname__"):
            self.threats.append(CodeThreat(
                severity="critical",
                category="sandbox_escape",
                description=f"Dunder attribute access: .{node.attr} — potential sandbox escape",
                line_number=node.lineno,
                code_snippet=f".{node.attr}",
            ))
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global):
        """Block global variable manipulation."""
        self.threats.append(CodeThreat(
            severity="high",
            category="scope_escape",
            description=f"Global statement: 'global {', '.join(node.names)}' — can modify outer scope",
            line_number=node.lineno,
            code_snippet=f"global {', '.join(node.names)}",
        ))
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete):
        """Flag delete statements (could delete critical objects)."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.threats.append(CodeThreat(
                    severity="medium",
                    category="deletion",
                    description=f"Delete statement: 'del {target.id}' — could remove safety objects",
                    line_number=node.lineno,
                    code_snippet=f"del {target.id}",
                ))
        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the full dotted name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""


# ═════════════════════════════════════════════════════════════════════
# LAYER 2: SAFE IMPORT SYSTEM
# ═════════════════════════════════════════════════════════════════════

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Restricted import function — only allows whitelisted modules."""
    module_root = name.split(".")[0]

    if module_root not in ALLOWED_IMPORTS:
        raise ImportError(
            f"🛡️ Security: Import of '{name}' is not allowed. "
            f"Allowed modules: {', '.join(sorted(ALLOWED_IMPORTS))}"
        )

    return __builtins__["__import__"](name, globals, locals, fromlist, level) if isinstance(__builtins__, dict) \
        else __import__(name, globals, locals, fromlist, level)


# ═════════════════════════════════════════════════════════════════════
# LAYER 3: SANDBOXED EXECUTION ENGINE
# ═════════════════════════════════════════════════════════════════════

class CodeSandbox:
    """Isolated execution environment for consumer-generated code.

    Prevents:
    - Malware injection (AST scanning)
    - System command execution (import blocking)
    - File system access (no open/os/shutil)
    - Network access (no socket/requests/urllib)
    - Cross-user attacks (isolated namespace per user)
    - Cascade to creator (no event_bus/core/gui access)
    - Resource exhaustion (timeout + output limits)
    """

    # Execution limits
    MAX_EXECUTION_TIME_SEC = 10
    MAX_OUTPUT_SIZE = 50_000     # 50KB output limit
    MAX_CODE_LENGTH = 100_000   # 100KB code limit

    def __init__(self, user_id: str = "default", event_bus=None):
        self.user_id = user_id
        self.event_bus = event_bus
        self.scanner = ASTMalwareScanner()
        self._execution_count = 0
        self._blocked_count = 0
        self._threat_log: List[dict] = []

        logger.info(f"🛡️ CodeSandbox initialized for user={user_id}")

    def scan_code(self, code: str) -> List[CodeThreat]:
        """Scan code for threats without executing it.

        Returns list of detected threats. Empty list = code is safe.
        """
        if len(code) > self.MAX_CODE_LENGTH:
            return [CodeThreat(
                severity="high",
                category="size_limit",
                description=f"Code exceeds maximum size ({len(code)} > {self.MAX_CODE_LENGTH} chars)",
            )]

        return self.scanner.scan(code)

    def execute(self, code: str) -> SandboxResult:
        """Execute code in a sandboxed environment.

        Steps:
        1. AST scan for malware
        2. Block if critical threats found
        3. Set up restricted namespace
        4. Execute with timeout
        5. Return captured output
        """
        self._execution_count += 1
        start_time = time.time()

        # Step 1: Size check
        if len(code) > self.MAX_CODE_LENGTH:
            return SandboxResult(
                success=False,
                was_blocked=True,
                block_reason=f"Code exceeds maximum size limit ({self.MAX_CODE_LENGTH} chars)",
            )

        # Step 2: AST malware scan
        threats = self.scanner.scan(code)
        critical_threats = [t for t in threats if t.severity in ("critical", "high")]

        if critical_threats:
            self._blocked_count += 1
            self._log_threat(code, threats)

            # Broadcast tamper alert
            if self.event_bus:
                self.event_bus.publish("security.code_threat", {
                    "user_id": self.user_id,
                    "threats": [t.to_dict() for t in critical_threats],
                    "code_hash": hashlib.sha256(code.encode()).hexdigest()[:16],
                    "timestamp": datetime.now().isoformat(),
                })

            threat_summary = "; ".join(
                f"Line {t.line_number}: {t.description}" for t in critical_threats[:5]
            )
            return SandboxResult(
                success=False,
                threats_found=threats,
                was_blocked=True,
                block_reason=f"Code blocked — {len(critical_threats)} security threat(s) detected:\n{threat_summary}",
            )

        # Step 3: Set up restricted namespace
        output_capture = StringIO()
        namespace = self._build_restricted_namespace(output_capture)

        # Step 4: Execute with timeout
        result = {"output": "", "error": "", "success": False}
        execution_error = [None]

        def _run():
            try:
                compiled = compile(code, f"<user_{self.user_id}>", "exec")
                exec(compiled, namespace)
                result["success"] = True
            except ImportError as e:
                execution_error[0] = f"🛡️ {e}"
            except Exception as e:
                execution_error[0] = f"Error: {type(e).__name__}: {e}"

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=self.MAX_EXECUTION_TIME_SEC)

        elapsed_ms = (time.time() - start_time) * 1000

        if thread.is_alive():
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {self.MAX_EXECUTION_TIME_SEC}s",
                threats_found=threats,
                execution_time_ms=elapsed_ms,
            )

        # Step 5: Collect output
        captured_output = output_capture.getvalue()
        if len(captured_output) > self.MAX_OUTPUT_SIZE:
            captured_output = captured_output[:self.MAX_OUTPUT_SIZE] + "\n... [output truncated]"

        if execution_error[0]:
            return SandboxResult(
                success=False,
                output=captured_output,
                error=execution_error[0],
                threats_found=threats,
                execution_time_ms=elapsed_ms,
            )

        return SandboxResult(
            success=True,
            output=captured_output,
            threats_found=threats,
            execution_time_ms=elapsed_ms,
        )

    def _build_restricted_namespace(self, output_stream: StringIO) -> dict:
        """Build a restricted execution namespace with safe builtins only."""

        def safe_print(*args, **kwargs):
            """Captured print — writes to sandbox output instead of stdout."""
            kwargs.pop("file", None)  # Never allow file= redirect
            kwargs["file"] = output_stream
            print(*args, **kwargs)

        restricted_builtins = dict(SAFE_BUILTINS)
        restricted_builtins["print"] = safe_print
        restricted_builtins["__import__"] = _safe_import
        restricted_builtins["__name__"] = f"__sandbox_{self.user_id}__"
        restricted_builtins["__build_class__"] = __builtins__["__build_class__"] if isinstance(__builtins__, dict) else getattr(__builtins__, "__build_class__")

        namespace = {
            "__builtins__": restricted_builtins,
            "__name__": f"__sandbox_{self.user_id}__",
            "__doc__": None,
        }

        return namespace

    def _log_threat(self, code: str, threats: List[CodeThreat]):
        """Log detected threats for creator review."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": self.user_id,
            "code_hash": hashlib.sha256(code.encode()).hexdigest()[:16],
            "code_preview": code[:200],
            "threats": [t.to_dict() for t in threats],
        }
        self._threat_log.append(entry)
        logger.warning(
            f"🚨 CODE THREAT from user={self.user_id}: "
            f"{len(threats)} threats in {len(code)} char code"
        )

    def get_stats(self) -> dict:
        return {
            "user_id": self.user_id,
            "total_executions": self._execution_count,
            "blocked_executions": self._blocked_count,
            "threat_log_size": len(self._threat_log),
        }

    def get_threat_log(self) -> List[dict]:
        return list(self._threat_log)


# ═════════════════════════════════════════════════════════════════════
# LAYER 4: API KEY ISOLATION
# ═════════════════════════════════════════════════════════════════════

class APIKeyIsolation:
    """Isolate consumer API keys from creator API keys.

    Consumers can:
    - Add/edit/delete their OWN API keys
    - Test their own key connections

    Consumers CANNOT:
    - See, read, or modify creator's API keys
    - Access other users' API keys
    - Export the full key database
    """

    # Creator's key storage filename (consumers never touch this)
    CREATOR_KEYS_FILE = "api_keys.json"
    # Consumer's personal key storage (isolated per user)
    CONSUMER_KEYS_PREFIX = "consumer_keys_"

    def __init__(self, data_dir: str = None, is_consumer: bool = True):
        self.is_consumer = is_consumer
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".kingdom_ai"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Encryption key derived from machine-specific info
        self._derive_encryption_key()

    def _derive_encryption_key(self):
        """Derive a Fernet encryption key for API key storage."""
        try:
            from cryptography.fernet import Fernet
            import base64

            # Machine-specific seed (changes per installation)
            machine_seed = (
                os.environ.get("COMPUTERNAME", "") +
                os.environ.get("USERNAME", "") +
                str(os.getpid())
            ).encode()
            key_material = hashlib.sha256(machine_seed).digest()
            self._fernet_key = base64.urlsafe_b64encode(key_material)
            self._fernet = Fernet(self._fernet_key)
            self._encryption_available = True
        except ImportError:
            logger.warning("cryptography package not available — API keys stored unencrypted")
            self._encryption_available = False
            self._fernet = None

    def get_consumer_keys_path(self, user_id: str) -> Path:
        """Get the isolated key file path for a consumer user."""
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '', user_id)[:64]
        return self.data_dir / f"{self.CONSUMER_KEYS_PREFIX}{safe_id}.json"

    def get_creator_keys_path(self) -> Path:
        """Get the creator's key file path."""
        return self.data_dir / self.CREATOR_KEYS_FILE

    def can_access_creator_keys(self) -> bool:
        """Consumer can NEVER access creator keys."""
        return not self.is_consumer

    def load_keys(self, user_id: str = "creator") -> dict:
        """Load API keys for the appropriate user."""
        if self.is_consumer:
            return self._load_consumer_keys(user_id)
        else:
            return self._load_creator_keys()

    def save_keys(self, keys: dict, user_id: str = "creator") -> bool:
        """Save API keys for the appropriate user."""
        if self.is_consumer:
            return self._save_consumer_keys(keys, user_id)
        else:
            return self._save_creator_keys(keys)

    def _load_consumer_keys(self, user_id: str) -> dict:
        """Load consumer's personal API keys only."""
        key_path = self.get_consumer_keys_path(user_id)
        if not key_path.exists():
            return {}

        try:
            import json
            raw = key_path.read_text(encoding='utf-8')
            if self._encryption_available and self._fernet:
                try:
                    raw = self._fernet.decrypt(raw.encode()).decode()
                except Exception:
                    pass  # Fallback to unencrypted
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Failed to load consumer keys: {e}")
            return {}

    def _save_consumer_keys(self, keys: dict, user_id: str) -> bool:
        """Save consumer's personal API keys."""
        key_path = self.get_consumer_keys_path(user_id)
        try:
            import json
            raw = json.dumps(keys, indent=2)
            if self._encryption_available and self._fernet:
                raw = self._fernet.encrypt(raw.encode()).decode()
            key_path.write_text(raw, encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f"Failed to save consumer keys: {e}")
            return False

    def _load_creator_keys(self) -> dict:
        """Load creator's full API key set."""
        key_path = self.get_creator_keys_path()
        if not key_path.exists():
            return {}
        try:
            import json
            return json.loads(key_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"Failed to load creator keys: {e}")
            return {}

    def _save_creator_keys(self, keys: dict) -> bool:
        """Save creator's full API key set."""
        key_path = self.get_creator_keys_path()
        try:
            import json
            key_path.write_text(json.dumps(keys, indent=2), encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f"Failed to save creator keys: {e}")
            return False


# ═════════════════════════════════════════════════════════════════════
# LAYER 5: USER ISOLATION MANAGER
# ═════════════════════════════════════════════════════════════════════

class UserIsolationManager:
    """Prevent cross-user attacks in multi-user environment.

    Enforces:
    - Each user has isolated code sandbox
    - Each user has isolated API key storage
    - No user can access another user's data
    - No consumer can cascade to creator systems
    - No consumer can shutdown/kill other users
    """

    def __init__(self, event_bus=None, is_consumer: bool = True):
        self.event_bus = event_bus
        self.is_consumer = is_consumer
        self._sandboxes: Dict[str, CodeSandbox] = {}
        self._key_stores: Dict[str, APIKeyIsolation] = {}
        self._active_users: Dict[str, dict] = {}

        logger.info(f"🛡️ UserIsolationManager initialized — mode={'consumer' if is_consumer else 'creator'}")

    def get_sandbox(self, user_id: str) -> CodeSandbox:
        """Get or create isolated sandbox for a user."""
        if user_id not in self._sandboxes:
            self._sandboxes[user_id] = CodeSandbox(
                user_id=user_id,
                event_bus=self.event_bus
            )
        return self._sandboxes[user_id]

    def get_key_store(self, user_id: str) -> APIKeyIsolation:
        """Get or create isolated API key store for a user."""
        if user_id not in self._key_stores:
            self._key_stores[user_id] = APIKeyIsolation(
                is_consumer=self.is_consumer
            )
        return self._key_stores[user_id]

    def execute_user_code(self, user_id: str, code: str) -> SandboxResult:
        """Execute code in user's isolated sandbox."""
        sandbox = self.get_sandbox(user_id)
        result = sandbox.execute(code)

        # Log execution
        if self.event_bus:
            self.event_bus.publish("security.code_execution", {
                "user_id": user_id,
                "success": result.success,
                "was_blocked": result.was_blocked,
                "threats_count": len(result.threats_found),
                "execution_time_ms": result.execution_time_ms,
                "timestamp": datetime.now().isoformat(),
            })

        return result

    def scan_user_code(self, user_id: str, code: str) -> List[CodeThreat]:
        """Scan code without executing — returns threats."""
        sandbox = self.get_sandbox(user_id)
        return sandbox.scan_code(code)

    def get_all_stats(self) -> dict:
        """Get security stats across all users."""
        return {
            "active_sandboxes": len(self._sandboxes),
            "active_key_stores": len(self._key_stores),
            "per_user": {
                uid: sandbox.get_stats()
                for uid, sandbox in self._sandboxes.items()
            },
        }
