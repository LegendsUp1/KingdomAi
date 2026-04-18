"""
Technical Visualization Engine - SOTA 2026 Advanced Drawing & Design

Provides: Mathematical, Cartography, Astrology, Calligraphy, Geometry visualization.
"""

import math
import logging
import colorsys
import random
from typing import Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QImage, QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QFontMetrics
)

logger = logging.getLogger("KingdomAI.TechnicalVisualization")


class TechnicalMode(Enum):
    MATHEMATICS = "mathematics"
    TRIGONOMETRY = "trigonometry"
    CALCULUS = "calculus"
    FUNCTION_PLOT = "function_plot"
    GEOMETRY = "geometry"
    CARTOGRAPHY = "cartography"
    ASTROLOGY = "astrology"
    CALLIGRAPHY = "calligraphy"
    SACRED_GEOMETRY = "sacred_geometry"
    FRACTAL = "fractal"


@dataclass
class TechnicalConfig:
    mode: TechnicalMode = TechnicalMode.MATHEMATICS
    width: int = 512
    height: int = 512
    animate: bool = False
    detail_level: int = 3
    show_grid: bool = True
    show_labels: bool = True
    show_axes: bool = True
    color_scheme: str = "default"


COLOR_SCHEMES = {
    'default': {
        'background': QColor(15, 15, 26), 'grid': QColor(40, 40, 80),
        'axes': QColor(100, 100, 180), 'primary': QColor(100, 200, 255),
        'secondary': QColor(255, 100, 150), 'tertiary': QColor(100, 255, 150),
        'text': QColor(200, 200, 240), 'highlight': QColor(255, 215, 0)
    },
    'blueprint': {
        'background': QColor(0, 31, 63), 'grid': QColor(0, 50, 100),
        'axes': QColor(100, 150, 200), 'primary': QColor(200, 220, 255),
        'secondary': QColor(255, 200, 100), 'text': QColor(220, 230, 255)
    },
    'neon': {
        'background': QColor(10, 10, 20), 'grid': QColor(30, 30, 60),
        'axes': QColor(0, 255, 255), 'primary': QColor(255, 0, 255),
        'secondary': QColor(0, 255, 0), 'text': QColor(255, 255, 255)
    }
}


