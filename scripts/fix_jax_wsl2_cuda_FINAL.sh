#!/bin/bash
# FINAL FIX: JAX CUDA in WSL2 - Based on Extensive Research
# Root cause: JAX can't find CUDA runtime libraries in WSL2

set -e

echo "🔧 FINAL FIX: JAX CUDA (native Linux / WSL2)"
echo "============================================"
echo ""

# Step 1: Verify GPU is accessible
echo "Step 1: Verifying GPU access..."
if ! nvidia-smi &>/dev/null; then
    echo "❌ nvidia-smi not working"
    echo "GPU passthrough not enabled in WSL2"
    exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
CUDA_VER=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}')
echo "✅ GPU detected: $GPU_NAME"
echo "✅ CUDA version: $CUDA_VER"
echo ""

# Step 2: Find CUDA libraries (native Linux first, then WSL fallback)
echo "Step 2: Locating CUDA libraries..."
WSL_CUDA_PATH=""
for candidate in "/usr/local/cuda/lib64" "/usr/local/cuda-12/lib64" "/usr/lib/wsl/lib"; do
    if [ -d "$candidate" ]; then
        WSL_CUDA_PATH="$candidate"
        break
    fi
done

if [ -z "$WSL_CUDA_PATH" ]; then
    echo "❌ Cannot find CUDA libraries in standard locations"
    echo "Checked: /usr/local/cuda/lib64, /usr/local/cuda-12/lib64, /usr/lib/wsl/lib"
    exit 1
fi

echo "✅ CUDA libraries at: $WSL_CUDA_PATH"

# List key libraries
echo "Checking for key CUDA libraries:"
for lib in libcudart.so libcublas.so libcusparse.so libcufft.so; do
    if ls $WSL_CUDA_PATH/$lib* &>/dev/null; then
        echo "  ✅ $lib found"
    else
        echo "  ⚠️  $lib not found"
    fi
done
echo ""

# Step 3: Configure Python to use WSL CUDA libraries
echo "Step 3: Configuring Python environment..."

# Create a sitecustomize.py to set LD_LIBRARY_PATH before JAX imports
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
echo "Python site-packages: $SITE_PACKAGES"

cat > "$SITE_PACKAGES/jax_cuda_fix.py" << PYEOF
"""
JAX CUDA Fix — sets LD_LIBRARY_PATH before JAX tries to load CUDA libraries
"""
import os
import sys

CUDA_LIB_PATH = "${WSL_CUDA_PATH}"

current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
if CUDA_LIB_PATH not in current_ld_path:
    if current_ld_path:
        os.environ['LD_LIBRARY_PATH'] = f"{CUDA_LIB_PATH}:{current_ld_path}"
    else:
        os.environ['LD_LIBRARY_PATH'] = CUDA_LIB_PATH
    os.environ['CUDA_PATH'] = '/usr/local/cuda'
PYEOF

echo "✅ Created jax_cuda_fix.py in site-packages"
echo ""

# Step 4: Ensure sitecustomize.py imports the fix FIRST
SITECUSTOMIZE="$SITE_PACKAGES/sitecustomize.py"

if [ -f "$SITECUSTOMIZE" ]; then
    # Check if fix is already imported
    if ! grep -q "jax_cuda_fix" "$SITECUSTOMIZE"; then
        # Add import at the very top
        echo -e "# JAX CUDA Fix for WSL2 - Must be FIRST\nimport jax_cuda_fix\n\n$(cat $SITECUSTOMIZE)" > "$SITECUSTOMIZE"
        echo "✅ Updated existing sitecustomize.py"
    else
        echo "✅ sitecustomize.py already has JAX CUDA fix"
    fi
else
    # Create new sitecustomize.py
    cat > "$SITECUSTOMIZE" << 'PYEOF'
# JAX CUDA Fix for WSL2 - Must be FIRST
import jax_cuda_fix
PYEOF
    echo "✅ Created sitecustomize.py"
fi
echo ""

