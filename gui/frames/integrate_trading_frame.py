#!/usr/bin/env python3
"""
Integration script for TradingFrame.
This script reads the current trading_frame.py file, adds all required methods
from the helper modules, and ensures proper Redis Quantum Nexus integration on port 6380.
"""

import os
import sys
import logging
import re
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TradingFrameIntegrator")

# Make sure we can import from parent directory
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.append(str(parent_dir))


def read_file_content(file_path):
    """Read file content and return as string"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None


def write_file_content(file_path, content):
    """Write content to file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {e}")
        return False


def extract_method_content(file_path, class_name):
    """Extract method content from a file containing a class"""
    content = read_file_content(file_path)
    if not content:
        return {}
    
    # Extract class content
    class_pattern = re.compile(fr'class\s+{class_name}\s*:.*?(?=class|\Z)', re.DOTALL)
    class_match = class_pattern.search(content)
    if not class_match:
        logger.error(f"Class {class_name} not found in {file_path}")
        return {}
        
    class_content = class_match.group(0)
    
    # Extract methods
    method_pattern = re.compile(r'(?:async\s+)?def\s+([_a-zA-Z0-9]+)\s*\([^)]*\):\s*(.*?)(?=(?:(?:async\s+)?def\s+|\Z))', re.DOTALL)
    method_matches = method_pattern.finditer(class_content)
    
    methods = {}
    for match in method_matches:
        method_name = match.group(1)
        method_content = match.group(0)
        methods[method_name] = method_content
        
    return methods


def integrate_trading_frame():
    """Integrate all components into the TradingFrame class"""
    logger.info("Starting TradingFrame integration")
    
    # File paths
    base_dir = Path(__file__).parent
    trading_frame_py = base_dir / "trading_frame.py"
    trading_frame_backup = base_dir / "trading_frame_backup.py"
    
    # Make backup of current file
    if trading_frame_py.exists():
        content = read_file_content(trading_frame_py)
        if content:
            write_file_content(trading_frame_backup, content)
            logger.info(f"Created backup of trading_frame.py at {trading_frame_backup}")
    
    # Helper files to integrate
    helper_files = [
        ("trading_frame_methods.py", "TradingFrameMethods"),
        ("trading_frame_handlers.py", "TradingFrameHandlers"),
        ("trading_frame_update_ui.py", "TradingFrameUpdateUI"),
        ("trading_frame_async.py", "TradingFrameAsync")
    ]
    
    # Extract methods from helper files
    all_methods = {}
    for file_name, class_name in helper_files:
        file_path = base_dir / file_name
        if file_path.exists():
            methods = extract_method_content(file_path, class_name)
            all_methods.update(methods)
            logger.info(f"Extracted {len(methods)} methods from {file_name}")
        else:
            logger.warning(f"Helper file {file_path} not found")
    
    # Get content of trading_frame.py
    content = read_file_content(trading_frame_py)
    if not content:
        logger.error("Failed to read trading_frame.py")
        return False
    
    # Find the end of TradingFrame class to insert methods
    class_match = re.search(r'class\s+TradingFrame\s*\(.*?\):\s*', content)
    if not class_match:
        logger.error("TradingFrame class not found in trading_frame.py")
        return False
    
    # Find the end of the class
    class_start = class_match.start()
    
    # Find all existing methods in TradingFrame to avoid duplicates
    existing_methods = re.finditer(r'(?:async\s+)?def\s+([_a-zA-Z0-9]+)\s*\(', content[class_start:])
    existing_method_names = set(match.group(1) for match in existing_methods)
    logger.info(f"Found {len(existing_method_names)} existing methods in TradingFrame")
    
    # Find a good insertion point - after the last method in the class
    # First determine where the class ends
    next_class_match = re.search(r'class\s+[A-Za-z_][A-Za-z0-9_]*\s*\(', content[class_start + 1:])
    if next_class_match:
        class_end = class_start + next_class_match.start()
    else:
        class_end = len(content)
    
    # Find the last method in the class
    last_method_match = None
    method_matches = list(re.finditer(r'(?:async\s+)?def\s+([_a-zA-Z0-9]+)\s*\(', content[class_start:class_end]))
    if method_matches:
        last_method_match = method_matches[-1]
        last_method_end = class_start
        
        # Find the end of the last method
        last_method_name = last_method_match.group(1)
        last_method_start = class_start + last_method_match.start()
        
        # Search for the start of the next method or the end of the class
        next_method_match = re.search(r'(?:async\s+)?def\s+', content[last_method_start + 1:class_end])
        if next_method_match:
            last_method_end = last_method_start + next_method_match.start()
        else:
            # Find the end of the method by indentation
            lines = content[last_method_start:class_end].split('\n')
            method_indent = len(lines[0]) - len(lines[0].lstrip())
            
            for i, line in enumerate(lines[1:], 1):
                if line.strip() and len(line) - len(line.lstrip()) <= method_indent:
                    last_method_end = last_method_start + sum(len(l) + 1 for l in lines[:i])
                    break
            else:
                last_method_end = class_end
        
        insertion_point = last_method_end
    else:
        # If no methods found, insert after class definition
        insertion_point = class_start + class_match.end()
        
    # Filter out methods that already exist
    new_methods = {name: content for name, content in all_methods.items() 
                  if name not in existing_method_names}
    logger.info(f"Adding {len(new_methods)} new methods to TradingFrame")
    
    # Build the new content with methods inserted
    new_content = content[:insertion_point]
    
    # Add new methods
    for method_name, method_content in new_methods.items():
        # Ensure proper indentation (4 spaces)
        indented_content = '\n    '.join(method_content.split('\n'))
        new_content += f"\n    {indented_content}\n"
    
    new_content += content[insertion_point:]
    
    # Add Redis port constants if not already present
    redis_port_const = "REDIS_PORT = 6380  # Mandatory Redis port - no fallbacks allowed"
    redis_password_const = "REDIS_PASSWORD = 'QuantumNexus2025'  # Default Redis password"
    
    if "REDIS_PORT = " not in new_content:
        # Add constants after class definition
        class_def_end = class_match.end()
        new_content = (new_content[:class_def_end] + 
                      f"\n    # Class constants for Redis configuration\n" + 
                      f"    {redis_port_const}\n" + 
                      f"    {redis_password_const}\n" + 
                      new_content[class_def_end:])
    
    # Write the updated content back to the file
    if write_file_content(trading_frame_py, new_content):
        logger.info("Successfully integrated all methods into TradingFrame")
        return True
    else:
        logger.error("Failed to write updated trading_frame.py")
        return False


if __name__ == "__main__":
    success = integrate_trading_frame()
    if success:
        print("TradingFrame integration completed successfully!")
    else:
        print("TradingFrame integration failed. Check the logs for details.")
        sys.exit(1)
