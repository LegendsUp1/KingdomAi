# =============================================================================
# SOTA 2025: EARLY LOGGING SUPPRESSION - Must run FIRST before any imports
# =============================================================================
# Suppress verbose third-party loggers IMMEDIATELY before they spam console.
# This must happen before ANY other imports that might trigger logging.
# =============================================================================
import logging as _logging

# Suppress noisy loggers immediately
for _noisy_logger in [
    "qiskit", "qiskit.transpiler", "qiskit.passmanager", "qiskit.compiler",
    "qiskit.circuit", "qiskit.primitives", "qiskit.transpiler.passes",
    "qiskit.transpiler.passes.basis", "qiskit.transpiler.passes.basis.basis_translator",
    "qiskit_ibm_provider", "qiskit_aer", "urllib3", "websockets", "asyncio",
    "aiohttp", "ccxt", "httpx", "httpcore", "PIL", "tensorflow", "torch",
    "transformers", "web3", "eth_utils", "setuptools", "pkg_resources",
]:
    _logging.getLogger(_noisy_logger).setLevel(_logging.WARNING)
del _noisy_logger

# =============================================================================
# SOTA 2026: SILENCE ALSA ERRORS - Must run FIRST before any audio imports
# =============================================================================
# ALSA (Advanced Linux Sound Architecture) spams stderr with errors in WSL.
# These are C-level errors that bypass Python logging. We suppress them by
# redirecting ALSA's error handler to a null function using ctypes.
# =============================================================================
import os
import sys

def _silence_alsa_errors():
    """Silence ALSA lib errors that spam logs in WSL/Linux environments."""
    try:
        # Only apply on Linux/WSL
        if sys.platform != 'linux':
            return
        
        import ctypes
        from ctypes import CFUNCTYPE, c_char_p, c_int
        
        # Define the ALSA error handler function type
        ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
        
        # Create a no-op error handler
        def _alsa_error_handler(filename, line, function, err, fmt):
            pass  # Silently ignore all ALSA errors
        
        # Keep reference to prevent garbage collection
        _alsa_error_handler_func = ERROR_HANDLER_FUNC(_alsa_error_handler)
        
        # Try to load libasound and set our error handler
        try:
            asound = ctypes.cdll.LoadLibrary('libasound.so.2')
            asound.snd_lib_error_set_handler(_alsa_error_handler_func)
        except OSError:
            # libasound not available, try alternative
            try:
                asound = ctypes.cdll.LoadLibrary('libasound.so')
                asound.snd_lib_error_set_handler(_alsa_error_handler_func)
            except OSError:
                pass  # No ALSA library found, nothing to silence
        
        # Store reference globally to prevent GC
        globals()['_alsa_error_handler_func'] = _alsa_error_handler_func
        
    except Exception:
        pass  # Any error, just continue - audio will still work

# Apply ALSA silencing immediately
_silence_alsa_errors()

# Also set environment variable to help suppress ALSA messages
os.environ['ALSA_CARD'] = 'default'
os.environ['AUDIODEV'] = 'default'

# CRITICAL FIX: Remove problematic pynvml finder that causes TypeError with Python 3.10+
# This must run before any other imports to prevent "unexpected keyword argument 'path'" errors
_finders_to_remove = []
for finder in sys.meta_path:
    if finder.__class__.__name__ == 'PynvmlFinder':
        _finders_to_remove.append(finder)
for finder in _finders_to_remove:
    try:
        sys.meta_path.remove(finder)
    except ValueError:
        pass
del _finders_to_remove

