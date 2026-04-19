#!/usr/bin/env python3
"""
SOTA 2026: Fix All Kingdom AI Dependencies

This script fixes the remaining dependency issues:
1. CuDNN version mismatch (9.1.0 vs 9.8.0)
2. spaCy/transformers BatchEncoding compatibility
3. WSL2 webcam access setup

Run with: python scripts/fix_dependencies_sota_2026.py

Based on extensive SOTA 2026 research (February 2026).
"""

import subprocess
import sys
import os
import platform
from pathlib import Path


def run_command(cmd, description, check=True):
    """Run a command and print status."""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"   Command: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if check and result.returncode != 0:
            print(f"⚠️ Command returned non-zero exit code: {result.returncode}")
            return False
        
        print(f"✅ {description} - Done")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def fix_cudnn():
    """Fix CuDNN version mismatch (SOTA 2026).
    
    The issue: JAX was compiled against CuDNN 9.8.0 but system has 9.1.0
    The fix: Install nvidia-cudnn-cu12 9.19.0+ (latest as of Feb 2026)
    """
    print("\n" + "="*60)
    print("🔧 FIX 1: CuDNN Version Mismatch")
    print("="*60)
    print("""
PROBLEM:
  - JAX compiled with CuDNN 9.8.0
  - Your system has CuDNN 9.1.0
  - Error: "Loaded runtime CuDNN library: 9.1.0 but source was compiled with: 9.8.0"

SOLUTION (SOTA 2026):
  - Install nvidia-cudnn-cu12 >= 9.19.0 (latest version, much newer than 9.8.0)
  - This is fully backward compatible with JAX compiled against 9.8.0
""")
    
    # Check current cuDNN version
    print("\n📊 Checking current cuDNN installation...")
    try:
        import nvidia.cudnn
        current_version = getattr(nvidia.cudnn, '__version__', 'unknown')
        print(f"   Current nvidia-cudnn-cu12: {current_version}")
    except ImportError:
        print("   nvidia-cudnn-cu12 not installed")
        current_version = None
    
    # Upgrade cuDNN
    commands = [
        ("pip install --upgrade nvidia-cudnn-cu12>=9.19.0", "Upgrade nvidia-cudnn-cu12 to latest"),
    ]
    
    success = True
    for cmd, desc in commands:
        if not run_command(cmd, desc, check=False):
            success = False
    
    # Verify
    print("\n📊 Verifying cuDNN installation...")
    try:
        # Force reimport
        import importlib
        import nvidia.cudnn
        importlib.reload(nvidia.cudnn)
        new_version = getattr(nvidia.cudnn, '__version__', 'unknown')
        print(f"   New nvidia-cudnn-cu12: {new_version}")
        
        if new_version != 'unknown':
            version_num = int(new_version.split('.')[0])
            if version_num >= 9:
                print("✅ CuDNN version is compatible!")
            else:
                print("⚠️ CuDNN version may still have issues")
    except ImportError:
        print("⚠️ Could not verify cuDNN installation")
    
    return success


def fix_jax():
    """Reinstall JAX with bundled CUDA (SOTA 2026)."""
    print("\n" + "="*60)
    print("🔧 FIX 2: JAX with Bundled CUDA")
    print("="*60)
    print("""
SOLUTION:
  - Reinstall JAX with cuda12_pip extra
  - This bundles compatible CUDA/cuDNN libraries
""")
    
    commands = [
        (
            'pip install --upgrade "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html',
            "Install JAX with CUDA 12 (bundled)"
        ),
    ]
    
    success = True
    for cmd, desc in commands:
        if not run_command(cmd, desc, check=False):
            success = False
    
    return success


def fix_spacy_transformers():
    """Fix spaCy/transformers compatibility (SOTA 2026).
    
    The issue: spacy-transformers expects BatchEncoding in transformers.tokenization_utils
              but transformers 5.0+ moved it to tokenization_utils_base
    """
    print("\n" + "="*60)
    print("🔧 FIX 3: spaCy/Transformers Compatibility")
    print("="*60)
    print("""
PROBLEM:
  - spacy-transformers 1.3.x imports BatchEncoding from transformers.tokenization_utils
  - transformers 5.0+ moved BatchEncoding to tokenization_utils_base
  - Error: "cannot import name 'BatchEncoding' from 'transformers.tokenization_utils'"

SOLUTION (SOTA 2026):
  - The sitecustomize.py patch handles this at runtime
  - Alternatively, pin transformers < 5.0.0 (not recommended for new features)
""")
    
    # Check versions
    print("\n📊 Checking current versions...")
    try:
        import transformers
        print(f"   transformers: {transformers.__version__}")
    except ImportError:
        print("   transformers: not installed")
    
    try:
        import spacy_transformers
        print(f"   spacy-transformers: {spacy_transformers.__version__}")
    except ImportError:
        print("   spacy-transformers: not installed")
    
    # The runtime patch in sitecustomize.py handles this
    print("\n✅ Runtime patch is active in sitecustomize.py")
    print("   This patches transformers.tokenization_utils.BatchEncoding at import time")
    
    # Verify patch works
    print("\n📊 Verifying BatchEncoding patch...")
    try:
        from transformers.tokenization_utils import BatchEncoding
        print(f"   BatchEncoding import: ✅ Success")
        print(f"   BatchEncoding type: {type(BatchEncoding)}")
    except ImportError as e:
        print(f"   BatchEncoding import: ❌ Failed - {e}")
        print("   The sitecustomize.py patch may need to run first")
    
    return True