class TechnicalVisualizationEngine:
    """SOTA 2026 Technical Visualization Engine - unified interface."""
    
    MATH_ENV = {
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
        'sinh': math.sinh, 'cosh': math.cosh, 'tanh': math.tanh,
        'exp': math.exp, 'log': math.log, 'log10': math.log10,
        'sqrt': math.sqrt, 'abs': abs, 'pow': pow,
        'pi': math.pi, 'e': math.e
    }
    
    ZODIAC = [("♈","Aries"),("♉","Taurus"),("♊","Gemini"),("♋","Cancer"),
              ("♌","Leo"),("♍","Virgo"),("♎","Libra"),("♏","Scorpio"),
              ("♐","Sagittarius"),("♑","Capricorn"),("♒","Aquarius"),("♓","Pisces")]
    
    PLANETS = [("☉","Sun"),("☽","Moon"),("☿","Mercury"),("♀","Venus"),
               ("♂","Mars"),("♃","Jupiter"),("♄","Saturn")]
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.colors = COLOR_SCHEMES['default']
        
        # FIX (2026-02-03): Subscribe to event bus for technical visualization requests
        if self.event_bus:
            try:
                self.event_bus.subscribe("technical.render", self._handle_render_request)
                self.event_bus.subscribe("visual.technical.request", self._handle_visual_technical_request)
                logger.info("✅ TechnicalVisualizationEngine subscribed to event bus")
            except Exception as e:
                logger.warning(f"⚠️ Failed to subscribe to events: {e}")
    
    def set_color_scheme(self, scheme: str):
        if scheme in COLOR_SCHEMES:
            self.colors = COLOR_SCHEMES[scheme]
    
    def render(self, prompt: str, config: TechnicalConfig) -> QImage:
        """Main render method - routes to appropriate visualizer."""
        image = QImage(config.width, config.height, QImage.Format.Format_RGB32)
        
        mode = config.mode
        if mode == TechnicalMode.FUNCTION_PLOT:
            return self.render_function(image, prompt, config)
        elif mode == TechnicalMode.TRIGONOMETRY:
            return self.render_trigonometry(image, config)
        elif mode == TechnicalMode.CALCULUS:
            return self.render_calculus(image, prompt, config)
        elif mode == TechnicalMode.CARTOGRAPHY:
            return self.render_map(image, config)
        elif mode == TechnicalMode.ASTROLOGY:
            return self.render_astrology(image, config)
        elif mode == TechnicalMode.CALLIGRAPHY:
            return self.render_calligraphy(image, prompt, config)
        elif mode == TechnicalMode.SACRED_GEOMETRY:
            return self.render_sacred_geometry(image, config)
        elif mode == TechnicalMode.FRACTAL:
            return self.render_fractal(image, config)
        else:
            return self.render_function(image, "sin(x)", config)
    
    def render_function(self, image: QImage, func_str: str, config: TechnicalConfig,
                       x_range: Tuple[float,float] = (-10, 10)) -> QImage:
        """Render mathematical function plot."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = config.width, config.height
        y_range = (-10, 10)
        
        painter.fillRect(0, 0, w, h, self.colors['background'])
        
        x_scale = w / (x_range[1] - x_range[0])
        y_scale = h / (y_range[1] - y_range[0])
        
        if config.show_grid:
            self._draw_grid(painter, w, h, x_range, y_range, x_scale, y_scale)
        if config.show_axes:
            self._draw_axes(painter, w, h, x_range, y_range, x_scale, y_scale)
        
        # Plot function
        pen = QPen(self.colors['primary'], 2)
        painter.setPen(pen)
        path = QPainterPath()
        first = True
        env = dict(self.MATH_ENV)
        
        for i in range(w * config.detail_level):
            x = x_range[0] + (i / (w * config.detail_level)) * (x_range[1] - x_range[0])
            env['x'] = x
            try:
                y = eval(func_str, {"__builtins__": {}}, env)
                if y_range[0] <= y <= y_range[1]:
                    sx = (x - x_range[0]) * x_scale
                    sy = h - (y - y_range[0]) * y_scale
                    if first: path.moveTo(sx, sy); first = False
                    else: path.lineTo(sx, sy)
                else: first = True
            except: first = True
        
        painter.drawPath(path)
        
        if config.show_labels:
            painter.setPen(self.colors['text'])
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(10, 25, f"f(x) = {func_str}")
        
        painter.end()
        return image
    
    def render_trigonometry(self, image: QImage, config: TechnicalConfig, angle: float = 45) -> QImage:
        """Render unit circle with trig functions."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = config.width, config.height
        cx, cy = w // 2, h // 2
        r = min(w, h) // 3
        
        painter.fillRect(0, 0, w, h, self.colors['background'])
        
        if config.show_grid:
            pen = QPen(self.colors['grid'], 1)
            painter.setPen(pen)
            for i in range(0, w, 30): painter.drawLine(i, 0, i, h)
            for i in range(0, h, 30): painter.drawLine(0, i, w, i)
        
        if config.show_axes:
            pen = QPen(self.colors['axes'], 2)
            painter.setPen(pen)
            painter.drawLine(0, cy, w, cy)
            painter.drawLine(cx, 0, cx, h)
        
        # Unit circle
        painter.setPen(QPen(self.colors['text'], 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        
        # Trig values
        rad = math.radians(angle)
        cos_v, sin_v = math.cos(rad), math.sin(rad)
        px, py = cx + r * cos_v, cy - r * sin_v
        
        # Radius
        painter.setPen(QPen(self.colors['highlight'], 3))
        painter.drawLine(cx, cy, int(px), int(py))
        
        # Cos (x)
        painter.setPen(QPen(self.colors['primary'], 3))
        painter.drawLine(cx, cy, int(px), cy)
        
        # Sin (y)
        painter.setPen(QPen(self.colors['secondary'], 3))
        painter.drawLine(int(px), cy, int(px), int(py))
        
        # Point
        painter.setBrush(self.colors['highlight'])
        painter.drawEllipse(int(px) - 5, int(py) - 5, 10, 10)
        
        if config.show_labels:
            painter.setPen(self.colors['text'])
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(cx + 50, cy - 10, f"θ = {angle}°")
            painter.setPen(self.colors['primary'])
            painter.drawText(10, 25, f"cos(θ) = {cos_v:.4f}")
            painter.setPen(self.colors['secondary'])
            painter.drawText(10, 45, f"sin(θ) = {sin_v:.4f}")
        
        painter.end()
        return image
    
    def render_calculus(self, image: QImage, func_str: str, config: TechnicalConfig) -> QImage:
        """Render function with derivative and integral visualization."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = config.width, config.height
        x_range, y_range = (-5, 5), (-10, 10)
        
        painter.fillRect(0, 0, w, h, self.colors['background'])
        x_scale = w / (x_range[1] - x_range[0])
        y_scale = h / (y_range[1] - y_range[0])
        
        if config.show_grid: self._draw_grid(painter, w, h, x_range, y_range, x_scale, y_scale)
        if config.show_axes: self._draw_axes(painter, w, h, x_range, y_range, x_scale, y_scale)
        
        env = dict(self.MATH_ENV)
        def f(x): env['x'] = x; return eval(func_str, {"__builtins__": {}}, env)
        def df(x, h=0.001): return (f(x+h) - f(x-h)) / (2*h)
        
        # Draw integral area
        y_axis = h - (0 - y_range[0]) * y_scale
        integral_path = QPainterPath()
        first = True
        for i in range(w * 2):
            x = x_range[0] + (i / (w * 2)) * (x_range[1] - x_range[0])
            try:
                y = f(x)
                if y_range[0] <= y <= y_range[1]:
                    sx = (x - x_range[0]) * x_scale
                    sy = h - (y - y_range[0]) * y_scale
                    if first: integral_path.moveTo(sx, y_axis); integral_path.lineTo(sx, sy); first = False
                    else: integral_path.lineTo(sx, sy)
            except Exception as e: logger.debug(f"Visualization render error: {e}")
        if not first:
            integral_path.lineTo(w, y_axis)
            integral_path.closeSubpath()
            c = QColor(self.colors['tertiary']); c.setAlpha(50)
            painter.fillPath(integral_path, c)
        
        # Draw function
        painter.setPen(QPen(self.colors['primary'], 3))
        path = QPainterPath(); first = True
        for i in range(w * config.detail_level):
            x = x_range[0] + (i / (w * config.detail_level)) * (x_range[1] - x_range[0])
            try:
                y = f(x)
                if y_range[0] <= y <= y_range[1]:
                    sx = (x - x_range[0]) * x_scale
                    sy = h - (y - y_range[0]) * y_scale
                    if first: path.moveTo(sx, sy); first = False
                    else: path.lineTo(sx, sy)
                else: first = True
            except: first = True
        painter.drawPath(path)
        
        # Draw derivative
        painter.setPen(QPen(self.colors['secondary'], 2, Qt.PenStyle.DashLine))
        path = QPainterPath(); first = True
        for i in range(w * config.detail_level):
            x = x_range[0] + (i / (w * config.detail_level)) * (x_range[1] - x_range[0])
            try:
                y = df(x)
                if y_range[0] <= y <= y_range[1]:
                    sx = (x - x_range[0]) * x_scale
                    sy = h - (y - y_range[0]) * y_scale
                    if first: path.moveTo(sx, sy); first = False
                    else: path.lineTo(sx, sy)
                else: first = True
            except: first = True
        painter.drawPath(path)
        
        if config.show_labels:
            painter.setFont(QFont("Segoe UI", 11))
            painter.setPen(self.colors['primary']); painter.drawText(10, 25, f"f(x) = {func_str}")
            painter.setPen(self.colors['secondary']); painter.drawText(10, 45, "f'(x) = derivative")
            painter.setPen(self.colors['tertiary']); painter.drawText(10, 65, "∫f(x)dx = area")
        
        painter.end()
        return image
    
    def render_map(self, image: QImage, config: TechnicalConfig) -> QImage:
        """Render procedural terrain map."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = config.width, config.height
        
        colors = [QColor(30,80,160), QColor(210,190,130), QColor(80,140,60),
                  QColor(40,100,40), QColor(100,90,80), QColor(240,240,255)]
        
        scale = config.detail_level * 20
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                n = 0; amp = 1; freq = 1
                for _ in range(4):
                    nx, ny = x * freq / scale, y * freq / scale
                    n += amp * (math.sin(nx * 12.9898 + ny * 78.233) * 0.5 + 0.5)
                    amp *= 0.5; freq *= 2
                n /= 2
                idx = min(5, int(n * 6))
                painter.fillRect(x, y, 2, 2, colors[idx])
        
        # Compass
        cx, cy, r = w - 50, h - 50, 25
        painter.setPen(QPen(QColor(255,255,255), 2))
        painter.setBrush(QColor(200,200,200,100))
        painter.drawEllipse(cx-r, cy-r, r*2, r*2)
        painter.setPen(QColor(255,255,255))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(cx - 4, cy - r - 5, "N")
        
        if config.show_labels:
            painter.setPen(QColor(255,255,255))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(10, h - 20, "Procedural Terrain Map")
        
        painter.end()
        return image
    
    def render_astrology(self, image: QImage, config: TechnicalConfig) -> QImage:
        """Render astrological birth chart."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = config.width, config.height
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 20
        
        # Background
        grad = QRadialGradient(cx, cy, r * 1.5)
        grad.setColorAt(0, QColor(20,15,40))
        grad.setColorAt(1, QColor(5,5,15))
        painter.fillRect(0, 0, w, h, grad)
        
        # Outer circle
        painter.setPen(QPen(QColor(100,80,150), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(cx-r, cy-r, r*2, r*2)
        ir = int(r * 0.85)
        painter.drawEllipse(cx-ir, cy-ir, ir*2, ir*2)
        
        # Zodiac signs
        zodiac_colors = [QColor(255,80,80), QColor(80,180,80), QColor(255,255,100),
                        QColor(200,200,255), QColor(255,180,0), QColor(100,150,100),
                        QColor(255,150,200), QColor(150,0,50), QColor(150,100,255),
                        QColor(100,100,100), QColor(0,200,255), QColor(100,150,200)]
        
        for i, ((sym, _), col) in enumerate(zip(self.ZODIAC, zodiac_colors)):
            ang = i * 30 - 90
            rad = math.radians(ang)
            x1, y1 = cx + ir * math.cos(rad), cy + ir * math.sin(rad)
            x2, y2 = cx + r * math.cos(rad), cy + r * math.sin(rad)
            painter.setPen(QPen(QColor(100,80,150), 1))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            
            srad = math.radians(ang + 15)
            sr = (r + ir) / 2
            sx, sy = cx + sr * math.cos(srad), cy + sr * math.sin(srad)
            painter.setPen(col)
            painter.setFont(QFont("Segoe UI Symbol", 14))
            painter.drawText(int(sx) - 8, int(sy) + 6, sym)
        
        # Planets
        planet_colors = {"Sun": QColor(255,200,0), "Moon": QColor(200,200,220),
                        "Mercury": QColor(180,180,180), "Venus": QColor(255,150,200),
                        "Mars": QColor(255,80,80), "Jupiter": QColor(255,180,100),
                        "Saturn": QColor(180,160,100)}
        
        pr = r * 0.5
        for i, (sym, name) in enumerate(self.PLANETS):
            pos = (i * 51 + 10) % 360
            prad = math.radians(pos - 90)
            px, py = cx + pr * math.cos(prad), cy + pr * math.sin(prad)
            col = planet_colors.get(name, QColor(200,200,200))
            painter.setPen(col); painter.setBrush(col)
            painter.drawEllipse(int(px)-6, int(py)-6, 12, 12)
            painter.setPen(QColor(30,30,50))
            painter.setFont(QFont("Segoe UI Symbol", 10))
            painter.drawText(int(px)-5, int(py)+4, sym)
        
        if config.show_labels:
            painter.setPen(QColor(200,180,255))
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.drawText(10, 25, "Natal Birth Chart")
        
        painter.end()
        return image
    
    def render_calligraphy(self, image: QImage, text: str, config: TechnicalConfig) -> QImage:
        """Render artistic calligraphy text."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = config.width, config.height
        
        # Dark background
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(20,20,35))
        grad.setColorAt(1, QColor(30,25,45))
        painter.fillRect(0, 0, w, h, grad)
        
        # Text
        font = QFont("Segoe UI", 48, QFont.Weight.Bold)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        tw = metrics.horizontalAdvance(text)
        x, y = (w - tw) // 2, h // 2
        
        # Shadow
        painter.setPen(QColor(50,50,80))
        painter.drawText(x + 3, y + 3, text)
        
        # Main text with gradient effect
        painter.setPen(QColor(200,220,255))
        painter.drawText(x, y, text)
        
        # Decorative line
        painter.setPen(QPen(QColor(100,150,200), 2))
        painter.drawLine(x, y + 20, x + tw, y + 20)
        
        if config.show_labels:
            painter.setPen(QColor(150,150,180))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(10, h - 20, "Modern Typography")
        
        painter.end()
        return image
    
    def render_sacred_geometry(self, image: QImage, config: TechnicalConfig) -> QImage:
        """Render sacred geometry - Flower of Life."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = config.width, config.height
        cx, cy = w // 2, h // 2
        
        grad = QRadialGradient(cx, cy, max(w, h) // 2)
        grad.setColorAt(0, QColor(30,25,50))
        grad.setColorAt(1, QColor(10,10,20))
        painter.fillRect(0, 0, w, h, grad)
        
        r = min(w, h) // 6
        painter.setPen(QPen(QColor(100,150,255), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Center
        painter.drawEllipse(cx-r, cy-r, r*2, r*2)
        
        # First ring (6 circles)
        for i in range(6):
            rad = math.radians(i * 60)
            x, y = cx + r * math.cos(rad), cy + r * math.sin(rad)
            painter.drawEllipse(int(x)-r, int(y)-r, r*2, r*2)
        
        # Second ring (12 circles)
        for i in range(12):
            rad = math.radians(i * 30)
            dist = r * math.sqrt(3) if i % 2 == 0 else r * 2
            x, y = cx + dist * math.cos(rad), cy + dist * math.sin(rad)
            painter.drawEllipse(int(x)-r, int(y)-r, r*2, r*2)
        
        if config.show_labels:
            painter.setPen(QColor(200,180,220))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(10, 25, "Sacred Geometry: Flower of Life")
        
        painter.end()
        return image
    
    def render_fractal(self, image: QImage, config: TechnicalConfig) -> QImage:
        """Render Mandelbrot fractal visualization."""
        painter = QPainter(image)
        w, h = config.width, config.height
        
        x_min, x_max = -2.5, 1.0
        y_min, y_max = -1.5, 1.5
        max_iter = 50 * config.detail_level
        
        for py in range(h):
            for px in range(w):
                x0 = x_min + (px / w) * (x_max - x_min)
                y0 = y_min + (py / h) * (y_max - y_min)
                x, y, i = 0, 0, 0
                while x*x + y*y <= 4 and i < max_iter:
                    x, y = x*x - y*y + x0, 2*x*y + y0
                    i += 1
                
                if i < max_iter:
                    hue = i / max_iter
                    r, g, b = colorsys.hsv_to_rgb(hue * 0.7, 0.9, 0.9)
                    color = QColor(int(r*255), int(g*255), int(b*255))
                else:
                    color = QColor(0, 0, 0)
                painter.setPen(color)
                painter.drawPoint(px, py)
        
        if config.show_labels:
            painter.setPen(QColor(255,255,255))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(10, 25, "Mandelbrot Fractal")
        
        painter.end()
        return image
    
    def _draw_grid(self, p: QPainter, w: int, h: int, xr, yr, xs, ys):
        p.setPen(QPen(self.colors['grid'], 1))
        step = 1 if xr[1] - xr[0] <= 20 else 2
        for x in range(int(xr[0]), int(xr[1]) + 1, step):
            sx = (x - xr[0]) * xs
            p.drawLine(int(sx), 0, int(sx), h)
        for y in range(int(yr[0]), int(yr[1]) + 1, step):
            sy = h - (y - yr[0]) * ys
            p.drawLine(0, int(sy), w, int(sy))
    
    def _draw_axes(self, p: QPainter, w: int, h: int, xr, yr, xs, ys):
        p.setPen(QPen(self.colors['axes'], 2))
        if yr[0] <= 0 <= yr[1]:
            sy = h - (0 - yr[0]) * ys
            p.drawLine(0, int(sy), w, int(sy))
        if xr[0] <= 0 <= xr[1]:
            sx = (0 - xr[0]) * xs
            p.drawLine(int(sx), 0, int(sx), h)
    
    def _handle_render_request(self, data: Dict) -> None:
        """Handle technical.render event requests."""
        try:
            if not isinstance(data, dict):
                return
            
            prompt = data.get("prompt", "")
            mode_str = data.get("mode", "mathematics")
            width = data.get("width", 512)
            height = data.get("height", 512)
            
            # Parse mode
            try:
                mode = TechnicalMode(mode_str)
            except ValueError:
                mode = TechnicalMode.MATHEMATICS
            
            config = TechnicalConfig(
                mode=mode,
                width=width,
                height=height,
                detail_level=data.get("detail_level", 3),
                show_grid=data.get("show_grid", True),
                show_labels=data.get("show_labels", True),
                show_axes=data.get("show_axes", True),
                color_scheme=data.get("color_scheme", "default")
            )
            
            # Render
            image = self.render(prompt, config)
            
            # Save to temporary file
            import tempfile
            import os
            output_path = data.get("output_path")
            if not output_path:
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, f"technical_{mode_str}_{hash(prompt) % 10000}.png")
            
            image.save(output_path)
            
            # Publish result
            if self.event_bus:
                self.event_bus.publish("technical.rendered", {
                    "image_path": output_path,
                    "mode": mode_str,
                    "prompt": prompt,
                    "request_id": data.get("request_id", "")
                })
        except Exception as e:
            logger.error(f"❌ technical.render handler error: {e}", exc_info=True)
            if self.event_bus:
                self.event_bus.publish("technical.render.error", {
                    "error": str(e),
                    "request_id": data.get("request_id", "")
                })
    
    def _handle_visual_technical_request(self, data: Dict) -> None:
        """Handle visual.technical.request events - unified visual request interface."""
        try:
            if not isinstance(data, dict):
                return
            
            # Route to render handler
            self._handle_render_request(data)
            
            # Also publish as visual.generated for consistency
            output_path = data.get("output_path")
            if output_path and self.event_bus:
                self.event_bus.publish("visual.generated", {
                    "image_path": output_path,
                    "request_id": data.get("request_id", ""),
                    "backend": "technical_visualization",
                    "prompt": data.get("prompt", ""),
                    "mode": data.get("mode", "mathematics")
                })
        except Exception as e:
            logger.error(f"❌ visual.technical.request handler error: {e}", exc_info=True)
            if self.event_bus:
                self.event_bus.publish("visual.generation.error", {
                    "request_id": data.get("request_id", ""),
                    "error": str(e)
                })


# Export
__all__ = ['TechnicalVisualizationEngine', 'TechnicalMode', 'TechnicalConfig']
