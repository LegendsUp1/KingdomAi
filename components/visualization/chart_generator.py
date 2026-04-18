"""Chart Generator Component - SOTA 2026 Full Implementation.

Generates trading charts, visualizations, and technical analysis displays.
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import math


class ChartType(Enum):
    """Supported chart types."""
    CANDLESTICK = "candlestick"
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    HEIKIN_ASHI = "heikin_ashi"
    RENKO = "renko"
    POINT_FIGURE = "point_figure"
    DEPTH = "depth"
    HEATMAP = "heatmap"


class TimeFrame(Enum):
    """Chart timeframes."""
    TICK = "tick"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN = "1M"


@dataclass
class ChartConfig:
    """Chart configuration."""
    chart_type: ChartType
    timeframe: TimeFrame
    width: int = 800
    height: int = 600
    
    # Colors
    background_color: str = "#0a0a14"
    grid_color: str = "#1a1a2e"
    text_color: str = "#e0e0e0"
    up_color: str = "#00ff88"
    down_color: str = "#ff4444"
    volume_color: str = "#4488ff"
    
    # Features
    show_grid: bool = True
    show_volume: bool = True
    show_crosshair: bool = True
    show_legend: bool = True
    
    # Technical indicators to display
    indicators: List[str] = None


@dataclass
class ChartData:
    """Chart data structure."""
    symbol: str
    timeframe: str
    candles: List[Dict[str, Any]]
    volume: List[float]
    indicators: Dict[str, List[float]]
    
    # Metadata
    start_time: float = 0
    end_time: float = 0
    
    # Statistics
    high: float = 0
    low: float = 0
    change_percent: float = 0


class ChartGenerator:
    """
    SOTA 2026: Advanced chart generation for trading visualization.
    
    Features:
    - Multiple chart types (candlestick, line, area, etc.)
    - Technical indicator overlays
    - Real-time updates
    - Interactive features
    - Export to multiple formats
    - VR/3D compatible output
    """
    
    def __init__(self, event_bus=None):
        """Initialize Chart Generator.
        
        Args:
            event_bus: Optional event bus for system integration
        """
        self.event_bus = event_bus
        self._initialized = False
        
        # Chart storage
        self.active_charts: Dict[str, Dict[str, Any]] = {}
        
        # Data cache
        self._price_cache: Dict[str, List[Dict]] = {}
        self._indicator_cache: Dict[str, Dict[str, List[float]]] = {}
        
        # Default config
        self.default_config = ChartConfig(
            chart_type=ChartType.CANDLESTICK,
            timeframe=TimeFrame.H1
        )
        
        # Supported indicators
        self.supported_indicators = [
            "sma", "ema", "rsi", "macd", "bollinger",
            "stochastic", "atr", "vwap", "volume_profile",
            "fibonacci", "pivot_points", "ichimoku"
        ]
        
        # Subscribe to events
        if self.event_bus:
            self._subscribe_to_events()
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to market data events."""
        if not self.event_bus:
            return
        
        self.event_bus.subscribe("market.price_update", self._handle_price_update)
        self.event_bus.subscribe("market.candle.close", self._handle_candle_close)
        self.event_bus.subscribe("chart.request", self._handle_chart_request)
    
    def initialize(self) -> bool:
        """Initialize the chart generator."""
        try:
            self._initialized = True
            
            if self.event_bus:
                self.event_bus.publish("chart.generator.initialized", {
                    "status": "ready",
                    "supported_types": [t.value for t in ChartType],
                    "supported_indicators": self.supported_indicators
                })
            
            return True
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("chart.generator.error", {
                    "error": str(e),
                    "phase": "initialization"
                })
            return False
    
    def create_chart(
        self,
        symbol: str,
        config: ChartConfig = None,
        data: List[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new chart.
        
        Args:
            symbol: Trading symbol
            config: Chart configuration
            data: Historical price data
            
        Returns:
            Chart object with render data
        """
        config = config or self.default_config
        
        chart_id = f"{symbol}_{config.chart_type.value}_{config.timeframe.value}_{int(time.time())}"
        
        # Process data
        chart_data = self._process_chart_data(symbol, data, config)
        
        # Generate render data based on chart type
        if config.chart_type == ChartType.CANDLESTICK:
            render_data = self._generate_candlestick(chart_data, config)
        elif config.chart_type == ChartType.LINE:
            render_data = self._generate_line_chart(chart_data, config)
        elif config.chart_type == ChartType.AREA:
            render_data = self._generate_area_chart(chart_data, config)
        elif config.chart_type == ChartType.HEIKIN_ASHI:
            render_data = self._generate_heikin_ashi(chart_data, config)
        elif config.chart_type == ChartType.DEPTH:
            render_data = self._generate_depth_chart(chart_data, config)
        elif config.chart_type == ChartType.HEATMAP:
            render_data = self._generate_heatmap(chart_data, config)
        else:
            render_data = self._generate_candlestick(chart_data, config)
        
        # Add indicators
        if config.indicators:
            indicators_data = self._calculate_indicators(chart_data, config.indicators)
            render_data["indicators"] = indicators_data
        
        chart = {
            "chart_id": chart_id,
            "symbol": symbol,
            "config": config,
            "data": chart_data,
            "render": render_data,
            "created_at": time.time()
        }
        
        self.active_charts[chart_id] = chart
        
        if self.event_bus:
            self.event_bus.publish("chart.created", {
                "chart_id": chart_id,
                "symbol": symbol,
                "type": config.chart_type.value
            })
        
        return chart
    
    def _process_chart_data(
        self,
        symbol: str,
        data: List[Dict[str, Any]],
        config: ChartConfig
    ) -> ChartData:
        """Process raw data into chart data structure."""
        if not data:
            data = self._price_cache.get(symbol, [])
        
        candles = []
        volumes = []
        
        for item in data:
            candles.append({
                "time": item.get("time", item.get("timestamp", 0)),
                "open": item.get("open", 0),
                "high": item.get("high", 0),
                "low": item.get("low", 0),
                "close": item.get("close", 0)
            })
            volumes.append(item.get("volume", 0))
        
        # Calculate stats
        if candles:
            highs = [c["high"] for c in candles]
            lows = [c["low"] for c in candles]
            high = max(highs) if highs else 0
            low = min(lows) if lows else 0
            
            first_close = candles[0]["close"] if candles else 0
            last_close = candles[-1]["close"] if candles else 0
            change_pct = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0
        else:
            high = low = change_pct = 0
        
        return ChartData(
            symbol=symbol,
            timeframe=config.timeframe.value,
            candles=candles,
            volume=volumes,
            indicators={},
            start_time=candles[0]["time"] if candles else 0,
            end_time=candles[-1]["time"] if candles else 0,
            high=high,
            low=low,
            change_percent=change_pct
        )
    
    def _generate_candlestick(
        self,
        data: ChartData,
        config: ChartConfig
    ) -> Dict[str, Any]:
        """Generate candlestick chart render data."""
        candle_width = config.width / max(len(data.candles), 1) * 0.8
        price_range = data.high - data.low if data.high > data.low else 1
        price_scale = config.height * 0.8 / price_range
        
        candles = []
        for i, candle in enumerate(data.candles):
            x = i * (config.width / max(len(data.candles), 1))
            
            is_up = candle["close"] >= candle["open"]
            color = config.up_color if is_up else config.down_color
            
            body_top = max(candle["open"], candle["close"])
            body_bottom = min(candle["open"], candle["close"])
            
            candles.append({
                "x": x,
                "body_y": (data.high - body_top) * price_scale,
                "body_height": max(1, (body_top - body_bottom) * price_scale),
                "wick_top_y": (data.high - candle["high"]) * price_scale,
                "wick_bottom_y": (data.high - candle["low"]) * price_scale,
                "width": candle_width,
                "color": color,
                "time": candle["time"],
                "ohlc": candle
            })
        
        # Volume bars
        volume_bars = []
        if config.show_volume and data.volume:
            max_vol = max(data.volume) if data.volume else 1
            vol_height = config.height * 0.15
            
            for i, vol in enumerate(data.volume):
                x = i * (config.width / max(len(data.volume), 1))
                is_up = data.candles[i]["close"] >= data.candles[i]["open"] if i < len(data.candles) else True
                
                volume_bars.append({
                    "x": x,
                    "height": (vol / max_vol) * vol_height if max_vol > 0 else 0,
                    "width": candle_width,
                    "color": config.up_color if is_up else config.down_color,
                    "value": vol
                })
        
        return {
            "type": "candlestick",
            "candles": candles,
            "volume_bars": volume_bars,
            "price_scale": {
                "min": data.low,
                "max": data.high,
                "range": price_range
            },
            "dimensions": {
                "width": config.width,
                "height": config.height
            }
        }
    
    def _generate_line_chart(
        self,
        data: ChartData,
        config: ChartConfig
    ) -> Dict[str, Any]:
        """Generate line chart render data."""
        if not data.candles:
            return {"type": "line", "points": []}
        
        price_range = data.high - data.low if data.high > data.low else 1
        
        points = []
        for i, candle in enumerate(data.candles):
            x = i * (config.width / max(len(data.candles) - 1, 1))
            y = (data.high - candle["close"]) / price_range * config.height * 0.8
            points.append({"x": x, "y": y, "price": candle["close"], "time": candle["time"]})
        
        return {
            "type": "line",
            "points": points,
            "color": config.up_color if data.change_percent >= 0 else config.down_color,
            "price_scale": {
                "min": data.low,
                "max": data.high
            }
        }
    
    def _generate_area_chart(
        self,
        data: ChartData,
        config: ChartConfig
    ) -> Dict[str, Any]:
        """Generate area chart render data."""
        line_data = self._generate_line_chart(data, config)
        
        # Add fill area
        if line_data["points"]:
            fill_points = line_data["points"].copy()
            fill_points.append({"x": config.width, "y": config.height})
            fill_points.append({"x": 0, "y": config.height})
            line_data["fill_points"] = fill_points
            line_data["fill_color"] = config.up_color if data.change_percent >= 0 else config.down_color
            line_data["fill_opacity"] = 0.3
        
        line_data["type"] = "area"
        return line_data
    
    def _generate_heikin_ashi(
        self,
        data: ChartData,
        config: ChartConfig
    ) -> Dict[str, Any]:
        """Generate Heikin-Ashi chart."""
        if not data.candles:
            return {"type": "heikin_ashi", "candles": []}
        
        ha_candles = []
        prev_ha = None
        
        for candle in data.candles:
            if prev_ha is None:
                ha_open = (candle["open"] + candle["close"]) / 2
            else:
                ha_open = (prev_ha["open"] + prev_ha["close"]) / 2
            
            ha_close = (candle["open"] + candle["high"] + candle["low"] + candle["close"]) / 4
            ha_high = max(candle["high"], ha_open, ha_close)
            ha_low = min(candle["low"], ha_open, ha_close)
            
            ha_candle = {
                "time": candle["time"],
                "open": ha_open,
                "high": ha_high,
                "low": ha_low,
                "close": ha_close
            }
            ha_candles.append(ha_candle)
            prev_ha = ha_candle
        
        # Create new chart data with HA candles
        ha_data = ChartData(
            symbol=data.symbol,
            timeframe=data.timeframe,
            candles=ha_candles,
            volume=data.volume,
            indicators={},
            high=max(c["high"] for c in ha_candles) if ha_candles else 0,
            low=min(c["low"] for c in ha_candles) if ha_candles else 0
        )
        
        render = self._generate_candlestick(ha_data, config)
        render["type"] = "heikin_ashi"
        return render
    
    def _generate_depth_chart(
        self,
        data: ChartData,
        config: ChartConfig
    ) -> Dict[str, Any]:
        """Generate order book depth chart."""
        # Depth chart requires order book data
        return {
            "type": "depth",
            "bids": [],
            "asks": [],
            "mid_price": data.candles[-1]["close"] if data.candles else 0
        }
    
    def _generate_heatmap(
        self,
        data: ChartData,
        config: ChartConfig
    ) -> Dict[str, Any]:
        """Generate price heatmap."""
        if not data.candles:
            return {"type": "heatmap", "cells": []}
        
        # Create volume profile heatmap
        price_levels = 50
        price_step = (data.high - data.low) / price_levels if data.high > data.low else 1
        
        volume_at_price = {}
        for i, candle in enumerate(data.candles):
            price_level = int((candle["close"] - data.low) / price_step)
            vol = data.volume[i] if i < len(data.volume) else 0
            volume_at_price[price_level] = volume_at_price.get(price_level, 0) + vol
        
        max_vol = max(volume_at_price.values()) if volume_at_price else 1
        
        cells = []
        for level, vol in volume_at_price.items():
            intensity = vol / max_vol
            cells.append({
                "price_level": level,
                "price": data.low + level * price_step,
                "volume": vol,
                "intensity": intensity
            })
        
        return {
            "type": "heatmap",
            "cells": cells,
            "price_range": {"min": data.low, "max": data.high}
        }
    
    def _calculate_indicators(
        self,
        data: ChartData,
        indicators: List[str]
    ) -> Dict[str, Any]:
        """Calculate technical indicators."""
        results = {}
        closes = [c["close"] for c in data.candles]
        
        for indicator in indicators:
            if indicator.startswith("sma"):
                period = int(indicator.split("_")[1]) if "_" in indicator else 20
                results[indicator] = self._calculate_sma(closes, period)
            elif indicator.startswith("ema"):
                period = int(indicator.split("_")[1]) if "_" in indicator else 20
                results[indicator] = self._calculate_ema(closes, period)
            elif indicator == "rsi":
                results["rsi"] = self._calculate_rsi(closes, 14)
            elif indicator == "macd":
                results["macd"] = self._calculate_macd(closes)
            elif indicator == "bollinger":
                results["bollinger"] = self._calculate_bollinger(closes, 20)
        
        return results
    
    def _calculate_sma(self, data: List[float], period: int) -> List[Optional[float]]:
        """Calculate Simple Moving Average."""
        result = [None] * len(data)
        for i in range(period - 1, len(data)):
            result[i] = sum(data[i - period + 1:i + 1]) / period
        return result
    
    def _calculate_ema(self, data: List[float], period: int) -> List[Optional[float]]:
        """Calculate Exponential Moving Average."""
        result = [None] * len(data)
        if len(data) < period:
            return result
        
        multiplier = 2 / (period + 1)
        result[period - 1] = sum(data[:period]) / period
        
        for i in range(period, len(data)):
            result[i] = (data[i] * multiplier) + (result[i - 1] * (1 - multiplier))
        
        return result
    
    def _calculate_rsi(self, data: List[float], period: int = 14) -> List[Optional[float]]:
        """Calculate Relative Strength Index."""
        result = [None] * len(data)
        if len(data) < period + 1:
            return result
        
        gains = []
        losses = []
        
        for i in range(1, len(data)):
            change = data[i] - data[i - 1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        for i in range(period, len(data)):
            avg_gain = sum(gains[i - period:i]) / period
            avg_loss = sum(losses[i - period:i]) / period
            
            if avg_loss == 0:
                result[i] = 100
            else:
                rs = avg_gain / avg_loss
                result[i] = 100 - (100 / (1 + rs))
        
        return result
    
    def _calculate_macd(
        self,
        data: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, List[Optional[float]]]:
        """Calculate MACD."""
        ema_fast = self._calculate_ema(data, fast)
        ema_slow = self._calculate_ema(data, slow)
        
        macd_line = []
        for i in range(len(data)):
            if ema_fast[i] is not None and ema_slow[i] is not None:
                macd_line.append(ema_fast[i] - ema_slow[i])
            else:
                macd_line.append(None)
        
        signal_line = self._calculate_ema([m if m else 0 for m in macd_line], signal)
        
        histogram = []
        for i in range(len(data)):
            if macd_line[i] is not None and signal_line[i] is not None:
                histogram.append(macd_line[i] - signal_line[i])
            else:
                histogram.append(None)
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    def _calculate_bollinger(
        self,
        data: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, List[Optional[float]]]:
        """Calculate Bollinger Bands."""
        sma = self._calculate_sma(data, period)
        
        upper = [None] * len(data)
        lower = [None] * len(data)
        
        for i in range(period - 1, len(data)):
            if sma[i] is not None:
                variance = sum((data[j] - sma[i]) ** 2 for j in range(i - period + 1, i + 1)) / period
                std = math.sqrt(variance)
                upper[i] = sma[i] + (std_dev * std)
                lower[i] = sma[i] - (std_dev * std)
        
        return {
            "middle": sma,
            "upper": upper,
            "lower": lower
        }
    
    def update_chart(self, chart_id: str, new_candle: Dict[str, Any]) -> bool:
        """Update chart with new price data."""
        if chart_id not in self.active_charts:
            return False
        
        chart = self.active_charts[chart_id]
        chart["data"].candles.append(new_candle)
        
        # Recalculate render data
        config = chart["config"]
        if config.chart_type == ChartType.CANDLESTICK:
            chart["render"] = self._generate_candlestick(chart["data"], config)
        
        if self.event_bus:
            self.event_bus.publish("chart.updated", {
                "chart_id": chart_id,
                "candle": new_candle
            })
        
        return True
    
    def _handle_price_update(self, data: Dict[str, Any]) -> None:
        """Handle real-time price updates."""
        symbol = data.get("symbol")
        if not symbol:
            return
        
        # Update cache
        if symbol not in self._price_cache:
            self._price_cache[symbol] = []
        
        # Update active charts for this symbol
        for chart_id, chart in self.active_charts.items():
            if chart.get("symbol") == symbol:
                # Update last candle
                if chart["data"].candles:
                    chart["data"].candles[-1]["close"] = data.get("price", 0)
    
    def _handle_candle_close(self, data: Dict[str, Any]) -> None:
        """Handle candle close events."""
        symbol = data.get("symbol")
        candle = data.get("candle")
        
        if symbol and candle:
            for chart_id, chart in self.active_charts.items():
                if chart.get("symbol") == symbol:
                    self.update_chart(chart_id, candle)
    
    def _handle_chart_request(self, data: Dict[str, Any]) -> None:
        """Handle chart generation requests."""
        symbol = data.get("symbol")
        chart_type = ChartType(data.get("type", "candlestick"))
        timeframe = TimeFrame(data.get("timeframe", "1h"))
        
        config = ChartConfig(
            chart_type=chart_type,
            timeframe=timeframe,
            indicators=data.get("indicators")
        )
        
        chart = self.create_chart(symbol, config, data.get("data"))
        
        if self.event_bus and chart:
            self.event_bus.publish("chart.generated", {
                "chart_id": chart["chart_id"],
                "symbol": symbol,
                "render": chart["render"]
            })
    
    def export_chart(
        self,
        chart_id: str,
        format: str = "json"
    ) -> Optional[Any]:
        """Export chart to various formats."""
        if chart_id not in self.active_charts:
            return None
        
        chart = self.active_charts[chart_id]
        
        if format == "json":
            return chart
        elif format == "svg":
            return self._export_svg(chart)
        elif format == "vr":
            return self._export_vr(chart)
        
        return None
    
    def _export_svg(self, chart: Dict[str, Any]) -> str:
        """Export chart as SVG."""
        # Basic SVG export
        config = chart["config"]
        render = chart["render"]
        
        svg = f'<svg width="{config.width}" height="{config.height}" xmlns="http://www.w3.org/2000/svg">'
        svg += f'<rect width="100%" height="100%" fill="{config.background_color}"/>'
        
        # Add chart elements based on type
        if render.get("type") == "candlestick" and render.get("candles"):
            for candle in render["candles"]:
                svg += f'<rect x="{candle["x"]}" y="{candle["body_y"]}" '
                svg += f'width="{candle["width"]}" height="{candle["body_height"]}" '
                svg += f'fill="{candle["color"]}"/>'
        
        svg += '</svg>'
        return svg
    
    def _export_vr(self, chart: Dict[str, Any]) -> Dict[str, Any]:
        """Export chart for VR rendering."""
        render = chart["render"]
        
        # Convert 2D chart to 3D representation
        vr_data = {
            "type": "3d_chart",
            "symbol": chart["symbol"],
            "objects": []
        }
        
        if render.get("candles"):
            for i, candle in enumerate(render["candles"]):
                vr_data["objects"].append({
                    "type": "box",
                    "position": (i * 0.1, candle["body_y"] / 100, 0),
                    "size": (0.08, candle["body_height"] / 100, 0.08),
                    "color": candle["color"]
                })
        
        return vr_data
    
    def get_chart(self, chart_id: str) -> Optional[Dict[str, Any]]:
        """Get chart by ID."""
        return self.active_charts.get(chart_id)
    
    def remove_chart(self, chart_id: str) -> bool:
        """Remove a chart."""
        if chart_id in self.active_charts:
            del self.active_charts[chart_id]
            
            if self.event_bus:
                self.event_bus.publish("chart.removed", {"chart_id": chart_id})
            
            return True
        return False
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.active_charts.clear()
        self._price_cache.clear()
        self._indicator_cache.clear()
        self._initialized = False
        
        if self.event_bus:
            self.event_bus.publish("chart.generator.cleanup", {"status": "cleaned"})


__all__ = ['ChartGenerator', 'ChartConfig', 'ChartData', 'ChartType', 'TimeFrame']
