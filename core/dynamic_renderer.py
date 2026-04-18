#!/usr/bin/env python3
"""
Kingdom AI - Dynamic Renderer
Automatically renders ANY data type with appropriate visualizations.
Works with trading, mining, wallet, blockchain, books, VR, code, AI, and custom data.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from PyQt6.QtGui import QPainter, QColor, QFont, QLinearGradient, QImage
from PyQt6.QtCore import Qt, QRect

logger = logging.getLogger("KingdomAI.DynamicRenderer")

class DynamicRenderer:
    """Universal renderer that adapts to any data type automatically."""
    
    def __init__(self):
        """Initialize the dynamic renderer."""
        self.logger = logger
        
        # Registry of rendering functions by data type
        self.renderers: Dict[str, Callable] = {
            'financial': self._render_financial,
            'chart': self._render_chart,
            'stats': self._render_stats,
            'list': self._render_list,
            'media': self._render_media,
            'code': self._render_code,
            'status': self._render_status,
            'network': self._render_network,
            'gauge': self._render_gauge,
            'timeline': self._render_timeline,
            'grid': self._render_grid,
            'text': self._render_text,
            'generic': self._render_generic
        }
    
    def render_data(self, painter: QPainter, width: int, height: int, 
                   data: Dict[str, Any], hints: Optional[Dict[str, Any]] = None) -> bool:
        """Render any data with automatic type detection.
        
        Args:
            painter: QPainter instance
            width: Canvas width
            height: Canvas height
            data: Data to render
            hints: Optional rendering hints (type, color, icon, etc.)
            
        Returns:
            True if rendered successfully
        """
        hints = hints or {}
        
        # Detect data type if not specified
        data_type = hints.get('type') or self._detect_data_type(data)
        
        # Get appropriate renderer
        renderer = self.renderers.get(data_type, self._render_generic)
        
        try:
            renderer(painter, width, height, data, hints)
            return True
        except Exception as e:
            logger.error(f"Rendering failed for type {data_type}: {e}")
            # Fallback to generic renderer
            try:
                self._render_generic(painter, width, height, data, hints)
                return True
            except:
                return False
    
    def _detect_data_type(self, data: Dict[str, Any]) -> str:
        """Automatically detect data type from structure.
        
        Args:
            data: Data dictionary
            
        Returns:
            Detected type string
        """
        # Financial data detection
        if any(key in data for key in ['value', 'price', 'balance', 'pnl', 'revenue', 'cost']):
            if any(key in data for key in ['currency', 'usd', 'btc', 'eth']):
                return 'financial'
        
        # Chart data detection
        if 'data_points' in data or 'series' in data or 'values' in data:
            return 'chart'
        
        # Stats/metrics detection
        if 'metrics' in data or 'statistics' in data:
            return 'stats'
        
        # List detection
        if 'items' in data or 'list' in data or isinstance(data.get('data'), list):
            return 'list'
        
        # Media detection (books, images, videos)
        if any(key in data for key in ['title', 'cover_url', 'image_url', 'media_url']):
            return 'media'
        
        # Code detection
        if 'code' in data or 'source' in data or 'contract' in data:
            return 'code'
        
        # Status detection
        if 'status' in data or 'state' in data or 'health' in data:
            return 'status'
        
        # Network/graph detection
        if 'nodes' in data or 'edges' in data or 'graph' in data:
            return 'network'
        
        # Gauge/progress detection
        if 'progress' in data or 'percentage' in data or 'level' in data:
            return 'gauge'
        
        # Timeline detection
        if 'events' in data or 'timeline' in data or 'history' in data:
            return 'timeline'
        
        # Grid detection
        if 'grid' in data or 'matrix' in data:
            return 'grid'
        
        return 'generic'
    
    def _render_financial(self, painter: QPainter, width: int, height: int, 
                         data: Dict[str, Any], hints: Dict[str, Any]):
        """Render financial data (money, prices, balances)."""
        value = data.get('value', data.get('balance', data.get('price', 0)))
        currency = data.get('currency', '$')
        label = data.get('label', hints.get('label', 'Value'))
        
        # Determine color based on value or hint
        if 'color' in hints:
            color = QColor(hints['color'])
        elif value > 0:
            color = QColor(100, 255, 100)
        elif value < 0:
            color = QColor(255, 100, 100)
        else:
            color = QColor(200, 200, 200)
        
        # Main value
        painter.setPen(color)
        font = QFont("Arial", 48, QFont.Weight.Bold)
        painter.setFont(font)
        
        value_text = f"{currency}{abs(value):,.2f}"
        if value < 0:
            value_text = f"-{value_text}"
        
        painter.drawText(QRect(0, height // 2 - 60, width, 80),
                        Qt.AlignmentFlag.AlignCenter, value_text)
        
        # Label
        painter.setPen(QColor(180, 180, 180))
        font = QFont("Arial", 16)
        painter.setFont(font)
        painter.drawText(QRect(0, height // 2 + 30, width, 40),
                        Qt.AlignmentFlag.AlignCenter, label)
    
    def _render_chart(self, painter: QPainter, width: int, height: int,
                     data: Dict[str, Any], hints: Dict[str, Any]):
        """Render chart/graph data."""
        data_points = data.get('data_points', data.get('values', []))
        
        if not data_points:
            self._render_text(painter, width, height, {'text': 'No chart data'}, hints)
            return
        
        # Simple line chart
        chart_height = height // 2
        chart_y = height // 2 - chart_height // 2
        margin = 60
        
        # Draw axes
        painter.setPen(QColor(100, 100, 150))
        painter.drawLine(margin, chart_y + chart_height, width - margin, chart_y + chart_height)
        painter.drawLine(margin, chart_y, margin, chart_y + chart_height)
        
        # Plot data
        if len(data_points) > 1:
            max_val = max(data_points)
            min_val = min(data_points)
            range_val = max_val - min_val if max_val != min_val else 1
            
            painter.setPen(QColor(100, 200, 255))
            
            for i in range(len(data_points) - 1):
                x1 = margin + (i / (len(data_points) - 1)) * (width - 2 * margin)
                y1 = chart_y + chart_height - ((data_points[i] - min_val) / range_val) * chart_height
                x2 = margin + ((i + 1) / (len(data_points) - 1)) * (width - 2 * margin)
                y2 = chart_y + chart_height - ((data_points[i + 1] - min_val) / range_val) * chart_height
                
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
    
    def _render_stats(self, painter: QPainter, width: int, height: int,
                     data: Dict[str, Any], hints: Dict[str, Any]):
        """Render statistics/metrics."""
        metrics = data.get('metrics', data.get('statistics', data))
        
        y_pos = 300
        for key, value in list(metrics.items())[:6]:  # Show up to 6 metrics
            # Key
            painter.setPen(QColor(180, 180, 200))
            font = QFont("Arial", 14)
            painter.setFont(font)
            painter.drawText(QRect(100, y_pos, width // 2 - 100, 30),
                           Qt.AlignmentFlag.AlignLeft, str(key).replace('_', ' ').title())
            
            # Value
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Arial", 18, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRect(width // 2, y_pos, width // 2 - 100, 30),
                           Qt.AlignmentFlag.AlignRight, str(value))
            
            y_pos += 50
    
    def _render_list(self, painter: QPainter, width: int, height: int,
                    data: Dict[str, Any], hints: Dict[str, Any]):
        """Render list of items."""
        items = data.get('items', data.get('list', []))
        icon = hints.get('icon', '•')
        
        y_pos = 300
        for item in items[:8]:  # Show up to 8 items
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Arial", 16)
            painter.setFont(font)
            
            item_text = str(item) if not isinstance(item, dict) else item.get('text', str(item))
            painter.drawText(QRect(80, y_pos, width - 160, 30),
                           Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextElideRight,
                           f"{icon} {item_text}")
            
            y_pos += 40
    
    def _render_media(self, painter: QPainter, width: int, height: int,
                     data: Dict[str, Any], hints: Dict[str, Any]):
        """Render media content (books, images, etc.)."""
        title = data.get('title', 'Untitled')
        subtitle = data.get('subtitle', data.get('author', ''))
        icon = hints.get('icon', '📄')
        
        # Icon
        painter.setPen(QColor(255, 200, 100))
        font = QFont("Arial", 72)
        painter.setFont(font)
        painter.drawText(QRect(0, 250, width, 100),
                        Qt.AlignmentFlag.AlignCenter, icon)
        
        # Title
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(40, 400, width - 80, 100),
                        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                        title)
        
        # Subtitle
        if subtitle:
            painter.setPen(QColor(200, 200, 200))
            font = QFont("Arial", 18)
            painter.setFont(font)
            painter.drawText(QRect(40, 520, width - 80, 60),
                           Qt.AlignmentFlag.AlignCenter, subtitle)
    
    def _render_code(self, painter: QPainter, width: int, height: int,
                    data: Dict[str, Any], hints: Dict[str, Any]):
        """Render code/text content."""
        code = data.get('code', data.get('source', data.get('text', '')))
        
        # Code background
        painter.fillRect(60, 300, width - 120, 600, QColor(20, 20, 30, 200))
        
        # Code text
        painter.setPen(QColor(100, 255, 150))
        font = QFont("Courier New", 12)
        painter.setFont(font)
        
        lines = str(code).split('\n')[:15]  # Show first 15 lines
        y_pos = 320
        for line in lines:
            painter.drawText(QRect(80, y_pos, width - 160, 20),
                           Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextElideRight,
                           line)
            y_pos += 25
    
    def _render_status(self, painter: QPainter, width: int, height: int,
                      data: Dict[str, Any], hints: Dict[str, Any]):
        """Render status/state information."""
        status = data.get('status', data.get('state', 'Unknown'))
        icon = hints.get('icon', '●')
        
        # Status color
        status_lower = str(status).lower()
        if any(word in status_lower for word in ['active', 'online', 'ready', 'success']):
            color = QColor(100, 255, 100)
        elif any(word in status_lower for word in ['error', 'failed', 'offline', 'down']):
            color = QColor(255, 100, 100)
        elif any(word in status_lower for word in ['warning', 'pending', 'loading']):
            color = QColor(255, 200, 100)
        else:
            color = QColor(100, 200, 255)
        
        # Icon
        painter.setPen(color)
        font = QFont("Arial", 64)
        painter.setFont(font)
        painter.drawText(QRect(0, 300, width, 100),
                        Qt.AlignmentFlag.AlignCenter, icon)
        
        # Status text
        font = QFont("Arial", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, 450, width, 60),
                        Qt.AlignmentFlag.AlignCenter, str(status).upper())
    
    def _render_network(self, painter: QPainter, width: int, height: int,
                       data: Dict[str, Any], hints: Dict[str, Any]):
        """Render network/graph visualization."""
        nodes = data.get('nodes', [])
        
        # Simple node visualization
        import random
        random.seed(42)
        
        painter.setPen(QColor(100, 150, 255))
        for i in range(min(len(nodes), 10)):
            x = random.randint(100, width - 100)
            y = random.randint(300, height - 300)
            painter.drawEllipse(x - 20, y - 20, 40, 40)
            
            # Node label
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Arial", 10)
            painter.setFont(font)
            node_text = str(nodes[i]) if i < len(nodes) else f"Node {i+1}"
            painter.drawText(QRect(x - 40, y + 25, 80, 20),
                           Qt.AlignmentFlag.AlignCenter, node_text[:10])
            painter.setPen(QColor(100, 150, 255))
    
    def _render_gauge(self, painter: QPainter, width: int, height: int,
                     data: Dict[str, Any], hints: Dict[str, Any]):
        """Render gauge/progress indicator."""
        value = data.get('progress', data.get('percentage', data.get('value', 0)))
        max_value = data.get('max', 100)
        percentage = (value / max_value) * 100 if max_value > 0 else 0
        
        # Progress bar
        bar_width = width - 200
        bar_height = 40
        bar_x = 100
        bar_y = height // 2 - 20
        
        # Background
        painter.fillRect(bar_x, bar_y, bar_width, bar_height, QColor(40, 40, 60))
        
        # Progress
        progress_width = int((percentage / 100) * bar_width)
        gradient = QLinearGradient(bar_x, 0, bar_x + progress_width, 0)
        gradient.setColorAt(0, QColor(100, 200, 255))
        gradient.setColorAt(1, QColor(100, 255, 200))
        painter.fillRect(bar_x, bar_y, progress_width, bar_height, gradient)
        
        # Percentage text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, bar_y - 80, width, 60),
                        Qt.AlignmentFlag.AlignCenter, f"{percentage:.1f}%")
    
    def _render_timeline(self, painter: QPainter, width: int, height: int,
                        data: Dict[str, Any], hints: Dict[str, Any]):
        """Render timeline of events."""
        events = data.get('events', data.get('timeline', data.get('history', [])))
        
        # Timeline line
        painter.setPen(QColor(100, 150, 255))
        painter.drawLine(100, 300, 100, height - 300)
        
        # Events
        y_pos = 320
        for event in events[:6]:  # Show up to 6 events
            # Event dot
            painter.setBrush(QColor(100, 200, 255))
            painter.drawEllipse(90, y_pos - 5, 20, 20)
            
            # Event text
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Arial", 14)
            painter.setFont(font)
            event_text = str(event) if not isinstance(event, dict) else event.get('text', str(event))
            painter.drawText(QRect(130, y_pos - 10, width - 180, 30),
                           Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextElideRight,
                           event_text)
            
            y_pos += 100
            painter.setPen(QColor(100, 150, 255))
    
    def _render_grid(self, painter: QPainter, width: int, height: int,
                    data: Dict[str, Any], hints: Dict[str, Any]):
        """Render grid/matrix layout."""
        grid_data = data.get('grid', data.get('matrix', []))
        
        if not grid_data:
            self._render_text(painter, width, height, {'text': 'No grid data'}, hints)
            return
        
        # Simple grid visualization
        rows = len(grid_data)
        cols = len(grid_data[0]) if rows > 0 and isinstance(grid_data[0], list) else 1
        
        cell_width = (width - 200) // max(cols, 1)
        cell_height = 60
        
        y_pos = 300
        for row in grid_data[:8]:  # Show up to 8 rows
            x_pos = 100
            for cell in (row if isinstance(row, list) else [row])[:6]:  # Up to 6 cols
                painter.setPen(QColor(100, 100, 150))
                painter.drawRect(x_pos, y_pos, cell_width, cell_height)
                
                painter.setPen(QColor(255, 255, 255))
                font = QFont("Arial", 12)
                painter.setFont(font)
                painter.drawText(QRect(x_pos + 5, y_pos + 5, cell_width - 10, cell_height - 10),
                               Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextElideRight,
                               str(cell))
                
                x_pos += cell_width
            y_pos += cell_height
    
    def _render_text(self, painter: QPainter, width: int, height: int,
                    data: Dict[str, Any], hints: Dict[str, Any]):
        """Render plain text content."""
        text = data.get('text', data.get('message', str(data)))
        
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 20)
        painter.setFont(font)
        painter.drawText(QRect(60, height // 2 - 100, width - 120, 200),
                        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                        str(text))
    
    def _render_generic(self, painter: QPainter, width: int, height: int,
                       data: Dict[str, Any], hints: Dict[str, Any]):
        """Generic fallback renderer for any data."""
        # Try to extract key information
        title = hints.get('title', 'Data')
        icon = hints.get('icon', '📊')
        
        # Icon
        painter.setPen(QColor(100, 200, 255))
        font = QFont("Arial", 64)
        painter.setFont(font)
        painter.drawText(QRect(0, 250, width, 100),
                        Qt.AlignmentFlag.AlignCenter, icon)
        
        # Title
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(40, 400, width - 80, 60),
                        Qt.AlignmentFlag.AlignCenter, title)
        
        # Show key-value pairs
        y_pos = 500
        for key, value in list(data.items())[:5]:  # Show first 5 items
            painter.setPen(QColor(180, 180, 200))
            font = QFont("Arial", 14)
            painter.setFont(font)
            painter.drawText(QRect(100, y_pos, width - 200, 30),
                           Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextElideRight,
                           f"{key}: {value}")
            y_pos += 35

# Global singleton instance
_dynamic_renderer_instance = None

def get_dynamic_renderer() -> DynamicRenderer:
    """Get or create the global dynamic renderer instance."""
    global _dynamic_renderer_instance
    if _dynamic_renderer_instance is None:
        _dynamic_renderer_instance = DynamicRenderer()
    return _dynamic_renderer_instance
