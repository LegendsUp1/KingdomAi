#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
os.environ["QT_API"] = "PyQt6"

import pyqtgraph as pg
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvas
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget
from PyQt6.QtCore import QTimer
import numpy as np
import logging

logger = logging.getLogger(__name__)

class StateOfTheArtDualPlotSystem(QWidget):
    """Ultimate plotting system: PyQtGraph + Matplotlib integration."""
    def __init__(self):
        super().__init__()
        self.setup_ui()
        logger.info("🚀 State-of-the-art dual plotting system initialized")

    def setup_ui(self):
        layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        self.pyqtgraph_widget = pg.PlotWidget()
        self.tab_widget.addTab(self.pyqtgraph_widget, "⚡ PyQtGraph (Ultra-Fast)")
        self.matplotlib_widget = FigureCanvas(plt.Figure())
        self.tab_widget.addTab(self.matplotlib_widget, "📊 Matplotlib (Professional)")
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

    def plot_realtime_data(self, x_data, y_data):
        """Plot real-time data using ultra-fast PyQtGraph."""
        self.pyqtgraph_widget.plot(x_data, y_data, pen="cyan")
