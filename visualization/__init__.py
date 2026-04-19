"""Kingdom AI — visualization package.

Exposes the trading/market visualization stack:

- ``VisualizationManager`` — the top-level coordinator that every tab or
  service goes through to draw candles, order books, and custom charts.
- ``CandlestickChart``, ``OrderbookViz``, ``ChartBase`` — the concrete
  chart widgets the manager instantiates on demand.

Importing ``visualization.viz_manager`` previously failed because this
package had no ``__init__.py`` and Python treated it as a namespace
directory only. Exporting the public symbols here makes the module
a proper package so ``from visualization.viz_manager import
VisualizationManager`` works everywhere — including the smoke tests in
``tests/test_visualization.py`` that gate the visualization subsystem.
"""
from __future__ import annotations

try:
    from .viz_manager import VisualizationManager, get_visualization_manager
except Exception:  # pragma: no cover - keep the package importable even if deps missing
    VisualizationManager = None  # type: ignore[assignment]
    get_visualization_manager = None  # type: ignore[assignment]

try:
    from .candlestick_chart import CandlestickChart  # noqa: F401
except Exception:  # pragma: no cover
    CandlestickChart = None  # type: ignore[assignment]

try:
    from .orderbook_viz import OrderbookViz  # noqa: F401
except Exception:  # pragma: no cover
    OrderbookViz = None  # type: ignore[assignment]

try:
    from .chart_base import ChartBase  # noqa: F401
except Exception:  # pragma: no cover
    ChartBase = None  # type: ignore[assignment]


__all__ = [
    "VisualizationManager",
    "get_visualization_manager",
    "CandlestickChart",
    "OrderbookViz",
    "ChartBase",
]
