#!/usr/bin/env python3
"""
Code Generator Tab - Wrapper for gui.frames.code_generator_qt

This file ensures compatibility with import statements expecting
code_generator_tab in gui.qt_frames directory.
"""

# Import from the actual location
from gui.frames.code_generator_qt import CodeGeneratorQt

# Re-export for compatibility
CodeGeneratorTab = CodeGeneratorQt

__all__ = ['CodeGeneratorTab', 'CodeGeneratorQt']
