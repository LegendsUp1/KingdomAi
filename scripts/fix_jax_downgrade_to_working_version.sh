#!/bin/bash
# 2025 STATE-OF-THE-ART FIX: Downgrade to JAX 0.6.0 (last stable CUDA version)
# Based on GitHub issues #28929 and #30050

set -e

echo "🔧 JAX CUDA FIX - 2025 State-of-the-Art Solution"
echo "=================================================="
echo ""
echo "Issue: JAX 0.6.1+ has a bug loading CUDA libraries in some environments"
echo "Solution: Downgrade to JAX 0.6.0 (confirmed working version)"
echo ""

# Uninstall current JAX
echo "1. Uninstalling JAX 0.6.2..."
pip uninstall -y jax jaxlib jax-cuda12-plugin jax-cuda12-pjrt

# Install working version
echo ""
echo "2. Installing JAX 0.6.0 with CUDA 12 support..."
pip install "jax[cuda12]==0.6.0" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html

# Test
echo ""
echo "3. Testing GPU detection..."
python3 << 'TESTEOF'
import jax
print(f"✅ JAX version: {jax.__version__}")
print(f"✅ Devices: {jax.devices()}")

devices = jax.devices()
has_gpu = any('gpu' in str(d).lower() or 'cuda' in str(d).lower() for d in devices)

if has_gpu:
    print("\n🎉 SUCCESS! GPU IS WORKING!")
    import jax.numpy as jnp
    x = jnp.ones((1000, 1000))
    y = jnp.dot(x, x)
    print(f"✅ GPU computation test passed!")
    print(f"   Device: {y.device()}")
else:
    print("\n⚠️  Still using CPU")
    print("This may require additional WSL2 configuration")
TESTEOF

echo ""
echo "=================================================="
echo "If GPU still not detected, JAX might need system CUDA toolkit:"
echo "  sudo apt-get install cuda-toolkit-12-4"
