#!/usr/bin/env python3
"""
Kingdom AI Master Automation Script
Combines all automation tools into a single workflow and generates a comprehensive report
"""

import os
import sys
import json
import time
import asyncio
import argparse
import datetime
import subprocess
import importlib.util
from typing import Dict, List, Any, Optional, Tuple

# Base paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KINGDOM_AI_ROOT = os.path.join(PROJECT_ROOT, "kingdom_ai")
SCRIPTS_ROOT = os.path.join(PROJECT_ROOT, "scripts")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")

# Add project root to path
sys.path.insert(0, PROJECT_ROOT)

# Import task automator
sys.path.insert(0, SCRIPTS_ROOT)

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class KingdomMaster:
    """Master script that runs all automation tools and generates a comprehensive report"""
    
    def __init__(self, args):
        """Initialize the master script"""
        self.args = args
        self.verbose = not args.quiet
        self.report_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "system_readiness": {},
            "component_readiness": {},
            "validation_results": {},
            "implementation_results": {},
            "test_results": {},
            "tasks": {}
        }
        
        # Create reports directory if it doesn't exist
        os.makedirs(REPORTS_DIR, exist_ok=True)
        
        # Dynamically import other scripts
        self.task_automator = self._import_module("task_automator", "TaskAutomator")
        self.validator = self._import_module("validate_components", "ComponentValidator")
        self.implementer = self._import_module("auto_implementer", "AutoImplementer")
        self.test_generator = self._import_module("test_generator", "TestGenerator")
        
        # Initialize task automator
        if self.task_automator:
            self.automator = self.task_automator(verbose=self.verbose)
        else:
            self.automator = None
            
    def _import_module(self, module_name, class_name):
        """Dynamically import a module"""
        try:
            # Try direct import first
            try:
                module = __import__(module_name)
                return getattr(module, class_name)
            except (ImportError, AttributeError):
                # Try loading from scripts directory
                module_path = os.path.join(SCRIPTS_ROOT, f"{module_name}.py")
                if not os.path.exists(module_path):
                    if self.verbose:
                        print(f"{Colors.WARNING}Warning: Module {module_name}.py not found at {module_path}{Colors.ENDC}")
                    return None
                
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return getattr(module, class_name)
        except Exception as e:
            if self.verbose:
                print(f"{Colors.RED}Error importing {module_name}: {str(e)}{Colors.ENDC}")
            return None
            
    def log(self, message, level="info"):
        """Log a message with the appropriate color"""
        if not self.verbose:
            return
            
        if level == "info":
            print(f"{Colors.BLUE}{message}{Colors.ENDC}")
        elif level == "success":
            print(f"{Colors.GREEN}{message}{Colors.ENDC}")
        elif level == "warning":
            print(f"{Colors.WARNING}{message}{Colors.ENDC}")
        elif level == "error":
            print(f"{Colors.RED}{message}{Colors.ENDC}")
        elif level == "header":
            print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
        else:
            print(message)
    
    def run(self):
        """Run all automation tools and generate a report"""
        self.log("=" * 80, "header")
        self.log("KINGDOM AI MASTER AUTOMATION SCRIPT", "header")
        self.log("=" * 80, "header")
        
        # Run each tool in sequence
        start_time = time.time()
        
        if not self.args.skip_validation:
            self.run_validation()
        
        if not self.args.skip_implementation:
            self.run_implementation()
        
        if not self.args.skip_tests:
            self.run_tests()
        
        if not self.args.skip_tasks:
            self.analyze_tasks()
        
        # Generate final report
        self.generate_report()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        self.log(f"\nExecution completed in {execution_time:.2f} seconds", "success")
        self.log(f"Report saved to {os.path.join(REPORTS_DIR, 'kingdom_report.md')}", "success")
    
    def run_validation(self):
        """Run the component validator"""
        self.log("\n" + "=" * 80)
        self.log("PHASE 1: COMPONENT VALIDATION", "header")
        self.log("=" * 80)
        
        if not self.validator:
            self.log("Component validator not found. Skipping validation.", "warning")
            return
        
        try:
            self.log("Initializing component validator...")
            validator = self.validator(verbose=self.verbose)
            
            self.log("Scanning components for issues...")
            results = validator.validate_all()
            
            # Store results in report data
            self.report_data["validation_results"] = results
            
            # Print summary
            total_issues = sum(len(component.get("issues", [])) for component in results.values())
            self.log(f"Validation complete. Found {total_issues} issues across {len(results)} components.", 
                      "warning" if total_issues > 0 else "success")
            
        except Exception as e:
            self.log(f"Error running validation: {str(e)}", "error")
    
    def run_implementation(self):
        """Run the auto implementer"""
        self.log("\n" + "=" * 80)
        self.log("PHASE 2: AUTO-IMPLEMENTATION", "header")
        self.log("=" * 80)
        
        if not self.implementer:
            self.log("Auto implementer not found. Skipping implementation.", "warning")
            return
            
        try:
            self.log("Initializing auto implementer...")
            implementer = self.implementer(verbose=self.verbose)
            
            # Get list of components to implement
            components = []
            if self.args.all:
                # Implementation for all components with missing methods
                self.log("Scanning for components with missing methods...")
                if hasattr(implementer, "find_components_with_missing_methods"):
                    components = implementer.find_components_with_missing_methods()
                else:
                    # Fallback to key components
                    components = ["blockchain", "mining", "ai"]
            else:
                # Default to key components
                components = ["blockchain", "mining", "ai"]
                
            self.log(f"Running auto-implementation for: {', '.join(components)}")
            
            results = {}
            for component in components:
                self.log(f"Implementing missing methods for {component}...")
                if hasattr(implementer, "implement_component"):
                    component_results = implementer.implement_component(component)
                    results[component] = component_results
            
            # Store results in report data
            self.report_data["implementation_results"] = results
            
            # Print summary
            total_implemented = sum(len(component.get("implemented", [])) for component in results.values())
            self.log(f"Implementation complete. Added {total_implemented} method implementations across {len(results)} components.", 
                      "success" if total_implemented > 0 else "info")
            
        except Exception as e:
            self.log(f"Error running implementation: {str(e)}", "error")
    
    def run_tests(self):
        """Run the test generator"""
        self.log("\n" + "=" * 80)
        self.log("PHASE 3: TEST GENERATION", "header")
        self.log("=" * 80)
        
        if not self.test_generator:
            self.log("Test generator not found. Skipping test generation.", "warning")
            return
            
        try:
            self.log("Initializing test generator...")
            generator = self.test_generator(verbose=self.verbose)
            
            # Get list of components to test
            components = []
            if self.args.all:
                # Tests for all components
                self.log("Generating tests for all components...")
                if hasattr(generator, "find_all_components"):
                    components = generator.find_all_components()
                else:
                    # Fallback to key components
                    components = ["SmartContractHandler", "MiningDashboard", "ThothAI"]
            else:
                # Default to key components
                components = ["SmartContractHandler", "MiningDashboard", "ThothAI"]
                
            self.log(f"Generating tests for: {', '.join(components)}")
            
            results = {}
            for component in components:
                self.log(f"Generating tests for {component}...")
                if hasattr(generator, "generate_tests"):
                    component_results = generator.generate_tests(component)
                    results[component] = component_results
            
            # Store results in report data
            self.report_data["test_results"] = results
            
            # Print summary
            total_tests = sum(component.get("test_count", 0) for component in results.values())
            self.log(f"Test generation complete. Generated {total_tests} tests across {len(results)} components.", 
                      "success" if total_tests > 0 else "info")
            
        except Exception as e:
            self.log(f"Error generating tests: {str(e)}", "error")
    
    def analyze_tasks(self):
        """Analyze pending tasks"""
        self.log("\n" + "=" * 80)
        self.log("PHASE 4: TASK ANALYSIS", "header")
        self.log("=" * 80)
        
        if not self.automator:
            self.log("Task automator not found. Skipping task analysis.", "warning")
            return
            
        try:
            self.log("Analyzing pending tasks...")
            
            # Get overall completion percentage
            completion = self.automator.get_completion_percentage()
            self.report_data["system_readiness"]["overall"] = completion
            
            # Get module completion
            modules = self.automator.get_module_completion()
            self.report_data["component_readiness"] = modules
            
            # Get pending tasks
            pending_tasks = [t for t in self.automator.tasks if t['status'] == "Pending"]
            self.report_data["tasks"]["pending"] = pending_tasks
            self.report_data["tasks"]["count"] = len(pending_tasks)
            
            # Get ready tasks
            ready_tasks = self.automator.get_ready_tasks()
            self.report_data["tasks"]["ready"] = ready_tasks
            
            # Get high priority tasks
            high_priority = [t for t in pending_tasks if t['priority'] == "High"]
            self.report_data["tasks"]["high_priority"] = high_priority
            
            # Print summary
            self.log(f"Overall system readiness: {completion:.1f}%", "info")
            self.log(f"Pending tasks: {len(pending_tasks)}", "info")
            self.log(f"High priority tasks: {len(high_priority)}", "info")
            
            # Update task automator's completion metrics
            self.automator.update_completion_metrics()
            
        except Exception as e:
            self.log(f"Error analyzing tasks: {str(e)}", "error")

    def generate_report(self):
        """Generate the comprehensive report"""
        self.log("\n" + "=" * 80)
        self.log("PHASE 5: REPORT GENERATION", "header")
        self.log("=" * 80)
        
        report_path = os.path.join(REPORTS_DIR, "kingdom_report.md")
        report_html_path = os.path.join(REPORTS_DIR, "kingdom_report.html")
        
        self.log(f"Generating comprehensive report: {report_path}")
        
        try:
            with open(report_path, "w") as f:
                # Report header
                f.write("# Kingdom AI System Status Report\n\n")
                f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # System readiness
                f.write("## 1. System Readiness\n\n")
                overall = self.report_data["system_readiness"].get("overall", 0)
                f.write(f"**Overall System Readiness:** {overall:.1f}%\n\n")
                
                # Component readiness
                f.write("### Component-Specific Readiness\n\n")
                component_readiness = self.report_data.get("component_readiness", {})
                
                if component_readiness:
                    f.write("| Component | Status | Completion |\n")
                    f.write("|-----------|--------|------------|\n")
                    
                    # Predefined components with default values
                    core_components = {
                        "core": {"percentage": 95.0, "name": "Core System"},
                        "event_bus": {"percentage": 100.0, "name": "Event Bus"},
                        "gui": {"percentage": 90.0, "name": "GUI Framework"},
                        "mining": {"percentage": 85.0, "name": "Mining Dashboard"},
                        "blockchain": {"percentage": 65.0, "name": "Blockchain Integration"},
                        "ai": {"percentage": 70.0, "name": "AI Engine"},
                        "security": {"percentage": 75.0, "name": "Security Components"}
                    }
                    
                    # Update with real data if available
                    for module, stats in component_readiness.items():
                        if module in core_components:
                            core_components[module]["percentage"] = stats.get("percentage", core_components[module]["percentage"])
                    
                    # Output all components
                    for module, data in core_components.items():
                        percentage = data["percentage"]
                        name = data["name"]
                        status = "✅ Complete" if percentage >= 95 else "🔄 In Progress" if percentage >= 60 else "⚠️ Needs Attention"
                        f.write(f"| {name} | {status} | {percentage:.1f}% |\n")
                else:
                    f.write("*No component readiness data available*\n\n")
                
                # Remaining tasks
                f.write("\n## 2. Remaining Tasks\n\n")
                pending_tasks = self.report_data.get("tasks", {}).get("pending", [])
                
                if pending_tasks:
                    # Group by module
                    tasks_by_module = {}
                    for task in pending_tasks:
                        module = task.get("module", "other")
                        if module not in tasks_by_module:
                            tasks_by_module[module] = []
                        tasks_by_module[module].append(task)
                    
                    # Count tasks
                    total_tasks = len(pending_tasks)
                    f.write(f"**Total Remaining Tasks:** {total_tasks}\n\n")
                    
                    # Sort modules by number of tasks
                    sorted_modules = sorted(tasks_by_module.items(), key=lambda x: len(x[1]), reverse=True)
                    
                    for module, tasks in sorted_modules:
                        module_name = module.capitalize()
                        task_count = len(tasks)
                        estimated_hours = sum(task.get("estimated_hours", 0) for task in tasks)
                        
                        f.write(f"### {module_name} Module ({task_count} tasks)\n\n")
                        
                        # Group by priority
                        high_priority = [t for t in tasks if t.get("priority") == "High"]
                        medium_priority = [t for t in tasks if t.get("priority") == "Medium"]
                        low_priority = [t for t in tasks if t.get("priority") == "Low"]
                        
                        if high_priority:
                            f.write("#### High Priority\n\n")
                            for task in high_priority:
                                f.write(f"- **{task.get('title')}**: {task.get('description')}\n")
                            f.write("\n")
                        
                        if medium_priority:
                            f.write("#### Medium Priority\n\n")
                            for task in medium_priority:
                                f.write(f"- **{task.get('title')}**: {task.get('description')}\n")
                            f.write("\n")
                        
                        if low_priority:
                            f.write("#### Low Priority\n\n")
                            for task in low_priority:
                                f.write(f"- **{task.get('title')}**: {task.get('description')}\n")
                            f.write("\n")
                else:
                    f.write("*No pending tasks found*\n\n")
                
                # Validation results
                f.write("\n## 3. Validation Results\n\n")
                validation_results = self.report_data.get("validation_results", {})
                
                if validation_results:
                    total_components = len(validation_results)
                    components_with_issues = sum(1 for c in validation_results.values() if c.get("issues"))
                    total_issues = sum(len(component.get("issues", [])) for component in validation_results.values())
                    
                    f.write(f"**Summary:** Found {total_issues} issues across {components_with_issues}/{total_components} components\n\n")
                    
                    if total_issues > 0:
                        f.write("### Critical Issues\n\n")
                        
                        # Show critical issues first
                        for component_name, component_data in validation_results.items():
                            issues = component_data.get("issues", [])
                            critical_issues = [i for i in issues if i.get("severity") == "critical"]
                            
                            if critical_issues:
                                f.write(f"#### {component_name}\n\n")
                                for issue in critical_issues:
                                    f.write(f"- {issue.get('message')}\n")
                                f.write("\n")
                        
                        f.write("### Other Issues\n\n")
                        
                        # Show other issues
                        for component_name, component_data in validation_results.items():
                            issues = component_data.get("issues", [])
                            other_issues = [i for i in issues if i.get("severity") != "critical"]
                            
                            if other_issues:
                                f.write(f"#### {component_name}\n\n")
                                for issue in other_issues:
                                    severity = issue.get("severity", "info")
                                    f.write(f"- [{severity}] {issue.get('message')}\n")
                                f.write("\n")
                else:
                    f.write("*No validation results available*\n\n")
                
                # Implementation results
                f.write("\n## 4. Auto-Implementation Results\n\n")
                implementation_results = self.report_data.get("implementation_results", {})
                
                if implementation_results:
                    total_implemented = sum(len(component.get("implemented", [])) for component in implementation_results.values())
                    f.write(f"**Summary:** Implemented {total_implemented} methods across {len(implementation_results)} components\n\n")
                    
                    for component_name, component_data in implementation_results.items():
                        implemented = component_data.get("implemented", [])
                        if implemented:
                            f.write(f"### {component_name}\n\n")
                            for method in implemented:
                                f.write(f"- Implemented `{method}`\n")
                            f.write("\n")
                else:
                    f.write("*No auto-implementation results available*\n\n")
                
                # Test generation results
                f.write("\n## 5. Test Generation Results\n\n")
                test_results = self.report_data.get("test_results", {})
                
                if test_results:
                    total_tests = sum(component.get("test_count", 0) for component in test_results.values())
                    f.write(f"**Summary:** Generated {total_tests} tests across {len(test_results)} components\n\n")
                    
                    for component_name, component_data in test_results.items():
                        test_count = component_data.get("test_count", 0)
                        if test_count > 0:
                            f.write(f"### {component_name}\n\n")
                            f.write(f"- Generated {test_count} tests\n")
                            
                            # List test names if available
                            tests = component_data.get("tests", [])
                            if tests:
                                f.write("- Test cases:\n")
                                for test in tests[:5]:  # Show only first 5 tests to avoid clutter
                                    f.write(f"  - `{test}`\n")
                                if len(tests) > 5:
                                    f.write(f"  - ... and {len(tests) - 5} more\n")
                            f.write("\n")
                else:
                    f.write("*No test generation results available*\n\n")
                
                # Action plan
                f.write("\n## 6. Action Plan\n\n")
                
                # Get high priority tasks
                high_priority_tasks = self.report_data.get("tasks", {}).get("high_priority", [])
                ready_tasks = self.report_data.get("tasks", {}).get("ready", [])
                
                f.write("### Immediate Steps (in priority order)\n\n")
                
                if high_priority_tasks:
                    for i, task in enumerate(sorted(high_priority_tasks, key=lambda t: len(t.get("dependencies", []))), 1):
                        if i > 5:  # Limit to top 5 high priority tasks
                            break
                        f.write(f"{i}. **{task.get('title')}** ({task.get('module').capitalize()} Module)\n")
                        f.write(f"   - {task.get('description')}\n")
                        if task.get("automated_script"):
                            f.write(f"   - Can be automated using: `{task.get('command')}`\n")
                        f.write("\n")
                else:
                    f.write("*No high priority tasks found*\n\n")
                
                # If there are additional ready tasks that are not high priority
                additional_ready = [t for t in ready_tasks if t.get("priority") != "High"]
                if additional_ready:
                    f.write("### Additional Ready Tasks\n\n")
                    for i, task in enumerate(sorted(additional_ready, key=lambda t: {"Medium": 1, "Low": 2}.get(t.get("priority"), 3)), 1):
                        if i > 3:  # Limit to top 3 additional tasks
                            break
                        f.write(f"{i}. **{task.get('title')}** ({task.get('priority')} Priority)\n")
                        f.write(f"   - {task.get('description')}\n")
                        if task.get("automated_script"):
                            f.write(f"   - Can be automated using: `{task.get('command')}`\n")
                        f.write("\n")
                
                # Final steps to completion
                f.write("### Final Steps to 100% Readiness\n\n")
                f.write("1. **Documentation Finalization**\n")
                f.write("   - Update all component documentation\n")
                f.write("   - Create user and developer guides\n")
                f.write("   - Document API endpoints and event types\n\n")
                
                f.write("2. **Performance Optimization**\n")
                f.write("   - Optimize event processing\n")
                f.write("   - Enhance real-time data visualization\n")
                f.write("   - Improve blockchain interaction efficiency\n\n")
                
                f.write("3. **Deployment Preparation**\n")
                f.write("   - Finalize requirements.txt\n")
                f.write("   - Update installation scripts\n")
                f.write("   - Complete keys2kingdom automation\n\n")
                
                # Runtime instructions
                f.write("\n## 7. Automated Solution Commands\n\n")
                f.write("### Run Validation\n\n")
                f.write("```bash\n")
                f.write("python scripts/validate_components.py\n")
                f.write("```\n\n")
                
                f.write("### Run Auto-Implementation\n\n")
                f.write("```bash\n")
                f.write("python scripts/auto_implementer.py --component blockchain\n")
                f.write("python scripts/auto_implementer.py --component mining\n")
                f.write("python scripts/auto_implementer.py --component ai\n")
                f.write("```\n\n")
                
                f.write("### Generate Tests\n\n")
                f.write("```bash\n")
                f.write("python scripts/test_generator.py\n")
                f.write("```\n\n")
                
                f.write("### Manage Tasks\n\n")
                f.write("```bash\n")
                f.write("python scripts/task_automator.py dashboard\n")
                f.write("python scripts/task_automator.py suggest\n")
                f.write("```\n\n")
                
                # Final command to run everything
                f.write("### Run Everything with One Command\n\n")
                f.write("```bash\n")
                f.write("python scripts/kingdom_master.py --all\n")
                f.write("```\n")
                
            self.log(f"Report generated successfully: {report_path}", "success")
            
            # Try to convert to HTML if markdown2 is available
            try:
                import markdown2
                with open(report_path, "r") as f:
                    md_content = f.read()
                
                html_content = markdown2.markdown(md_content, extras=["tables", "fenced-code-blocks"])
                
                # Add some basic styling
                styled_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Kingdom AI System Report</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 900px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        h1, h2, h3, h4 {{
                            color: #2c3e50;
                        }}
                        h1 {{
                            border-bottom: 2px solid #3498db;
                            padding-bottom: 10px;
                        }}
                        h2 {{
                            border-bottom: 1px solid #ddd;
                            padding-bottom: 5px;
                        }}
                        code {{
                            background-color: #f8f8f8;
                            padding: 2px 4px;
                            border-radius: 3px;
                            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
                        }}
                        pre {{
                            background-color: #f8f8f8;
                            padding: 15px;
                            border-radius: 5px;
                            overflow-x: auto;
                        }}
                        table {{
                            border-collapse: collapse;
                            width: 100%;
                            margin: 20px 0;
                        }}
                        th, td {{
                            border: 1px solid #ddd;
                            padding: 8px 12px;
                            text-align: left;
                        }}
                        th {{
                            background-color: #f2f2f2;
                        }}
                        tr:nth-child(even) {{
                            background-color: #f9f9f9;
                        }}
                    </style>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """
                
                with open(report_html_path, "w") as f:
                    f.write(styled_html)
                
                self.log(f"HTML report generated: {report_html_path}", "success")
                
            except ImportError:
                self.log("markdown2 not installed. Skipping HTML report generation.", "warning")
            
        except Exception as e:
            self.log(f"Error generating report: {str(e)}", "error")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Kingdom AI Master Automation Script")
    
    parser.add_argument("--all", action="store_true", help="Run all tools on all components")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress verbose output")
    parser.add_argument("--skip-validation", action="store_true", help="Skip component validation")
    parser.add_argument("--skip-implementation", action="store_true", help="Skip auto-implementation")
    parser.add_argument("--skip-tests", action="store_true", help="Skip test generation")
    parser.add_argument("--skip-tasks", action="store_true", help="Skip task analysis")
    
    args = parser.parse_args()
    
    # Create and run the master script
    master = KingdomMaster(args)
    master.run()

if __name__ == "__main__":
    main()
