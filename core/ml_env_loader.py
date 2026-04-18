#!/usr/bin/env python3
"""
ML Environment Package Loader for Kingdom AI
Loads JAX and other ML packages from the ML-specific virtual environment
"""

import sys
import os
from pathlib import Path

def load_ml_packages():
    """Load ML packages from kingdom-ai-ml environment"""
    ml_env_paths = [
        "/root/miniconda3/envs/kingdom-ai-ml/lib/python3.10/site-packages",
        "/root/miniconda3/envs/kingdom-ultimate/lib/python3.10/site-packages",
    ]
    
    for ml_path in ml_env_paths:
        if os.path.exists(ml_path) and ml_path not in sys.path:
            sys.path.insert(0, ml_path)
            print(f"✅ Added ML environment to path: {ml_path}")
    
    # Now try importing JAX
    try:
        import jax
        import jax.numpy as jnp
        print(f"✅ JAX {jax.__version__} loaded from ML environment")
        return True
    except ImportError as e:
        print(f"⚠️ JAX not available: {e}")
        return False

# Auto-load on import
load_ml_packages()