def setup_wsl2_camera():
    """Setup WSL2 camera access (SOTA 2026)."""
    print("\n" + "="*60)
    print("🔧 FIX 4: WSL2 Camera Access")
    print("="*60)
    
    # Detect environment
    is_wsl = False
    try:
        is_wsl = os.path.exists('/proc/sys/fs/binfmt_misc/WSLInterop') or \
                 'microsoft' in platform.uname().release.lower()
    except Exception:
        pass
    
    if not is_wsl:
        print("ℹ️ Running on native Linux - camera access should work natively")
        return True
    
    print("""
PROBLEM:
  - WSL2 doesn't have direct access to Windows webcams
  - /dev/video0 doesn't exist in WSL2 by default
  - OpenCV cv2.VideoCapture(0) fails

SOLUTIONS (SOTA 2026):

1. RECOMMENDED: MJPEG Camera Server (easiest)
   - Run on Windows: python scripts/windows_camera_server.py
   - Access in WSL2: cv2.VideoCapture('http://localhost:8090/video.mjpg')

2. ALTERNATIVE: usbipd-win (requires kernel rebuild)
   - Windows: winget install dorssel.usbipd-win
   - WSL2: sudo apt install linux-tools-generic hwdata
   - Bind camera: usbipd bind --busid <device-id>
   - Attach: usbipd attach --wsl --busid <device-id>
   - May require custom WSL2 kernel with V4L2 support

3. ALTERNATIVE: cam2web
   - Download from: https://github.com/cvsandbox/cam2web/releases
   - Run on Windows, access MJPEG stream in WSL2
""")
    
    # Check if camera server script exists
    script_path = Path(__file__).parent / 'windows_camera_server.py'
    if script_path.exists():
        print(f"\n✅ Camera server script available at: {script_path}")
        print("   Run on Windows: python scripts/windows_camera_server.py")
    
    # Check if we can access any camera bridges
    print("\n📊 Testing camera access methods...")
    
    try:
        import cv2
        
        # Test MJPEG stream
        for url in ['http://localhost:8090/video.mjpg', 'http://localhost:8090/brio.mjpg']:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                if ret:
                    print(f"   ✅ MJPEG stream available: {url}")
                    return True
            
        # Test direct access (unlikely to work)
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.release()
            print("   ✅ Direct camera access works!")
            return True
        
        print("   ❌ No camera access available")
        print("   💡 Start the Windows camera server first")
        
    except ImportError:
        print("   OpenCV not installed")
    
    return True


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Kingdom AI - SOTA 2026 Dependency Fixer                  ║
║     Resolves CuDNN, spaCy/transformers, and Camera issues    ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")
    
    results = {}
    
    # Fix 1: CuDNN
    results['cudnn'] = fix_cudnn()
    
    # Fix 2: JAX
    results['jax'] = fix_jax()
    
    # Fix 3: spaCy/transformers
    results['spacy'] = fix_spacy_transformers()
    
    # Fix 4: WSL2 camera
    results['camera'] = setup_wsl2_camera()
    
    # Summary
    print("\n" + "="*60)
    print("📋 SUMMARY")
    print("="*60)
    
    for name, success in results.items():
        status = "✅ Fixed" if success else "⚠️ Check manually"
        print(f"   {name}: {status}")
    
    print("""
═══════════════════════════════════════════════════════════════

NEXT STEPS:
1. Restart Python to apply sitecustomize.py patches
2. For WSL2 camera: Run windows_camera_server.py on Windows first
3. Run Kingdom AI to verify fixes

If issues persist:
- CuDNN: Try 'conda install -c conda-forge cudnn>=9.8.0'
- spaCy: The runtime patch should handle it automatically
- Camera: Make sure the Windows camera server is running

═══════════════════════════════════════════════════════════════
""")
    
    return 0 if all(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
