#!/bin/bash
# Fix WSL2 CUDA Library Access for JAX
# This solves: "Error loading CUDA libraries"

echo "🔧 Fixing CUDA library access for JAX (native Linux / WSL2)..."

# Step 1: Find CUDA libraries
echo "📍 Locating CUDA libraries..."

# CUDA library locations — native Linux paths first, then WSL fallback
CUDA_PATHS=(
    "/usr/local/cuda/lib64"
    "/usr/local/cuda-12/lib64"
    "/usr/local/cuda-12.9/lib64"
    "/usr/lib/wsl/lib"
)

FOUND_PATH=""
for path in "${CUDA_PATHS[@]}"; do
    if [ -d "$path" ] && [ -f "$path/libcudart.so" ] || [ -f "$path/libcudart.so.12" ]; then
        FOUND_PATH="$path"
        echo "✅ Found CUDA libraries at: $FOUND_PATH"
        break
    fi
done

if [ -z "$FOUND_PATH" ]; then
    echo "❌ Cannot find CUDA libraries"
    echo ""
    echo "Solution: Install CUDA toolkit"
    echo "Run: sudo apt-get install nvidia-cuda-toolkit"
    exit 1
fi

# Step 2: Set LD_LIBRARY_PATH permanently
echo ""
echo "📝 Configuring library paths..."

# Add to .bashrc if not already there
BASHRC="$HOME/.bashrc"
EXPORT_LINE="export LD_LIBRARY_PATH=\"$FOUND_PATH:\$LD_LIBRARY_PATH\""

if grep -q "$FOUND_PATH" "$BASHRC" 2>/dev/null; then
    echo "✅ Library path already configured in .bashrc"
else
    echo "" >> "$BASHRC"
    echo "# CUDA libraries for JAX (added by Kingdom AI)" >> "$BASHRC"
    echo "$EXPORT_LINE" >> "$BASHRC"
    echo "✅ Added library path to .bashrc"
fi

# Step 3: Set for current session
export LD_LIBRARY_PATH="$FOUND_PATH:$LD_LIBRARY_PATH"
echo "✅ Library path set for current session"

# Step 4: Verify CUDA is accessible
echo ""
echo "🔍 Verifying CUDA runtime access..."

# Check if libcudart is accessible
if ldconfig -p | grep -q libcudart; then
    echo "✅ libcudart found in library cache"
else
    echo "⚠️  libcudart not in cache, updating ldconfig..."
    sudo ldconfig "$FOUND_PATH" 2>/dev/null || true
fi

# Step 5: Test JAX with GPU
echo ""
echo "🧪 Testing JAX GPU access..."

python3 << 'PYEOF'
import os
import sys

# LD_LIBRARY_PATH already set by the shell script above

try:
    import jax
    print(f"✅ JAX version: {jax.__version__}")
    print(f"✅ JAX devices: {jax.devices()}")
    
    devices = jax.devices()
    has_gpu = any('gpu' in str(d).lower() or 'cuda' in str(d).lower() for d in devices)
    
    if has_gpu:
        print("")
        print("🎉 SUCCESS! GPU is now accessible to JAX!")
        print(f"GPU devices: {[str(d) for d in devices if 'gpu' in str(d).lower() or 'cuda' in str(d).lower()]}")
        
        # Test computation
        import jax.numpy as jnp
        x = jnp.ones((1000, 1000))
        y = jnp.dot(x, x)
        print(f"✅ GPU computation test passed! Result shape: {y.shape}")
        sys.exit(0)
    else:
        print("")
        print("⚠️  Still using CPU - GPU not detected")
        print(f"Devices: {devices}")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ WSL2 CUDA access configured successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Restart your terminal or run: source ~/.bashrc"
    echo "2. Start Kingdom AI: python3 kingdom_ai_perfect.py"
    echo "3. JAX will now use your RTX 4060 GPU!"
else
    echo "❌ GPU still not accessible"
    echo ""
    echo "Additional troubleshooting:"
    echo ""
    echo "1. Verify CUDA runtime version matches:"
    echo "   nvidia-smi shows: CUDA 12.9"
    echo "   JAX installed for: CUDA 12.x ✓"
    echo ""
    echo "2. Try installing CUDA toolkit in WSL:"
    echo "   wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb"
    echo "   sudo dpkg -i cuda-keyring_1.1-1_all.deb"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install cuda-toolkit-12-6"
    echo ""
    echo "3. Ensure Windows .wslconfig has GPU support:"
    echo "   [wsl2]"
    echo "   gpuSupport=true"
fi
