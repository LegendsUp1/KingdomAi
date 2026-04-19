# Kingdom AI Automation Tools

This directory contains automation tools designed to streamline the development and maintenance of the Kingdom AI system.

## Overview

The automation tools are designed to:

1. Validate all components
2. Auto-implement missing methods
3. Generate tests
4. Track and manage tasks
5. Generate comprehensive reports

## Available Scripts

### Main Scripts

- **kingdom_master.py**: The main script that runs all automation tools and generates a comprehensive report
- **validate_components.py**: Validates all components for missing methods, imports, and linting issues
- **auto_implementer.py**: Automatically implements missing methods in components
- **test_generator.py**: Generates unit and integration tests for components
- **task_automator.py**: Tracks and manages tasks for the project

### Helper Scripts

- **kingdom_report.bat**: Windows batch script to run the master automation and open the generated report
- **kingdom_tasks.bat**: Windows batch script to manage tasks
- **kingdom_tasks**: Unix/Linux script to manage tasks

## Quick Start

For a complete system analysis and report, simply run:

```bash
kingdom_report.bat
```

This will:
1. Run validation on all components
2. Auto-implement missing methods
3. Generate tests
4. Analyze pending tasks
5. Generate a comprehensive HTML report
6. Open the report in your default web browser

## Individual Tool Usage

### Component Validation

```bash
python scripts/validate_components.py
```

### Auto-Implementation

```bash
python scripts/auto_implementer.py --component [component_name]
```

### Test Generation

```bash
python scripts/test_generator.py --component [component_name]
```

### Task Management

View dashboard:
```bash
python scripts/task_automator.py dashboard
```

List tasks:
```bash
python scripts/task_automator.py list
```

View task details:
```bash
python scripts/task_automator.py view [task_id]
```

Update task status:
```bash
python scripts/task_automator.py update [task_id] [status]
```

Run automated task:
```bash
python scripts/task_automator.py run [task_id]
```

## Master Script Options

```bash
python scripts/kingdom_master.py [options]
```

Options:
- `--all`: Run all tools on all components
- `--quiet`: Suppress verbose output
- `--skip-validation`: Skip component validation
- `--skip-implementation`: Skip auto-implementation
- `--skip-tests`: Skip test generation
- `--skip-tasks`: Skip task analysis

## Generated Reports

Reports are saved in the `reports` directory:

- `kingdom_report.md`: Markdown report
- `kingdom_report.html`: HTML report (if markdown2 is installed)

The report includes:
- System readiness statistics
- Component-specific readiness
- Remaining tasks grouped by module and priority
- Validation results with issues found
- Auto-implementation results
- Test generation results
- Action plan with next steps