# =============================================================================
# SOTA 2026 FIX: JAX/ml_dtypes/TensorFlow compatibility guard
# =============================================================================
# Problem: JAX requires specific ml_dtypes version with float8_e3m4, float8_e4m3b11, etc.
# Mismatched versions cause AttributeError crashes on import.
# Solution: Patch ml_dtypes with stub attributes before JAX/TensorFlow import them.
# =============================================================================
def _patch_ml_dtypes():
    """Patch ml_dtypes to prevent AttributeError on missing types."""
    try:
        import ml_dtypes
        # List of ALL types that different JAX/TensorFlow versions may expect
        stub_types = [
            # Float8 types
            'float8_e3m4', 'float8_e4m3', 'float8_e4m3b11', 'float8_e4m3b11fnuz',
            'float8_e4m3fn', 'float8_e4m3fnuz', 'float8_e5m2', 'float8_e5m2fnuz',
            'float8_e8m0fnu', 'float4_e2m1fn', 'float6_e2m3fn', 'float6_e3m2fn',
            # Integer types (int2, int4, uint2, uint4)
            'int2', 'int4', 'uint2', 'uint4',
            # Additional types
            'bfloat16', 'finfo', 'iinfo'
        ]
        # Create stub class for missing types
        class DTypeStub:
            """Stub for missing dtype - prevents AttributeError"""
            dtype = None
            def __init__(self, *args, **kwargs): pass
            def __repr__(self): return '<DTypeStub>'
        
        for attr in stub_types:
            if not hasattr(ml_dtypes, attr):
                setattr(ml_dtypes, attr, DTypeStub)
    except ImportError:
        pass  # ml_dtypes not installed, no patching needed
    except Exception:
        pass  # Any other error, continue without patching

# Apply the patch immediately
_patch_ml_dtypes()

# =============================================================================
# SOTA 2026: AGGRESSIVE JAX BLOCK - Environment has incompatible versions
# =============================================================================
# The environment has broken JAX/ml_dtypes. Block JAX entirely before it crashes.
# This is applied BEFORE any other imports to prevent cascade failures.
# =============================================================================
# JAX compatibility check - NumPy dtypes patch in sitecustomize.py fixes ml_dtypes issues
_JAX_BLOCKED = False
_jax_enabled = os.environ.get("KINGDOM_ENABLE_JAX", "1").strip().lower() in {"1", "true", "yes"}
if sys.platform.startswith("win") and not _jax_enabled:
    _JAX_BLOCKED = True
    import logging as _logging
    _logging.info("ℹ️ JAX probe skipped on Windows (KINGDOM_ENABLE_JAX=0)")
else:
    try:
        # Test if JAX can import successfully with NumPy dtypes patch
        import jax._src.dtypes
        import logging as _logging
        _logging.info("[OK] JAX loaded successfully - NumPy dtypes patch working")
    except (ImportError, AttributeError, ModuleNotFoundError) as e:
        # JAX not installed or still has issues
        _JAX_BLOCKED = True
        import logging as _logging
        _logging.warning(f"⚠️ JAX not available (optional): {e}")
    except Exception as e:
        _JAX_BLOCKED = True
        import logging as _logging
        _logging.warning(f"⚠️ JAX import failed (optional): {e}")

# =============================================================================
# SOTA 2026 FIX: Block TensorFlow/JAX imports if they would crash
# =============================================================================
# If the environment has broken JAX/TensorFlow, block their imports gracefully
# rather than letting them crash the entire application.
# =============================================================================
class _BlockedModuleLoader:
    """Import hook that blocks problematic modules and returns a stub."""
    
    BLOCKED_MODULES = set()  # Will be populated if we detect broken installs
    
    def find_module(self, fullname, path=None):
        if fullname in self.BLOCKED_MODULES or any(fullname.startswith(m + '.') for m in self.BLOCKED_MODULES):
            return self
        return None
    
    def find_spec(self, fullname, path=None, target=None):
        """Python 3.4+ MetaPathFinder protocol method."""
        if fullname in self.BLOCKED_MODULES or any(fullname.startswith(m + '.') for m in self.BLOCKED_MODULES):
            from importlib.machinery import ModuleSpec
            return ModuleSpec(fullname, loader=None)  # Use None loader, handle in load_module
        return None
    
    def create_module(self, spec):
        """Create a stub module."""
        return None  # Use default module creation
    
    def exec_module(self, module):
        """Execute (no-op for stub modules)."""
        pass
    
    def load_module(self, fullname):
        import types
        import logging
        logging.warning(f"⚠️ Module '{fullname}' blocked due to compatibility issues")
        mod = types.ModuleType(fullname)
        mod.__file__ = '<blocked>'
        mod.__loader__ = self
        mod.__path__ = []
        sys.modules[fullname] = mod
        return mod

