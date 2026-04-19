"""
Kingdom AI Launch Validation Script
Validates the system environment before launching Kingdom AI
"""

import os
import sys
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_directory_structure():
    """Validate that all required directories exist"""
    required_dirs = [
        "blockchain",
        "blockchain/xrp",
        "core",
        "utils",
        "gui",
        # legacy folders are optional in current runtime
        # ("analysis", "meta_learning")
        "wallet",
        "vr",
        "scripts",
        "config",
        "logs",
        "data",
        "models",
        "tests"
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            missing_dirs.append(dir_path)
            
    if missing_dirs:
        logger.error(f"Missing directories: {missing_dirs}")
        return False
    return True

def validate_config():
    """Validate configuration file exists and has required fields"""
    config_path = "config/config.json"
    if not os.path.exists(config_path):
        logger.error("config.json not found")
        return False
        
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        required_fields = [
            "system",
            "blockchain.xrp",
            "blockchain.ethereum",
            "gui",
            "security",
            "api"
        ]
        
        for field in required_fields:
            parts = field.split('.')
            current = config
            for part in parts:
                if part not in current:
                    logger.error(f"Missing config field: {field}")
                    return False
                current = current[part]
                
        return True
    except Exception as e:
        logger.error(f"Failed to validate config: {e}")
        return False

def validate_dependencies():
    """Validate that all required Python packages are installed"""
    # Map package distribution names to import names.
    required_packages = [
        ("xrpl-py", "xrpl"),
        ("web3", "web3"),
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("requests", "requests"),
    ]
    
    missing_packages = []
    for package, import_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package)
            
    if missing_packages:
        logger.error(f"Missing Python packages: {missing_packages}")
        return False
    return True

def validate_environment():
    """Validate environment variables"""
    # In WSL/conda runtime, these may be unset while launch still works.
    # Require either explicit env vars OR inferable runtime root.
    pythonpath_ok = bool(os.environ.get("PYTHONPATH"))
    kingdom_root = os.environ.get("KINGDOM_ROOT")
    inferred_root_ok = os.path.exists("kingdom_ai_perfect.py")
    if not pythonpath_ok:
        logger.warning("PYTHONPATH not set (allowed in current runtime)")
    if not kingdom_root and not inferred_root_ok:
        logger.error("KINGDOM_ROOT missing and runtime root cannot be inferred")
        return False
    return True

def main():
    """Main validation function"""
    logger.info("Starting Kingdom AI validation...")
    
    # Run all validation checks
    validations = [
        (validate_directory_structure, "Directory structure validation"),
        (validate_config, "Configuration validation"),
        (validate_dependencies, "Dependencies validation"),
        (validate_environment, "Environment validation")
    ]
    
    success = True
    for validate_func, description in validations:
        logger.info(f"Running {description}...")
        if not validate_func():
            logger.error(f"{description} failed")
            success = False
            
    if success:
        logger.info("All validation checks passed!")
        return 0
    else:
        logger.error("Validation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
