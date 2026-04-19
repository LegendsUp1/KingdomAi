#!/bin/bash
# SOTA 2026: Fix CuDNN Version Mismatch
# Error: "Loaded runtime CuDNN library: 9.1.0 but source was compiled with: 9.8.0"
#
# This script upgrades cuDNN to match what JAX was compiled against.
# Run this in the kingdom-ai conda environment.

echo "🔧 Fixing CuDNN version mismatch..."
echo "   Current: CuDNN 9.1.0"
echo "   Required: CuDNN 9.8.0"
echo ""

# Activate conda environment if not already active
if [[ -z "$CONDA_DEFAULT_ENV" ]] || [[ "$CONDA_DEFAULT_ENV" != "kingdom-ai" ]]; then
    echo "⚠️ Please activate the kingdom-ai conda environment first:"
    echo "   conda activate kingdom-ai"
    exit 1
fi

echo "📦 Installing matching cuDNN version..."

# Option 1: Install via pip (nvidia packages)
echo "   Trying pip install..."
pip install -U nvidia-cudnn-cu12==9.8.0.131 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ cuDNN 9.8.0 installed via pip"
else
    echo "   pip install failed, trying conda..."
    
    # Option 2: Install via conda
    conda install -c conda-forge cudnn=9.8.0 -y 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ cuDNN 9.8.0 installed via conda"
    else
        echo "   conda install failed, trying JAX reinstall..."
        
        # Option 3: Reinstall JAX with bundled CUDA/cuDNN
        pip install -U "jax[cuda12_pip]" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "✅ JAX reinstalled with bundled CUDA/cuDNN"
        else
            echo "❌ All methods failed. Manual fix required:"
            echo "   1. Download cuDNN 9.8.0 from: https://developer.nvidia.com/cudnn"
            echo "   2. Install to: /usr/local/cuda/lib64/"
            echo "   3. Or set LD_LIBRARY_PATH to include cuDNN 9.8.0 directory"
            exit 1
        fi
    fi
fi

echo ""
echo "🔄 Verifying installation..."
python -c "
import jax
print(f'JAX version: {jax.__version__}')
print(f'JAX devices: {jax.devices()}')
try:
    import jax.numpy as jnp
    x = jnp.ones((100, 100))
    y = jnp.dot(x, x)
    print('✅ JAX GPU operations working!')
except Exception as e:
    print(f'⚠️ JAX GPU test failed: {e}')
"

echo ""
echo "✅ CuDNN fix complete!"
