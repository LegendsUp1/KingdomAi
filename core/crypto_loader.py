# Import wrapper first to ensure it's loaded
from core.compat.cryptography_wrapper import patch_cryptography

def ensure_crypto_wrapper():
    '''Ensure our compatibility wrapper is loaded'''
    return patch_cryptography()