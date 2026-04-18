# Cryptography compatibility wrapper
import logging
import importlib.util
import sys

logger = logging.getLogger(__name__)

class RustExceptionsWrapper:
    '''Compatibility wrapper for cryptography.hazmat.bindings._rust.exceptions'''
    
    def __init__(self):
        # Define exception classes that might be needed
        self.UnsupportedAlgorithm = type('UnsupportedAlgorithm', (Exception,), {})
        self.AlreadyFinalized = type('AlreadyFinalized', (Exception,), {})
        self.NotYetFinalized = type('NotYetFinalized', (Exception,), {})
        self.AlreadyUpdated = type('AlreadyUpdated', (Exception,), {})
        self.InvalidTag = type('InvalidTag', (Exception,), {})
        
        logger.info("Initialized cryptography.hazmat.bindings._rust.exceptions wrapper")

# Create the wrapper instance
exceptions = RustExceptionsWrapper()

def patch_cryptography():
    '''Patch the cryptography module to use our compatibility wrapper'''
    
    # See if cryptography is imported
    if 'cryptography' not in sys.modules:
        logger.warning("Cryptography not imported yet, will apply patch when imported")
        return False
    
    # Get cryptography module
    crypto_module = sys.modules['cryptography']
    
    # Create the module structure if it doesn't exist
    if not hasattr(crypto_module, 'hazmat'):
        crypto_module.hazmat = type('hazmat', (), {})
    
    if not hasattr(crypto_module.hazmat, 'bindings'):
        crypto_module.hazmat.bindings = type('bindings', (), {})
    
    if not hasattr(crypto_module.hazmat.bindings, '_rust'):
        crypto_module.hazmat.bindings._rust = type('_rust', (), {})
    
    # Add our exceptions wrapper
    crypto_module.hazmat.bindings._rust.exceptions = exceptions
    
    # Also insert directly into sys.modules for import statements
    sys.modules['cryptography.hazmat.bindings._rust.exceptions'] = exceptions
    
    logger.info("Patched cryptography module with compatibility wrapper")
    return True

# Apply the patch immediately
patch_cryptography()

import importlib.abc
import importlib.machinery


class _CryptoCompatFinder(importlib.abc.MetaPathFinder):
    """Intercepts imports of the Rust-based cryptography exceptions module
    and returns our pure-Python wrapper instead."""

    def find_module(self, fullname, path=None):
        if fullname == 'cryptography.hazmat.bindings._rust.exceptions':
            return self
        return None

    def load_module(self, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]
        sys.modules[fullname] = exceptions
        return exceptions


sys.meta_path.insert(0, _CryptoCompatFinder())