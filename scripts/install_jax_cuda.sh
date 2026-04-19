#!/bin/bash
# JAX CUDA Installation Script - 2025 Best Practices
# Based on official JAX documentation

echo "🚀 Installing JAX with CUDA support..."

# Detect CUDA version
if command -v nvidia-smi &> /dev/null; then
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}' | cut -d. -f1)
    echo "📍 Detected CUDA version: $CUDA_VERSION"
else
    echo "⚠️  nvidia-smi not found, defaulting to CUDA 12"
    CUDA_VERSION=12
fi

# Uninstall existing JAX
echo "🗑️  Removing old JAX installation..."
pip uninstall -y jax jaxlib jax-cuda12-plugin jax-cuda12-pjrt 2>/dev/null || true

# Install JAX with CUDA support from the correct repository
echo "📦 Installing JAX with CUDA support..."

if [ "$CUDA_VERSION" -ge 13 ] || [ "$CUDA_VERSION" -eq 12 ]; then
    # For CUDA 12.x (most common)
    echo "Installing JAX for CUDA 12..."
    pip install --upgrade "jax[cuda12]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
    
    # Alternative explicit installation
    if [ $? -ne 0 ]; then
        echo "Trying alternative installation method..."
        pip install --upgrade pip
        pip install --upgrade "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
    fi
else
    # Fallback to latest
    echo "Installing latest JAX with CUDA..."
    pip install --upgrade jax[cuda12] -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
fi

# Verify installation
echo ""
echo "🔍 Verifying JAX installation..."
python3 << 'PYEOF'
import jax
import sys

print(f"✅ JAX version: {jax.__version__}")
print(f"✅ JAX devices: {jax.devices()}")

# Check if GPU is available
devices = jax.devices()
has_gpu = any('gpu' in str(d).lower() or 'cuda' in str(d).lower() for d in devices)

if has_gpu:
    print("🎉 GPU support ENABLED!")
    print(f"GPU devices: {[d for d in devices if 'gpu' in str(d).lower() or 'cuda' in str(d).lower()]}")
else:
    print("⚠️  GPU support NOT enabled - using CPU")
    print("Possible reasons:")
    print("  1. No NVIDIA GPU present")
    print("  2. NVIDIA driver not installed or too old")
    print("  3. CUDA toolkit not properly installed")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ JAX CUDA installation complete and verified!"
else
    echo ""
    echo "❌ JAX installed but GPU not detected"
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Check NVIDIA driver: nvidia-smi"
    echo "2. Required driver version: >= 525 for CUDA 12, >= 580 for CUDA 13"
    echo "3. Check CUDA: nvcc --version"
    echo "4. Try reinstalling with: pip install jax[cuda12_local]"
fi
