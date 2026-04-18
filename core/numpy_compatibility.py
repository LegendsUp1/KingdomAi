#!/usr/bin/env python3
"""
NumPy Compatibility Patch for Kingdom AI
Handles numpy.core deprecation warnings and provides compatibility
"""

import logging
import warnings
import sys

logger = logging.getLogger(__name__)

def patch_numpy_compatibility():
    """Apply NumPy compatibility patches"""
    try:
        import numpy as np
        
        # Suppress numpy.core deprecation warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning, module='numpy')
        warnings.filterwarnings('ignore', category=FutureWarning, module='numpy')
        
        # Handle numpy.core -> numpy._core migration
        if hasattr(np, '_core'):
            # Create numpy.core alias for backward compatibility
            import types
            core_module = types.ModuleType('numpy.core')
            
            # Copy all attributes from numpy._core to numpy.core
            for attr_name in dir(np._core):
                if not attr_name.startswith('_'):
                    setattr(core_module, attr_name, getattr(np._core, attr_name))
            
            # Add to sys.modules for import compatibility
            sys.modules['numpy.core'] = core_module
            
            logger.info("✅ NumPy compatibility patch applied - numpy.core alias created")
        else:
            # Create numpy._core alias if it doesn't exist
            if hasattr(np, 'core'):
                import types
                _core_module = types.ModuleType('numpy._core')
                
                # Copy all attributes from numpy.core to numpy._core
                for attr_name in dir(np.core):
                    if not attr_name.startswith('_'):
                        setattr(_core_module, attr_name, getattr(np.core, attr_name))
                
                sys.modules['numpy._core'] = _core_module
                np._core = _core_module
                
                logger.info("✅ NumPy compatibility patch applied - numpy._core alias created")
        
        # Patch specific numpy.core imports
        original_import = __builtins__.__import__
        
        def patched_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'numpy.core' and hasattr(np, '_core'):
                return np._core
            elif name.startswith('numpy.core.'):
                # Redirect numpy.core.* to numpy._core.*
                redirected_name = name.replace('numpy.core', 'numpy._core')
                try:
                    return original_import(redirected_name, globals, locals, fromlist, level)
                except ImportError:
                    # Fall back to original if redirect fails
                    pass
            return original_import(name, globals, locals, fromlist, level)
        
        __builtins__.__import__ = patched_import
        
        logger.info("✅ NumPy import patch applied")
        return True
        
    except ImportError:
        logger.info("ℹ️ NumPy not available - no compatibility patches needed")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to apply NumPy compatibility patch: {e}")
        return False

# Auto-apply patch when imported
patch_numpy_compatibility()

# Export compatibility functions
def get_numpy_core():
    """Get numpy.core module (compatibility layer)"""
    try:
        import numpy as np
        if hasattr(np, '_core'):
            return np._core
        elif hasattr(np, 'core'):
            return np.core
        else:
            return np
    except ImportError:
        return None

def is_numpy_available():
    """Check if NumPy is available"""
    try:
        import numpy
        return True
    except ImportError:
        return False

logger.info("✅ NumPy compatibility module loaded")
