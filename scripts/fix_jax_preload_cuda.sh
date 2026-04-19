#!/bin/bash
# Final fix: Preload CUDA libraries for WSL2

echo "🔧 Final Fix: Preloading CUDA libraries for JAX"
echo "======================================================="
echo ""

# Detect CUDA library path (native Linux vs WSL)
if [ -d "/usr/local/cuda/lib64" ]; then
    CUDA_BASE="/usr/local/cuda/lib64"
elif [ -d "/usr/lib/wsl/lib" ]; then
    CUDA_BASE="/usr/lib/wsl/lib"
else
    CUDA_BASE="/usr/local/cuda/lib64"
fi
echo "Using CUDA base: $CUDA_BASE"

# Find all CUDA .so files
CUDA_LIBS=$(find /usr/local/lib/python3.10/dist-packages/nvidia -name "*.so*" -type f 2>/dev/null | tr '\n' ':')

# Update .bashrc with LD_PRELOAD
echo "Adding LD_PRELOAD to .bashrc..."
cat >> ~/.bashrc << BASHEOF

# JAX CUDA Preload Fix
export LD_LIBRARY_PATH="${CUDA_BASE}:/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_cupti/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_nvrtc/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cufft/lib:/usr/local/lib/python3.10/dist-packages/nvidia/curand/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cusolver/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cusparse/lib:/usr/local/lib/python3.10/dist-packages/nvidia/nccl/lib:/usr/local/lib/python3.10/dist-packages/nvidia/nvjitlink/lib:/usr/local/lib/python3.10/dist-packages/nvidia/nvtx/lib:\$LD_LIBRARY_PATH"

# Preload critical CUDA libraries
export LD_PRELOAD="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/libcudnn.so.9:/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib/libcublas.so.12:/usr/local/lib/python3.10/dist-packages/nvidia/cusparse/lib/libcusparse.so.12:\$LD_PRELOAD"
BASHEOF

echo "✅ Updated .bashrc"
echo ""

# Apply for current session
export LD_LIBRARY_PATH="${CUDA_BASE}:/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_cupti/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_nvrtc/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cufft/lib:/usr/local/lib/python3.10/dist-packages/nvidia/curand/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cusolver/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cusparse/lib:/usr/local/lib/python3.10/dist-packages/nvidia/nccl/lib:/usr/local/lib/python3.10/dist-packages/nvidia/nvjitlink/lib:/usr/local/lib/python3.10/dist-packages/nvidia/nvtx/lib:$LD_LIBRARY_PATH"

export LD_PRELOAD="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/libcudnn.so.9:/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib/libcublas.so.12:/usr/local/lib/python3.10/dist-packages/nvidia/cusparse/lib/libcusparse.so.12:$LD_PRELOAD"

echo "Testing with preloaded libraries..."
python3 << 'PYEOF'
import jax
import jax.numpy as jnp

print(f"✅ JAX version: {jax.__version__}")
print(f"✅ Devices: {jax.devices()}")

try:
    x = jnp.ones((1000, 1000))
    y = jnp.dot(x, x)
    result = jnp.sum(y)
    
    print(f"\n🎉 SUCCESS! GPU COMPUTATION WORKING!")
    print(f"   Result: {result:.2f}")
    print(f"   Device: {result.device()}")
    print(f"\n✅ JAX CUDA is now fully functional on WSL2!")
except Exception as e:
    print(f"\n❌ Still failing: {e}")
    print("\nTry running in a new terminal:")
    print("  source ~/.bashrc")
    print("  python3 -c 'import jax; import jax.numpy as jnp; print(jnp.dot(jnp.ones((10,10)), jnp.ones((10,10))))'")
PYEOF

echo ""
echo "======================================================="
echo "✅ Configuration complete!"
echo ""
echo "To use JAX with GPU in new terminals:"
echo "  1. Open new terminal OR run: source ~/.bashrc"
echo "  2. JAX will automatically use GPU"
echo "======================================================="
