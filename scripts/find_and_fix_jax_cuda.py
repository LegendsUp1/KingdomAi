#!/usr/bin/env python3
"""
Find CUDA libraries installed by pip and configure JAX to use them
"""
import os
import sys
import site
from pathlib import Path

print("🔍 Locating pip-installed CUDA libraries...")
print("=" * 60)

# Find all site-packages directories
site_packages = site.getsitepackages()
print(f"Checking {len(site_packages)} site-packages locations...")

cuda_lib_paths = []

# Look for nvidia-* packages
for sp in site_packages:
    sp_path = Path(sp)
    if not sp_path.exists():
        continue
    
    # Find nvidia cuda libraries
    for nvidia_pkg in sp_path.glob("nvidia_*"):
        if nvidia_pkg.is_dir():
            # Look for lib subdirectory
            lib_dir = nvidia_pkg / "lib"
            if lib_dir.exists():
                # Check if it has .so files
                so_files = list(lib_dir.glob("*.so*"))
                if so_files:
                    cuda_lib_paths.append(str(lib_dir))
                    print(f"✅ Found: {nvidia_pkg.name}/lib ({len(so_files)} libraries)")

# Add WSL driver path
wsl_lib = "/usr/lib/wsl/lib"
if Path(wsl_lib).exists():
    cuda_lib_paths.insert(0, wsl_lib)
    print(f"✅ Found: WSL driver libraries at {wsl_lib}")

print()
print(f"📊 Total CUDA library paths found: {len(cuda_lib_paths)}")

if not cuda_lib_paths:
    print("❌ No CUDA libraries found!")
    sys.exit(1)

print()
print("🔧 Creating JAX CUDA configuration...")

# Create the library path string
lib_path_str = ":".join(cuda_lib_paths)

# Create sitecustomize.py in the first site-packages
target_site = Path(site_packages[0])
sitecustomize = target_site / "sitecustomize.py"

# Read existing content if it exists
existing_content = ""
if sitecustomize.exists():
    with open(sitecustomize, 'r') as f:
        existing_content = f.read()
    
    # Remove old JAX CUDA fix if present
    if "# JAX CUDA Configuration for WSL2" in existing_content:
        lines = existing_content.split('\n')
        new_lines = []
        skip = False
        for line in lines:
            if "# JAX CUDA Configuration for WSL2" in line:
                skip = True
            elif skip and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                skip = False
            
            if not skip:
                new_lines.append(line)
        
        existing_content = '\n'.join(new_lines).strip() + '\n\n'

# Create new configuration
new_config = f'''# JAX CUDA Configuration for WSL2 - Auto-generated
import os
import sys

# CUDA library paths (pip-installed + WSL driver)
_cuda_lib_paths = {repr(cuda_lib_paths)}

# Set LD_LIBRARY_PATH before any imports
_current_ld = os.environ.get('LD_LIBRARY_PATH', '')
_new_ld = ':'.join(_cuda_lib_paths)
if _current_ld:
    _new_ld += ':' + _current_ld

os.environ['LD_LIBRARY_PATH'] = _new_ld

# Also set these for XLA
os.environ['XLA_FLAGS'] = '--xla_gpu_cuda_data_dir={cuda_lib_paths[0] if cuda_lib_paths else "/usr/local/cuda"}'

# Debug: Print configuration on first import
if not os.environ.get('_JAX_CUDA_CONFIGURED'):
    os.environ['_JAX_CUDA_CONFIGURED'] = '1'
    # Uncomment to debug:
    # print(f"[JAX CUDA] Library paths: {{_new_ld}}")

'''

# Write combined content
with open(sitecustomize, 'w') as f:
    f.write(new_config)
    if existing_content:
        f.write(existing_content)

print(f"✅ Created/updated: {sitecustomize}")

# Also update .bashrc
bashrc = Path.home() / ".bashrc"
bash_export = f'export LD_LIBRARY_PATH="{lib_path_str}:$LD_LIBRARY_PATH"'

if bashrc.exists():
    with open(bashrc, 'r') as f:
        bashrc_content = f.read()
    
    if lib_path_str not in bashrc_content:
        with open(bashrc, 'a') as f:
            f.write(f'\n# JAX CUDA libraries (auto-added)\n{bash_export}\n')
        print(f"✅ Updated: {bashrc}")
    else:
        print(f"✅ Already configured: {bashrc}")

print()
print("🧪 Testing JAX with GPU...")
print("=" * 60)

# Set environment for current process
os.environ['LD_LIBRARY_PATH'] = lib_path_str + ":" + os.environ.get('LD_LIBRARY_PATH', '')

try:
    import jax
    import jax.numpy as jnp
    
    print(f"✅ JAX version: {jax.__version__}")
    devices = jax.devices()
    print(f"✅ JAX devices: {devices}")
    
    # Check for GPU
    has_gpu = any('gpu' in str(d).lower() or 'cuda' in str(d).lower() for d in devices)
    
    if has_gpu:
        print()
        print("🎉" * 20)
        print("🎉 SUCCESS! GPU IS WORKING! 🎉")
        print("🎉" * 20)
        print()
        
        # Test computation
        print("Testing GPU computation...")
        key = jax.random.PRNGKey(0)
        x = jax.random.normal(key, (1000, 1000))
        y = jnp.dot(x, x.T)
        result = jnp.sum(y)
        
        print(f"✅ GPU computation successful!")
        print(f"   Result: {result:.4f}")
        print(f"   Device: {result.device()}")
        print()
        print("=" * 60)
        print("✅ JAX CUDA is now fully configured!")
        print("=" * 60)
        print()
        print("To use in new terminals:")
        print("  1. Restart terminal OR run: source ~/.bashrc")
        print("  2. Python will automatically use GPU")
        print()
        sys.exit(0)
    else:
        print()
        print("⚠️  GPU not detected")
        print(f"Devices: {devices}")
        print()
        print("Troubleshooting:")
        print(f"Library paths set: {lib_path_str}")
        sys.exit(1)
        
except Exception as e:
    print()
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