# Test if JAX import would crash
def _test_jax_compatibility():
    """Test if JAX can be imported without crashing."""
    try:
        # Try importing jax core - this is what triggers ml_dtypes issues
        import jax._src.dtypes
        return True
    except (ImportError, AttributeError, ModuleNotFoundError):
        return False
    except Exception:
        return False

# Apply NumPy _ARRAY_API patch before importing ml_dtypes
try:
    import types
    import sys
    import importlib.abc
    import importlib.machinery

    class _NumpyTopLevelPatchFinder(importlib.abc.MetaPathFinder):
        """Set numpy._ARRAY_API at the very start of numpy load, before submodules run."""
        
        def __init__(self):
            self._patched = False

        def find_spec(self, fullname, path=None, target=None):
            if fullname != "numpy":
                return None
            
            # Avoid recursion - only patch once
            if self._patched:
                return None
            
            self._patched = True
            
            # Find numpy spec using other finders
            for f in sys.meta_path:
                if f is self:
                    continue
                spec = f.find_spec(fullname, path, target) if hasattr(f, 'find_spec') else None
                if spec is not None and spec.loader is not None:
                    # Wrap the loader to patch after import
                    original_loader = spec.loader
                    
                    class PatchingLoader:
                        def __init__(self, original):
                            self.original = original
                        
                        def create_module(self, spec):
                            return self.original.create_module(spec) if hasattr(self.original, 'create_module') else None
                        
                        def exec_module(self, module):
                            # Execute original module load
                            if hasattr(self.original, 'exec_module'):
                                self.original.exec_module(module)
                            # Patch immediately after load
                            if not hasattr(module, '_ARRAY_API'):
                                module._ARRAY_API = True
                    
                    spec.loader = PatchingLoader(original_loader)
                    return spec
            
            return None

    # Insert the patch finder at the beginning of meta_path
    sys.meta_path.insert(0, _NumpyTopLevelPatchFinder())
except Exception:
    pass

# Only block if we detect the environment is broken
_blocked_loader = _BlockedModuleLoader()
try:
    # Quick test - try to import ml_dtypes and check for required attributes
    import ml_dtypes
    _required_attrs = ['float8_e4m3fn', 'float8_e5m2']
    _missing = [a for a in _required_attrs if not hasattr(ml_dtypes, a)]
    if _missing:
        # Environment has broken ml_dtypes, block jax to prevent cascade failures
        _blocked_loader.BLOCKED_MODULES.add('jax')
        sys.meta_path.insert(0, _blocked_loader)
except ImportError:
    pass  # ml_dtypes not installed
except Exception:
    pass  # Continue without blocking

# =============================================================================
# SOTA 2026 FIX: TensorFlow compatibility patch
# =============================================================================
# TensorFlow 2.16+ moved __version__ to tf.version.VERSION and requires tf-keras.
# Patch __version__ if missing so downstream code can do `import tensorflow; tf.__version__`.
# =============================================================================
try:
    import tensorflow as _tf
    if not hasattr(_tf, '__version__'):
        _tf.__version__ = getattr(
            getattr(_tf, 'version', None), 'VERSION',
            '2.19.0'  # Safe fallback
        )
except ImportError:
    pass  # TensorFlow not installed — fine
except Exception:
    pass  # Any other TF issue — ignore at init time

# =============================================================================
# SOTA 2025: Centralized Logging Configuration
# =============================================================================
# Import kingdom_logging to configure the logging system early.
# This reduces terminal clutter by:
# - Only showing WARNING+ on console
# - Logging DEBUG+ to files
# - Rate-limiting repetitive API errors
# - Using structured JSON format for file logs
# =============================================================================
try:
    from core import kingdom_logging  # Auto-configures on import
except ImportError:
    pass  # Logging will use defaults
