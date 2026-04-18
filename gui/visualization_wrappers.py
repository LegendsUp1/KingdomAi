#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualization wrapper modules for the Kingdom AI system.
Provides wrappers around various visualization libraries for advanced GUI features.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

# Set up logging
logger = logging.getLogger(__name__)

# Import necessary libraries based on availability
HAS_MATPLOTLIB = False
HAS_PLOTLY = False
HAS_SEABORN = False
HAS_PYQTGRAPH = False
HAS_BOKEH = False

# Try to import Matplotlib
try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
    logger.debug("Matplotlib visualization wrapper loaded")
except ImportError:
    logger.debug("Matplotlib not available")

# Try to import Plotly
try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
    logger.debug("Plotly visualization wrapper loaded")
except ImportError:
    logger.debug("Plotly not available")

# Try to import Seaborn
try:
    import seaborn as sns
    HAS_SEABORN = True
    logger.debug("Seaborn visualization wrapper loaded")
except ImportError:
    logger.debug("Seaborn not available")

# Try to import PyQtGraph
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
    logger.debug("PyQtGraph visualization wrapper loaded")
except ImportError:
    logger.debug("PyQtGraph not available")

# Try to import Bokeh
try:
    from bokeh.plotting import figure
    from bokeh.resources import CDN
    from bokeh.embed import file_html
    HAS_BOKEH = True
    logger.debug("Bokeh visualization wrapper loaded")
except ImportError:
    logger.debug("Bokeh not available")

class MatplotlibWrapper:
    """Wrapper for Matplotlib visualizations."""
    
    def __init__(self):
        self.available = HAS_MATPLOTLIB
        if not self.available:
            logger.warning("MatplotlibWrapper instantiated but Matplotlib is not available")
    
    def create_figure(self, width=10, height=6, dpi=100):
        """Create a new Matplotlib figure."""
        if not self.available:
            logger.warning("Attempted to create Matplotlib figure but library is not available")
            return None
            
        fig = Figure(figsize=(width, height), dpi=dpi)
        return fig
    
    def create_canvas(self, figure):
        """Create a canvas for a Matplotlib figure."""
        if not self.available:
            logger.warning("Attempted to create Matplotlib canvas but library is not available")
            return None
            
        return FigureCanvas(figure)
    
    def draw_line_chart(self, x_data, y_data, title="Line Chart", x_label="X", y_label="Y", 
                         color='blue', width=10, height=6, dpi=100):
        """Draw a line chart with the provided data."""
        if not self.available:
            logger.warning("Attempted to draw Matplotlib chart but library is not available")
            return None
            
        fig = self.create_figure(width, height, dpi)
        ax = fig.add_subplot(111)
        ax.plot(x_data, y_data, color=color)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        fig.tight_layout()
        
        return FigureCanvas(fig)
    
    def draw_bar_chart(self, x_data, y_data, title="Bar Chart", x_label="Categories", y_label="Values", 
                       color='blue', width=10, height=6, dpi=100):
        """Draw a bar chart with the provided data."""
        if not self.available:
            logger.warning("Attempted to draw Matplotlib chart but library is not available")
            return None
            
        fig = self.create_figure(width, height, dpi)
        ax = fig.add_subplot(111)
        ax.bar(x_data, y_data, color=color)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        fig.tight_layout()
        
        return FigureCanvas(fig)
    
    def draw_scatter_plot(self, x_data, y_data, title="Scatter Plot", x_label="X", y_label="Y", 
                          color='blue', width=10, height=6, dpi=100):
        """Draw a scatter plot with the provided data."""
        if not self.available:
            logger.warning("Attempted to draw Matplotlib chart but library is not available")
            return None
            
        fig = self.create_figure(width, height, dpi)
        ax = fig.add_subplot(111)
        ax.scatter(x_data, y_data, color=color)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        fig.tight_layout()
        
        return FigureCanvas(fig)
    
    def draw_pie_chart(self, data, labels, title="Pie Chart", width=10, height=6, dpi=100):
        """Draw a pie chart with the provided data."""
        if not self.available:
            logger.warning("Attempted to draw Matplotlib chart but library is not available")
            return None
            
        fig = self.create_figure(width, height, dpi)
        ax = fig.add_subplot(111)
        ax.pie(data, labels=labels, autopct='%1.1f%%')
        ax.set_title(title)
        fig.tight_layout()
        
        return FigureCanvas(fig)

class PlotlyWrapper:
    """Wrapper for Plotly visualizations."""
    
    def __init__(self):
        self.available = HAS_PLOTLY
        if not self.available:
            logger.warning("PlotlyWrapper instantiated but Plotly is not available")
    
    def create_line_chart(self, x_data, y_data, title="Line Chart", x_title="X", y_title="Y"):
        """Create a Plotly line chart."""
        if not self.available:
            logger.warning("Attempted to create Plotly chart but library is not available")
            return None
            
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='lines'))
        fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title)
        
        return fig
    
    def create_bar_chart(self, x_data, y_data, title="Bar Chart", x_title="Categories", y_title="Values"):
        """Create a Plotly bar chart."""
        if not self.available:
            logger.warning("Attempted to create Plotly chart but library is not available")
            return None
            
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_data, y=y_data))
        fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title)
        
        return fig
    
    def create_scatter_plot(self, x_data, y_data, title="Scatter Plot", x_title="X", y_title="Y"):
        """Create a Plotly scatter plot."""
        if not self.available:
            logger.warning("Attempted to create Plotly chart but library is not available")
            return None
            
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='markers'))
        fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title)
        
        return fig
    
    def create_pie_chart(self, data, labels, title="Pie Chart"):
        """Create a Plotly pie chart."""
        if not self.available:
            logger.warning("Attempted to create Plotly chart but library is not available")
            return None
            
        fig = go.Figure()
        fig.add_trace(go.Pie(values=data, labels=labels))
        fig.update_layout(title=title)
        
        return fig

# Create wrapper instances for use in the application
matplotlib_wrapper = MatplotlibWrapper()
plotly_wrapper = PlotlyWrapper()

# Export visualization status
HAS_VISUALIZATIONS = any([HAS_MATPLOTLIB, HAS_PLOTLY, HAS_SEABORN, HAS_PYQTGRAPH, HAS_BOKEH])
if HAS_VISUALIZATIONS:
    logger.info("Advanced visualizations enabled")
else:
    logger.warning("Advanced visualizations disabled - no visualization libraries available")
