#!/usr/bin/env python3
"""
Ensure Voice Dependencies Are Properly Installed
==================================================
This script ensures all voice/TTS dependencies are correctly installed
and compatible versions are used to prevent runtime errors.
"""

import sys
import subprocess
import importlib.util
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_package(package_name, min_version=None):
    """Check if a package is installed and optionally verify version."""
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            return False, None
        
        if min_version:
            import importlib.metadata
            try:
                installed_version = importlib.metadata.version(package_name)
                from packaging import version
                if version.parse(installed_version) < version.parse(min_version):
                    return True, installed_version  # Installed but outdated
                return True, installed_version
            except Exception:
                return True, "unknown"
        
        return True, None
    except Exception as e:
        logger.debug(f"Error checking {package_name}: {e}")
        return False, None

def install_package(package_spec):
    """Install a package using pip."""
    try:
        logger.info(f"Installing {package_spec}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_spec],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"✅ Successfully installed {package_spec}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install {package_spec}: {e.stderr}")
        return False

def ensure_voice_dependencies():
    """Ensure all voice dependencies are properly installed."""
    logger.info("🔍 Checking voice dependencies...")
    
    # Critical dependencies with specific versions for compatibility
    required_packages = {
        "librosa": "0.10.2",  # Compatible with numba 0.59.0
        "numba": "0.59.0",    # Compatible with librosa 0.10.2
        "TTS": "0.22.0",      # Coqui TTS for XTTS v2
        "edge-tts": "6.1.5",
        "soundfile": "0.12.1",
        "sounddevice": "0.4.5",
        "pyttsx3": "2.90",
    }
    
    missing_packages = []
    outdated_packages = []
    
    # Check each package
    for package, min_version in required_packages.items():
        is_installed, version = check_package(package, min_version)
        
        if not is_installed:
            missing_packages.append(f"{package}>={min_version}")
            logger.warning(f"❌ {package} not installed")
        elif version and min_version:
            from packaging import version as v
            try:
                if v.parse(version) < v.parse(min_version):
                    outdated_packages.append(f"{package}>={min_version}")
                    logger.warning(f"⚠️ {package} version {version} is outdated (need {min_version})")
                else:
                    logger.info(f"✅ {package} version {version} is compatible")
            except Exception:
                logger.info(f"✅ {package} is installed")
        else:
            logger.info(f"✅ {package} is installed")
    
    # Install missing packages
    if missing_packages:
        logger.info(f"📦 Installing {len(missing_packages)} missing packages...")
        for package_spec in missing_packages:
            install_package(package_spec)
    
    # Update outdated packages
    if outdated_packages:
        logger.info(f"🔄 Updating {len(outdated_packages)} outdated packages...")
        for package_spec in outdated_packages:
            install_package(package_spec)
    
    # Pre-download TTS models to prevent runtime delays
    logger.info("📥 Pre-downloading TTS models...")
    try:
        from TTS.api import TTS
        logger.info("Downloading XTTS v2 model (this may take a while)...")
        tts = TTS('tts_models/multilingual/multi-dataset/xtts_v2')
        logger.info("✅ XTTS v2 model ready")
    except Exception as e:
        logger.warning(f"⚠️ Could not pre-download TTS models: {e}")
        logger.info("Models will be downloaded on first use")
    
    if not missing_packages and not outdated_packages:
        logger.info("✅ All voice dependencies are properly installed!")
        return True
    else:
        logger.warning("⚠️ Some dependencies needed installation/updates")
        return False

if __name__ == "__main__":
    success = ensure_voice_dependencies()
    sys.exit(0 if success else 1)
