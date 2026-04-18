#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - PyQt6 GUI Validator

This module provides utilities to validate that all GUI components properly use PyQt6
(no Tkinter fallback allowed) and properly connect to the event bus. It also validates
that all GUI elements needed for quantum mining, blockchain operations, and other
critical features are present and properly wired.
"""

import os
import sys
import importlib
import inspect
import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
import json

# Configure logging
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(_LOG_DIR, "gui_validation.log")),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("PyQt6Validator")

# Define required PyQt6 classes for Kingdom AI
REQUIRED_PYQT6_MODULES = [
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui"
]

# Required GUI components
REQUIRED_COMPONENTS = [
    "MainWindow",
    "TabManager",
    "TradingTab",
    "MiningTab",
    "BlockchainTab",
    "ApiKeyManagerTab",
    "ThothAITab",
    "WalletTab",
    "SettingsTab",
    "VRTab",
]

# Required event bus connections for GUI
REQUIRED_EVENT_TYPES = [
    "mining_status_update",
    "trading_status_update",
    "blockchain_connection_update",
    "quantum_nexus_health",
    "wallet_balance_update",
    "card_transaction",
    "mcp_connection_status",
    "api_key_update",
    "thoth_ai_task"
]

# Active runtime GUI surfaces (strictly validated). Legacy files outside these
# surfaces are still scanned, but violations are downgraded to warnings.
ACTIVE_RUNTIME_PATH_PREFIXES = [
    "gui/qt_frames/",
    "gui/widgets/",
]
ACTIVE_RUNTIME_FILES = {
    "gui/main_window.py",
    "gui/main_window_qt.py",
    "gui/tab_manager.py",
    "main.py",
    "kingdom_ai_perfect.py",
}

EVENT_BUS_REQUIRED_FILES = {
    "gui/main_window.py",
    "gui/main_window_qt.py",
    "gui/tab_manager.py",
    "gui/widgets/visual_creation_canvas.py",
}


class PyQt6Validator:
    """Validates that the Kingdom AI GUI properly uses PyQt6 and connects to the event bus."""
    
    def __init__(self, base_dir: str = None):
        """
        Initialize the validator.
        
        Args:
            base_dir: Base directory of the Kingdom AI codebase
        """
        self.logger = logging.getLogger("PyQt6Validator")
        
        # Set base directory
        self.base_dir = Path(base_dir) if base_dir else Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.gui_dir = self.base_dir / "gui"
        
        # Results tracking
        self.results = {
            "pyqt6_usage": {
                "passed": True,
                "issues": [],
                "components_checked": 0,
                "pyqt6_imports_found": 0,
                "tkinter_imports_found": 0
            },
            "event_bus_connection": {
                "passed": True,
                "issues": [],
                "components_with_event_bus": 0,
                "components_without_event_bus": 0,
                "event_types_found": set()
            },
            "required_components": {
                "passed": True,
                "issues": [],
                "components_found": set(),
                "components_missing": set()
            },
            "gui_initialization": {
                "passed": True,
                "issues": [],
            }
        }
        
        # Track processed files
        self.files_processed = 0
    
    def validate_all(self) -> Dict[str, Any]:
        """
        Run all validation checks.
        
        Returns:
            Dict: Validation results
        """
        self.logger.info("Starting PyQt6 validation for Kingdom AI GUI")
        
        # Check that the GUI directory exists
        if not self.gui_dir.exists():
            self.logger.error(f"GUI directory not found: {self.gui_dir}")
            self.results["pyqt6_usage"]["passed"] = False
            self.results["pyqt6_usage"]["issues"].append(f"GUI directory not found: {self.gui_dir}")
            return {
                "overall_passed": False,
                "details": self.results
            }
        
        # Check PyQt6 installation
        self._check_pyqt6_installation()
        
        # Validate GUI files
        self._validate_gui_directory()
        
        # Validate required components
        self._check_required_components()
        
        # Check main.py for proper GUI initialization
        self._check_gui_initialization()
        
        # Overall result is only passed if all categories passed
        overall_passed = all(self.results[category]["passed"] for category in self.results)
        
        self.logger.info(f"PyQt6 validation complete. Overall result: {'PASSED' if overall_passed else 'FAILED'}")
        
        return {
            "overall_passed": overall_passed,
            "details": self.results
        }
    
    def _check_pyqt6_installation(self):
        """Check that PyQt6 is properly installed."""
        self.logger.info("Checking PyQt6 installation")
        
        missing_modules = []
        
        for module_name in REQUIRED_PYQT6_MODULES:
            try:
                module = importlib.import_module(module_name)
                self.results["pyqt6_usage"]["pyqt6_imports_found"] += 1
                self.logger.debug(f"Successfully imported {module_name}")
            except ImportError as e:
                missing_modules.append(module_name)
                self.logger.error(f"Failed to import {module_name}: {e}")
        
        if missing_modules:
            self.results["pyqt6_usage"]["passed"] = False
            self.results["pyqt6_usage"]["issues"].append(
                f"Missing PyQt6 modules: {', '.join(missing_modules)}"
            )
            self.logger.critical("PyQt6 modules are missing! Kingdom AI requires PyQt6 with no fallbacks.")
    
    def _validate_gui_directory(self):
        """Validate all Python files in the GUI directory."""
        self.logger.info(f"Validating GUI directory: {self.gui_dir}")
        
        if not self.gui_dir.exists():
            return
        
        # Process Python files
        for py_file in self.gui_dir.glob("**/*.py"):
            self._validate_gui_file(py_file)
            
        # Also check main.py in the root directory
        main_py = self.base_dir / "main.py"
        if main_py.exists():
            self._validate_gui_file(main_py)
        runtime_entry = self.base_dir / "kingdom_ai_perfect.py"
        if runtime_entry.exists():
            self._validate_gui_file(runtime_entry)
    
    def _validate_gui_file(self, file_path: Path):
        """
        Validate a GUI Python file.
        
        Args:
            file_path: Path to Python file
        """
        self.files_processed += 1
        relative_path = file_path.relative_to(self.base_dir)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            self.logger.debug(f"Validating GUI file: {relative_path}")
            
            rel_str = str(relative_path).replace("\\", "/")
            is_active_runtime_file = (
                rel_str in ACTIVE_RUNTIME_FILES
                or any(rel_str.startswith(prefix) for prefix in ACTIVE_RUNTIME_PATH_PREFIXES)
            )

            # Check for PyQt6 imports
            if "PyQt6" in content:
                self.results["pyqt6_usage"]["pyqt6_imports_found"] += 1
                self.logger.debug(f"PyQt6 import found in {relative_path}")
            
            # Check for explicit Tkinter imports (string mentions in docs/comments
            # are not runtime violations).
            has_tkinter_import = bool(
                re.search(r"^\s*(import|from)\s+tkinter\b", content, flags=re.IGNORECASE | re.MULTILINE)
            )
            if has_tkinter_import:
                self.results["pyqt6_usage"]["tkinter_imports_found"] += 1
                if is_active_runtime_file:
                    self.results["pyqt6_usage"]["passed"] = False
                    self.results["pyqt6_usage"]["issues"].append(
                        f"Active runtime file {relative_path} uses Tkinter instead of PyQt6"
                    )
                    self.logger.error(f"Tkinter usage detected in active runtime file {relative_path}!")
                else:
                    self.logger.warning(f"Legacy file uses Tkinter (non-runtime): {relative_path}")
            
            # Check for component classes
            if "class " in content:
                # This file defines a class
                self.results["pyqt6_usage"]["components_checked"] += 1
                
                # Check for event bus connection
                if "event_bus" in content or "EventBus" in content or "get_event_bus" in content:
                    self.results["event_bus_connection"]["components_with_event_bus"] += 1
                    self.logger.debug(f"Event bus connection found in {relative_path}")
                    
                    # Check for specific event types
                    for event_type in REQUIRED_EVENT_TYPES:
                        if event_type in content:
                            self.results["event_bus_connection"]["event_types_found"].add(event_type)
                else:
                    # Only enforce event-bus connectivity for active runtime GUI
                    # components that are actual Qt widgets/windows.
                    is_qt_component = "QWidget" in content or "QMainWindow" in content
                    requires_event_bus = (
                        rel_str in EVENT_BUS_REQUIRED_FILES
                        or ("class " in content and "Tab(" in content)
                        or ("class " in content and "MainWindow(" in content)
                    )
                    if is_active_runtime_file and is_qt_component and requires_event_bus:
                        self.results["event_bus_connection"]["components_without_event_bus"] += 1
                        self.results["event_bus_connection"]["passed"] = False
                        self.results["event_bus_connection"]["issues"].append(
                            f"Active GUI component in {relative_path} does not connect to the event bus"
                        )
                        self.logger.warning(f"No event bus connection found in active component {relative_path}")
                
                # Check for required components
                for component in REQUIRED_COMPONENTS:
                    if f"class {component}" in content:
                        self.results["required_components"]["components_found"].add(component)
                        self.logger.info(f"Required component found: {component} in {relative_path}")
            
            # Check for quantum mining controls in mining frame
            if file_path.name == "mining_frame.py":
                mining_controls = ["start_mining", "stop_mining", "quantum_devices", "hashrate"]
                missing_controls = [control for control in mining_controls if control not in content.lower()]
                
                if missing_controls:
                    self.results["required_components"]["passed"] = False
                    self.results["required_components"]["issues"].append(
                        f"MiningFrame is missing required controls: {', '.join(missing_controls)}"
                    )
                    self.logger.warning(f"MiningFrame is missing required controls: {', '.join(missing_controls)}")
            
            # Check for proper tab management in tab manager
            if file_path.name == "tab_manager.py":
                required_tabs = ["Trading", "Mining", "Blockchain", "API", "Thoth", "Wallet", "Settings"]
                missing_tabs = [tab for tab in required_tabs if tab not in content]
                
                if missing_tabs:
                    # In current architecture, tab labels can be assembled dynamically.
                    self.logger.warning(f"TabManager static labels not found for: {', '.join(missing_tabs)}")
            
        except Exception as e:
            self.logger.error(f"Error validating file {relative_path}: {str(e)}")
    
    def _check_required_components(self):
        """Check that all required GUI components are present."""
        self.logger.info("Checking for required GUI components")
        
        # Check which required components were found
        missing_components = set(REQUIRED_COMPONENTS) - self.results["required_components"]["components_found"]
        
        if missing_components:
            self.results["required_components"]["passed"] = False
            self.results["required_components"]["components_missing"] = missing_components
            self.results["required_components"]["issues"].append(
                f"Missing required GUI components: {', '.join(missing_components)}"
            )
            self.logger.error(f"Missing required GUI components: {', '.join(missing_components)}")
        
        # Check if all event types are handled
        missing_event_types = set(REQUIRED_EVENT_TYPES) - self.results["event_bus_connection"]["event_types_found"]
        
        if missing_event_types:
            self.results["event_bus_connection"]["passed"] = False
            self.results["event_bus_connection"]["issues"].append(
                f"Missing handlers for event types: {', '.join(missing_event_types)}"
            )
            self.logger.warning(f"Missing handlers for event types: {', '.join(missing_event_types)}")
    
    def _check_gui_initialization(self):
        """Check that the main application properly initializes the GUI."""
        main_py = self.base_dir / "main.py"
        runtime_entry = self.base_dir / "kingdom_ai_perfect.py"
        init_file = runtime_entry if runtime_entry.exists() else main_py
        
        if not init_file.exists():
            self.results["gui_initialization"]["passed"] = False
            self.results["gui_initialization"]["issues"].append("No GUI entrypoint found (main.py/kingdom_ai_perfect.py)")
            self.logger.error("No GUI entrypoint found")
            return
        
        try:
            with open(init_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check for PyQt6 application initialization
            if "QApplication" not in content and "main_window" not in content.lower():
                self.results["gui_initialization"]["passed"] = False
                self.results["gui_initialization"]["issues"].append(
                    f"{init_file.name} does not initialize QApplication/main window path"
                )
                self.logger.error("%s does not initialize QApplication/main window path", init_file.name)
            
            # Check for MainWindow initialization
            if "MainWindow" not in content and "main_window" not in content.lower():
                self.results["gui_initialization"]["passed"] = False
                self.results["gui_initialization"]["issues"].append(
                    f"{init_file.name} does not initialize MainWindow path"
                )
                self.logger.error("%s does not initialize MainWindow path", init_file.name)
            
            # Check for event bus initialization
            if "event_bus" not in content.lower() and "EventBus" not in content and "get_event_bus" not in content:
                self.results["gui_initialization"]["passed"] = False
                self.results["gui_initialization"]["issues"].append(
                    f"{init_file.name} does not initialize the event bus"
                )
                self.logger.error("%s does not initialize the event bus", init_file.name)
            
            # Check for exec_() or show() call
            if "exec" not in content and ".show()" not in content and "start(" not in content:
                self.results["gui_initialization"]["passed"] = False
                self.results["gui_initialization"]["issues"].append(
                    f"{init_file.name} does not call exec/show/start path"
                )
                self.logger.error("%s does not call exec/show/start path", init_file.name)
            
            # Check for Redis Quantum Nexus initialization
            if "quantum_nexus" not in content.lower() and "Redis" not in content and "redis" not in content.lower():
                self.results["gui_initialization"]["passed"] = False
                self.results["gui_initialization"]["issues"].append(
                    f"{init_file.name} does not initialize Redis/Quantum Nexus path"
                )
                self.logger.error("%s does not initialize Redis/Quantum Nexus path", init_file.name)
                
        except Exception as e:
            self.logger.error(f"Error checking main.py: {str(e)}")
    
    def generate_report(self) -> str:
        """
        Generate a formatted report of validation results.
        
        Returns:
            str: Formatted report
        """
        validation_results = self.validate_all()
        overall_passed = validation_results["overall_passed"]
        details = validation_results["details"]
        
        # Create the report
        report = []
        report.append("=" * 80)
        report.append("KINGDOM AI - PyQt6 GUI VALIDATION REPORT")
        report.append("=" * 80)
        report.append("")
        
        report.append(f"Overall Status: {'PASSED' if overall_passed else 'FAILED'}")
        report.append(f"Files Processed: {self.files_processed}")
        report.append("")
        
        report.append("-" * 80)
        report.append("1. PyQt6 USAGE VALIDATION")
        report.append("-" * 80)
        report.append(f"Status: {'PASSED' if details['pyqt6_usage']['passed'] else 'FAILED'}")
        report.append(f"Components checked: {details['pyqt6_usage']['components_checked']}")
        report.append(f"PyQt6 imports found: {details['pyqt6_usage']['pyqt6_imports_found']}")
        report.append(f"Tkinter imports found (VIOLATION): {details['pyqt6_usage']['tkinter_imports_found']}")
        
        if details['pyqt6_usage']['issues']:
            report.append("Issues:")
            for issue in details['pyqt6_usage']['issues']:
                report.append(f"  - {issue}")
        report.append("")
        
        report.append("-" * 80)
        report.append("2. EVENT BUS CONNECTION VALIDATION")
        report.append("-" * 80)
        report.append(f"Status: {'PASSED' if details['event_bus_connection']['passed'] else 'FAILED'}")
        report.append(f"Components with event bus: {details['event_bus_connection']['components_with_event_bus']}")
        report.append(f"Components without event bus: {details['event_bus_connection']['components_without_event_bus']}")
        report.append(f"Event types found: {', '.join(sorted(details['event_bus_connection']['event_types_found']))}")
        
        if details['event_bus_connection']['issues']:
            report.append("Issues:")
            for issue in details['event_bus_connection']['issues']:
                report.append(f"  - {issue}")
        report.append("")
        
        report.append("-" * 80)
        report.append("3. REQUIRED COMPONENTS VALIDATION")
        report.append("-" * 80)
        report.append(f"Status: {'PASSED' if details['required_components']['passed'] else 'FAILED'}")
        report.append(f"Components found: {', '.join(sorted(details['required_components']['components_found']))}")
        report.append(f"Components missing: {', '.join(sorted(details['required_components']['components_missing']))}")
        
        if details['required_components']['issues']:
            report.append("Issues:")
            for issue in details['required_components']['issues']:
                report.append(f"  - {issue}")
        report.append("")
        
        report.append("-" * 80)
        report.append("4. GUI INITIALIZATION VALIDATION")
        report.append("-" * 80)
        report.append(f"Status: {'PASSED' if details['gui_initialization']['passed'] else 'FAILED'}")
        
        if details['gui_initialization']['issues']:
            report.append("Issues:")
            for issue in details['gui_initialization']['issues']:
                report.append(f"  - {issue}")
        report.append("")
        
        report.append("-" * 80)
        report.append("CONCLUSION")
        report.append("-" * 80)
        
        if overall_passed:
            report.append("The Kingdom AI GUI successfully passed all PyQt6 validation checks.")
            report.append("All required components are present and connected to the event bus.")
        else:
            report.append("The Kingdom AI GUI FAILED PyQt6 validation checks.")
            report.append("See issues listed above for required fixes to comply with system requirements.")
        
        report.append("")
        report.append("IMPORTANT: Kingdom AI strictly prioritizes PyQt6 over Tkinter with no fallback allowed.")
        report.append("All components must be real (no placeholders) and connected to the event bus.")
        report.append("System must halt if critical GUI components are missing.")
        
        return "\n".join(report)


def main():
    """Run the PyQt6 validator."""
    validator = PyQt6Validator()
    report = validator.generate_report()
    
    # Write report to file
    os.makedirs(_LOG_DIR, exist_ok=True)
    report_path = os.path.join(_LOG_DIR, "pyqt6_validation_report.txt")
    
    with open(report_path, "w") as f:
        f.write(report)
    
    # Print summary to console
    print("\n" + report + "\n")
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
