#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class AdvancedTradingChart(QWidget):
    """State-of-the-art trading charts with PyQtGraph."""
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)
