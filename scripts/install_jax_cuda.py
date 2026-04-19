#!/usr/bin/env python3
"""
Install JAX with CUDA support - 2025 Best Practices
Based on official JAX documentation
"""
import subprocess
import sys
import re

print("🚀 Installing JAX with CUDA support...")

def run_command(cmd, check=True):
    """Run command and return output"""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"⚠️  Command failed: {' '.join(cmd)}")
        print(f"Error: {result.stderr}")
    return result

# Step 1: Detect CUDA version
print("📍 Detecting CUDA version...")
nvidia_result = run_command(["nvidia-smi"], check=False)
if nvidia_result.returncode == 0:
    match = re.search(r'CUDA Version:\s+(\d+)', nvidia_result.stdout)
    cuda_version = int(match.group(1)) if match else 12
    print(f"✅ Detected CUDA version: {cuda_version}")
else:
    print("⚠️  nvidia-smi not found, defaulting to CUDA 12")
    cuda_version = 12

# Step 2: Uninstall existing JAX
print("🗑️  Removing old JAX installation...")
packages_to_remove = ["jax", "jaxlib", "jax-cuda12-plugin", "jax-cuda12-pjrt"]
for pkg in packages_to_remove:
    run_command([sys.executable, "-m", "pip", "uninstall", "-y", pkg], check=False)

# Step 3: Install JAX with CUDA support
print("📦 Installing JAX with CUDA support from official repository...")

# Use the correct installation method
install_cmd = [
    sys.executable, "-m", "pip", "install", "--upgrade",
    "jax[cuda12]",
    "-f", "https://storage.googleapis.com/jax-releases/jax_cuda_releases.html"
]

result = run_command(install_cmd, check=False)

if result.returncode != 0:
    print("⚠️  First installation attempt failed, trying alternative...")
    # Try alternative method
    run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    install_cmd_alt = [
        sys.executable, "-m", "pip", "install", "--upgrade",
        "jax[cuda12_pip]",
        "-f", "https://storage.googleapis.com/jax-releases/jax_cuda_releases.html"
    ]
    result = run_command(install_cmd_alt)

# Step 4: Verify installation
print("")
print("🔍 Verifying JAX installation...")

try:
    import jax
    import jax.numpy as jnp
    
    print(f"✅ JAX version: {jax.__version__}")
    print(f"✅ JAX devices: {jax.devices()}")
    
    # Check for GPU
    devices = jax.devices()
    has_gpu = any('gpu' in str(d).lower() or 'cuda' in str(d).lower() for d in devices)
    
    if has_gpu:
        print("🎉 GPU support ENABLED!")
        gpu_devices = [d for d in devices if 'gpu' in str(d).lower() or 'cuda' in str(d).lower()]
        print(f"GPU devices: {gpu_devices}")
        
        # Test GPU computation
        print("🧪 Testing GPU computation...")
        x = jnp.ones((1000, 1000))
        y = jnp.dot(x, x)
        print(f"✅ GPU computation successful! Result shape: {y.shape}")
        
        print("")
        print("✅ JAX CUDA installation complete and verified!")
        sys.exit(0)
    else:
        print("⚠️  GPU support NOT enabled - using CPU")
        print("")
        print("Possible reasons:")
        print("  1. No NVIDIA GPU present on this system")
        print("  2. NVIDIA driver not installed or version too old")
        print("     - Required: >= 525 for CUDA 12")
        print("     - Check with: nvidia-smi")
        print("  3. CUDA toolkit not properly installed")
        print("     - Check with: nvcc --version")
        print("  4. Running in WSL without GPU passthrough enabled")
        print("")
        print("To enable GPU in WSL2:")
        print("  1. Update Windows to latest version")
        print("  2. Install latest NVIDIA driver for Windows")
        print("  3. Ensure .wslconfig has: [wsl2] gpuSupport=true")
        print("")
        sys.exit(1)
        
except ImportError as e:
    print(f"❌ Failed to import JAX: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Verification failed: {e}")
    sys.exit(1)