# Step 5: Also add to .bashrc for shell sessions
echo "Step 5: Updating .bashrc..."
BASHRC="$HOME/.bashrc"

if ! grep -q "CUDA for JAX" "$BASHRC"; then
    cat >> "$BASHRC" << BASHEOF

# CUDA for JAX
export LD_LIBRARY_PATH="${WSL_CUDA_PATH}:\${LD_LIBRARY_PATH}"
export CUDA_PATH="/usr/local/cuda"
BASHEOF
    echo "✅ Updated .bashrc"
else
    echo "✅ .bashrc already configured"
fi

# Apply for current session
export LD_LIBRARY_PATH="${WSL_CUDA_PATH}:${LD_LIBRARY_PATH}"
export CUDA_PATH="/usr/local/cuda"
echo ""

# Step 6: Test JAX with GPU
echo "Step 6: Testing JAX GPU access..."
echo "============================================"

python3 << 'TESTPY'
import os
import sys

# Ensure environment is set (CUDA_LIB_PATH detected by shell script above)
os.environ['LD_LIBRARY_PATH'] = os.environ.get('LD_LIBRARY_PATH', '')

print("\n🧪 Testing JAX with GPU...")
print("-" * 50)

try:
    import jax
    import jax.numpy as jnp
    
    print(f"✅ JAX version: {jax.__version__}")
    print(f"✅ JAX devices: {jax.devices()}")
    
    devices = jax.devices()
    device_strs = [str(d) for d in devices]
    
    # Check if GPU is detected
    has_gpu = any('gpu' in s.lower() or 'cuda' in s.lower() for s in device_strs)
    
    if has_gpu:
        print("\n🎉 SUCCESS! GPU IS DETECTED!")
        print("-" * 50)
        
        gpu_devices = [d for d in devices if 'gpu' in str(d).lower() or 'cuda' in str(d).lower()]
        print(f"GPU devices available: {gpu_devices}")
        
        # Test computation on GPU
        print("\n🧮 Testing GPU computation...")
        key = jax.random.PRNGKey(0)
        x = jax.random.normal(key, (1000, 1000))
        y = jnp.dot(x, x.T)
        result = jnp.sum(y)
        
        print(f"✅ GPU computation successful!")
        print(f"   Matrix multiplication result: {result:.2f}")
        print(f"   Computation device: {result.device()}")
        
        print("\n" + "=" * 50)
        print("🎉 JAX CUDA IS NOW WORKING IN WSL2!")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n⚠️  GPU not detected, still using CPU")
        print(f"Devices: {devices}")
        sys.exit(1)
        
except Exception as e:
    print(f"\n❌ Error during JAX test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
TESTPY

TEST_EXIT=$?
echo ""

if [ $TEST_EXIT -eq 0 ]; then
    echo "============================================"
    echo "✅ COMPLETE! JAX CUDA WORKING!"
    echo "============================================"
    echo ""
    echo "Your RTX 4060 is now accessible to JAX!"
    echo ""
    echo "To use in new terminals:"
    echo "  1. Restart terminal OR run: source ~/.bashrc"
    echo "  2. Start Kingdom AI: python3 kingdom_ai_perfect.py"
    echo ""
else
    echo "============================================"
    echo "❌ GPU Still Not Detected"
    echo "============================================"
    echo ""
    echo "Additional steps to try:"
    echo ""
    echo "1. Check if CUDA libraries are accessible:"
    echo "   ls -la /usr/lib/wsl/lib/libcudart*"
    echo ""
    echo "2. Verify library loader can find them:"
    echo "   ldconfig -p | grep cuda"
    echo ""
    echo "3. Try running with explicit library path:"
    echo "   LD_LIBRARY_PATH=/usr/lib/wsl/lib python3 -c 'import jax; print(jax.devices())'"
    echo ""
    echo "4. Check XLA backend logs:"
    echo "   XLA_FLAGS=--xla_gpu_cuda_data_dir=/usr/lib/wsl python3 -c 'import jax; print(jax.devices())'"
    echo ""
fi

exit $TEST_EXIT
