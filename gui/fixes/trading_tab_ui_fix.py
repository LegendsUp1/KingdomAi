#!/usr/bin/env python3
"""
Trading Tab UI Fix - Apply proper styling and layout
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt

def fix_trading_tab_layout(trading_tab):
    """Fix trading tab UI formatting issues"""
    
    # Ensure main layout has proper margins and spacing
    if hasattr(trading_tab, 'layout') and trading_tab.layout():
        layout = trading_tab.layout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
    
    # Fix control button labels if they exist
    button_labels = {
        'buy_button': '💰 BUY BTC',
        'sell_button': '💸 SELL BTC',
        'quick_buy_button': '⚡ Quick Buy',
        'quick_sell_button': '⚡ Quick Sell'
    }
    
    for attr_name, label_text in button_labels.items():
        if hasattr(trading_tab, attr_name):
            button = getattr(trading_tab, attr_name)
            button.setText(label_text)
            button.setMinimumHeight(40)
    
    # Fix section labels
    section_labels = [
        'trading_controls_label',
        'order_book_label',
        'recent_trades_label',
        'portfolio_label'
    ]
    
    for label_attr in section_labels:
        if hasattr(trading_tab, label_attr):
            label = getattr(trading_tab, label_attr)
            font = label.font()
            font.setPointSize(11)
            font.setBold(True)
            label.setFont(font)
    
    print("✅ Trading tab UI formatting applied")
    return True
