#!/usr/bin/env python3
"""
Kingdom AI Component Validator
Scans all components to identify missing methods, imports, and linting issues
"""

import os
import sys
import ast
import re
import importlib
import inspect
from typing import Dict, List, Set, Any, Optional, Tuple
from datetime import datetime

# Base paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KINGDOM_AI_ROOT = os.path.join(PROJECT_ROOT, "kingdom_ai")

# Add project root to path
sys.path.insert(0, PROJECT_ROOT)

class ComponentValidator:
    """Validates Kingdom AI components for completeness and correctness"""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.required_methods = {
            "BaseComponent": ["initialize", "shutdown"],
            "EventBus": ["subscribe", "publish", "unsubscribe"],
            "MiningDashboard": [
                "initialize", "_handle_worker_added", "_handle_worker_removed",
                "_handle_performance_update", "_handle_temperature_update",
                "_handle_reward_update", "_handle_alert_triggered", "_handle_alert_resolved"
            ],
            "SmartContractHandler": [
                "initialize", "load_contract", "call_contract_method", 
                "send_transaction", "register_event_listener"
            ],
            "SecurityManager": [
                "check_permission", "verify_proof", "check_rate_limit", "check_replay"
            ],
            "ThothAI": [
                "initialize", "analyze", "optimize", "predict", "recommend"
            ]
        }
        self.errors = []
        self.warnings = []
        self.suggestions = []
        
    def log_error(self, component, message):
        """Log an error"""
        error = f"ERROR in {component}: {message}"
        self.errors.append(error)
        if self.verbose:
            print(f"\033[91m{error}\033[0m")
            
    def log_warning(self, component, message):
        """Log a warning"""
        warning = f"WARNING in {component}: {message}"
        self.warnings.append(warning)
        if self.verbose:
            print(f"\033[93m{warning}\033[0m")
            
    def log_suggestion(self, component, message):
        """Log a suggestion"""
        suggestion = f"SUGGESTION for {component}: {message}"
        self.suggestions.append(suggestion)
        if self.verbose:
            print(f"\033[94m{suggestion}\033[0m")
            
    def find_python_files(self, start_dir: str) -> List[str]:
        """Find all Python files in a directory recursively"""
        python_files = []
        for root, _, files in os.walk(start_dir):
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))
        return python_files
    
    def parse_file(self, file_path: str) -> Optional[ast.Module]:
        """Parse a Python file to AST"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return ast.parse(f.read(), filename=file_path)
        except Exception as e:
            self.log_error(file_path, f"Failed to parse: {str(e)}")
            return None
    
    def validate_imports(self, file_path: str) -> None:
        """Validate imports in a file"""
        tree = self.parse_file(file_path)
        if not tree:
            return
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    try:
                        importlib.import_module(name.name)
                    except Exception as e:  # noqa: BLE001
                        self.log_error(file_path, f"Cannot import module '{name.name}': {e}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    try:
                        base_module = importlib.import_module(node.module)
                        for name in node.names:
                            if name.name == "*":
                                continue
                            if not hasattr(base_module, name.name):
                                self.log_error(file_path, f"Cannot import '{name.name}' from '{node.module}'")
                    except Exception as e:  # noqa: BLE001
                        self.log_error(file_path, f"Cannot import from module '{node.module}': {e}")
    
    def validate_class_methods(self, file_path: str) -> None:
        """Validate required methods in classes"""
        tree = self.parse_file(file_path)
        if not tree:
            return
            
        class_visitor = ClassVisitor()
        class_visitor.visit(tree)
        
        for class_name, methods in class_visitor.classes.items():
            if class_name in self.required_methods:
                for required_method in self.required_methods[class_name]:
                    if required_method not in methods:
                        self.log_error(file_path, f"Class '{class_name}' is missing required method '{required_method}'")
                    elif not methods[required_method]["has_body"]:
                        self.log_warning(file_path, f"Method '{required_method}' in class '{class_name}' has no implementation")
    
    def validate_event_handlers(self, file_path: str) -> None:
        """Validate event handlers are properly registered"""
        tree = self.parse_file(file_path)
        if not tree:
            return
            
        for node in ast.walk(tree):
            # Look for event_bus.subscribe calls
            if (isinstance(node, ast.Call) and 
                isinstance(node.func, ast.Attribute) and 
                node.func.attr == "subscribe"):
                
                # Check if we have an event type and handler function
                if (len(node.args) >= 2 and 
                    isinstance(node.args[0], ast.Str) and 
                    (isinstance(node.args[1], ast.Name) or isinstance(node.args[1], ast.Attribute))):
                    
                    event_type = node.args[0].s
                    handler_name = node.args[1].id if isinstance(node.args[1], ast.Name) else node.args[1].attr
                    
                    # Check if the handler exists
                    handler_found = False
                    for class_node in ast.walk(tree):
                        if isinstance(class_node, ast.ClassDef):
                            for method in class_node.body:
                                if isinstance(method, ast.FunctionDef) and method.name == handler_name:
                                    handler_found = True
                                    
                                    # Check if the handler is implemented
                                    if len(method.body) == 1 and isinstance(method.body[0], ast.Expr) and isinstance(method.body[0].value, ast.Ellipsis):
                                        self.log_warning(file_path, f"Event handler '{handler_name}' for event '{event_type}' has no implementation")
                    
                    if not handler_found:
                        self.log_error(file_path, f"Event handler '{handler_name}' for event '{event_type}' is not defined")
    
    def validate_components(self) -> Dict[str, Any]:
        """Validate all Kingdom AI components"""
        python_files = self.find_python_files(KINGDOM_AI_ROOT)
        
        # Group files by component
        components = {}
        for file_path in python_files:
            rel_path = os.path.relpath(file_path, KINGDOM_AI_ROOT)
            component = rel_path.split(os.sep)[0] if os.sep in rel_path else "core"
            
            if component not in components:
                components[component] = []
            components[component].append(file_path)
        
        # Validate each component
        for component, files in components.items():
            if self.verbose:
                print(f"\n\033[1mValidating component: {component}\033[0m")
                
            for file_path in files:
                if self.verbose:
                    print(f"  Checking {os.path.basename(file_path)}...")
                    
                self.validate_imports(file_path)
                self.validate_class_methods(file_path)
                self.validate_event_handlers(file_path)
        
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "components": components
        }
    
    def generate_report(self) -> str:
        """Generate a validation report"""
        report = [
            "# Kingdom AI Component Validation Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## Summary",
            f"- Total Errors: {len(self.errors)}",
            f"- Total Warnings: {len(self.warnings)}",
            f"- Total Suggestions: {len(self.suggestions)}",
            "",
            "## Errors",
        ]
        
        for error in self.errors:
            report.append(f"- {error}")
            
        report.extend(["", "## Warnings"])
        for warning in self.warnings:
            report.append(f"- {warning}")
            
        report.extend(["", "## Suggestions"])
        for suggestion in self.suggestions:
            report.append(f"- {suggestion}")
            
        return "\n".join(report)

class ClassVisitor(ast.NodeVisitor):
    """AST visitor to find classes and their methods"""
    
    def __init__(self):
        self.classes = {}
        self.current_class = None
        
    def visit_ClassDef(self, node):
        """Visit a class definition"""
        self.current_class = node.name
        self.classes[node.name] = {}
        
        # Visit all methods in the class
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                self.classes[node.name][child.name] = {
                    "has_body": len(child.body) > 0 and not (
                        len(child.body) == 1 and 
                        isinstance(child.body[0], ast.Expr) and 
                        isinstance(child.body[0].value, ast.Ellipsis)
                    )
                }
        
        # Continue visiting child nodes
        self.generic_visit(node)
        self.current_class = None

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Kingdom AI components")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--output", "-o", help="Output report to file")
    args = parser.parse_args()
    
    validator = ComponentValidator(verbose=args.verbose)
    validator.validate_components()
    
    report = validator.generate_report()
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print("\n" + report)
    
    # Exit with error code if there are errors
    sys.exit(1 if validator.errors else 0)

if __name__ == "__main__":
    main()
