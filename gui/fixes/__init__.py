#!/usr/bin/env python3
"""Auto-apply all GUI fixes on startup"""

def apply_all_fixes(main_window):
    """Apply all UI fixes to main window tabs"""
    try:
        # Fix Trading Tab UI
        if hasattr(main_window, 'trading_tab'):
            from gui.fixes.trading_tab_ui_fix import fix_trading_tab_layout
            fix_trading_tab_layout(main_window.trading_tab)
            print("✅ Applied trading tab UI fixes")
    except Exception as e:
        print(f"⚠️ Could not apply UI fixes: {e}")
