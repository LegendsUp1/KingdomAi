"""Aggregates data from all chemistry/manufacturing engines for dashboard display."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.visualization_dashboard")

DASHBOARD_REQUEST = "chemistry.dashboard.request"
DASHBOARD_UPDATE = "chemistry.dashboard.update"


class DataSource:
    """Wrapper around a registered data source with optional polling."""

    __slots__ = ("name", "source", "last_value", "last_updated")

    def __init__(self, name: str, source: Any) -> None:
        self.name = name
        self.source = source
        self.last_value: Optional[Dict[str, Any]] = None
        self.last_updated: float = 0.0

    def poll(self) -> Dict[str, Any]:
        """Pull current metrics from the source object."""
        result: Dict[str, Any] = {"name": self.name, "status": "unknown", "metrics": {}}

        if hasattr(self.source, "list_all"):
            items = self.source.list_all()
            result["metrics"]["item_count"] = len(items) if isinstance(items, list) else 0
            result["status"] = "online"
        elif hasattr(self.source, "list_alloys"):
            result["metrics"]["alloy_count"] = len(self.source.list_alloys())
            result["status"] = "online"
        elif hasattr(self.source, "list_elements"):
            result["metrics"]["element_count"] = len(self.source.list_elements())
            result["status"] = "online"
        elif hasattr(self.source, "list_processes"):
            result["metrics"]["process_count"] = len(self.source.list_processes())
            result["status"] = "online"
        elif hasattr(self.source, "_blueprints"):
            result["metrics"]["blueprint_count"] = len(self.source._blueprints)
            result["status"] = "online"
        elif hasattr(self.source, "_views"):
            result["metrics"]["view_count"] = len(self.source._views)
            result["status"] = "online"
        else:
            result["status"] = "online"
            result["metrics"]["type"] = type(self.source).__name__

        result["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.last_value = result
        self.last_updated = time.time()
        return result


class VisualizationDashboard:
    """Central dashboard that aggregates metrics from every chemistry/manufacturing engine."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._sources: Dict[str, DataSource] = {}
        self._snapshot_history: List[Dict[str, Any]] = []
        self._max_history = 100
        logger.info("VisualizationDashboard initialised")

        if event_bus:
            event_bus.subscribe(DASHBOARD_REQUEST, self._on_request)
            logger.debug("Subscribed to %s", DASHBOARD_REQUEST)

    # ── public API ───────────────────────────────────────────────────────────

    def register_data_source(self, name: str, source: Any) -> None:
        """Register a sub-engine as a named data source."""
        self._sources[name] = DataSource(name, source)
        logger.info("register_data_source: %s (%s)", name, type(source).__name__)

    def unregister_data_source(self, name: str) -> bool:
        if name in self._sources:
            del self._sources[name]
            logger.info("unregister_data_source: %s", name)
            return True
        return False

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Poll all registered sources and return aggregated dashboard data."""
        engine_metrics: Dict[str, Any] = {}
        online_count = 0
        total_items = 0

        for name, ds in self._sources.items():
            snapshot = ds.poll()
            engine_metrics[name] = snapshot
            if snapshot.get("status") == "online":
                online_count += 1
            for v in snapshot.get("metrics", {}).values():
                if isinstance(v, (int, float)):
                    total_items += v

        dashboard: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sources_registered": len(self._sources),
            "sources_online": online_count,
            "total_tracked_items": int(total_items),
            "engines": engine_metrics,
        }

        self._snapshot_history.append(dashboard)
        if len(self._snapshot_history) > self._max_history:
            self._snapshot_history = self._snapshot_history[-self._max_history:]

        logger.debug("get_dashboard_data: %d sources, %d online", len(self._sources), online_count)
        return dashboard

    def format_for_gui(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Transform raw dashboard data into a GUI-friendly structure.

        Returns a dict with ``summary``, ``cards`` (one per engine), and ``chart_data``.
        """
        if data is None:
            data = self.get_dashboard_data()

        cards: List[Dict[str, Any]] = []
        for name, engine_data in data.get("engines", {}).items():
            metrics = engine_data.get("metrics", {})
            primary_metric_key = next(iter(metrics), None)
            primary_value = metrics.get(primary_metric_key, 0) if primary_metric_key else 0
            cards.append({
                "title": name.replace("_", " ").title(),
                "status": engine_data.get("status", "unknown"),
                "status_color": "#22c55e" if engine_data.get("status") == "online" else "#ef4444",
                "primary_metric": primary_metric_key or "",
                "primary_value": primary_value,
                "all_metrics": metrics,
                "last_updated": engine_data.get("last_updated", ""),
            })

        chart_points: List[Dict[str, Any]] = []
        for snap in self._snapshot_history[-20:]:
            chart_points.append({
                "timestamp": snap.get("timestamp", ""),
                "total_items": snap.get("total_tracked_items", 0),
                "sources_online": snap.get("sources_online", 0),
            })

        gui: Dict[str, Any] = {
            "summary": {
                "total_engines": data.get("sources_registered", 0),
                "engines_online": data.get("sources_online", 0),
                "total_items": data.get("total_tracked_items", 0),
                "last_refresh": data.get("timestamp", ""),
            },
            "cards": cards,
            "chart_data": chart_points,
        }
        return gui

    def get_history(self, last_n: int = 10) -> List[Dict[str, Any]]:
        """Return the last *n* dashboard snapshots."""
        return self._snapshot_history[-last_n:]

    def list_sources(self) -> List[str]:
        return list(self._sources.keys())

    # ── event bus handler ────────────────────────────────────────────────────

    def _on_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("_on_request: expected dict, got %s", type(data).__name__)
            return

        action = data.get("action", "get")
        result: Any

        if action == "get":
            result = self.get_dashboard_data()
        elif action == "gui":
            result = self.format_for_gui()
        elif action == "history":
            result = self.get_history(int(data.get("last_n", 10)))
        elif action == "list_sources":
            result = self.list_sources()
        else:
            result = {"error": f"Unknown dashboard action: {action}"}

        if self.event_bus:
            self.event_bus.publish(DASHBOARD_UPDATE, {"action": action, "result": result})
            logger.debug("Published %s for action=%s", DASHBOARD_UPDATE, action)
