"""Harmonic orchestrator coordinating multiple AI sub-systems."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.harmonic_orchestrator_v3")


class _SubSystem:
    __slots__ = ("name", "handler", "priority", "load", "total_tasks", "total_time", "failures", "active")

    def __init__(self, name: str, handler: Callable[..., Any], priority: int = 5) -> None:
        self.name = name
        self.handler = handler
        self.priority = priority
        self.load: float = 0.0
        self.total_tasks: int = 0
        self.total_time: float = 0.0
        self.failures: int = 0
        self.active: bool = True


class HarmonicOrchestratorV3:
    """Coordinates AI sub-systems with priority routing and load balancing."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._subsystems: Dict[str, _SubSystem] = {}
        self._task_log: List[Dict[str, Any]] = []
        self._max_load: float = 1.0
        if event_bus:
            event_bus.subscribe("orchestrator.task.request", self._on_task_request)
        logger.info("HarmonicOrchestratorV3 initialised")

    def register_subsystem(self, name: str, handler: Callable[..., Any], priority: int = 5) -> Dict[str, Any]:
        sub = _SubSystem(name, handler, priority)
        self._subsystems[name] = sub
        logger.info("Registered sub-system '%s' (priority=%d)", name, priority)
        return {"name": name, "priority": priority, "status": "registered"}

    def orchestrate(self, task: Dict[str, Any]) -> Dict[str, Any]:
        target = task.get("target")
        if target and target in self._subsystems:
            sub = self._subsystems[target]
            if sub.active:
                return self._dispatch(sub, task)
        best = self._select_best(task)
        if not best:
            logger.warning("No available sub-system for task: %s", task.get("type", "unknown"))
            return {"success": False, "error": "No available sub-system"}
        return self._dispatch(best, task)

    def _select_best(self, task: Dict[str, Any]) -> Optional[_SubSystem]:
        candidates = [s for s in self._subsystems.values() if s.active and s.load < self._max_load]
        if not candidates:
            return None
        candidates.sort(key=lambda s: (-s.priority, s.load))
        return candidates[0]

    def _dispatch(self, sub: _SubSystem, task: Dict[str, Any]) -> Dict[str, Any]:
        sub.load = min(sub.load + 0.1, self._max_load)
        start = time.monotonic()
        try:
            result = sub.handler(task)
            elapsed = time.monotonic() - start
            sub.total_tasks += 1
            sub.total_time += elapsed
            sub.load = max(sub.load - 0.1, 0.0)
            entry = {"subsystem": sub.name, "task": task.get("type", "unknown"), "elapsed": round(elapsed, 4), "success": True}
            self._task_log.append(entry)
            logger.debug("Task dispatched to '%s' in %.4fs", sub.name, elapsed)
            return {"success": True, "subsystem": sub.name, "result": result, "elapsed": round(elapsed, 4)}
        except Exception as exc:
            elapsed = time.monotonic() - start
            sub.failures += 1
            sub.load = max(sub.load - 0.1, 0.0)
            self._task_log.append({"subsystem": sub.name, "task": task.get("type", "unknown"), "elapsed": round(elapsed, 4), "success": False, "error": str(exc)})
            logger.exception("Sub-system '%s' failed", sub.name)
            return {"success": False, "subsystem": sub.name, "error": str(exc)}

    def get_harmony_score(self) -> float:
        if not self._subsystems:
            return 1.0
        active = [s for s in self._subsystems.values() if s.active]
        if not active:
            return 0.0
        load_balance = 1.0 - (max(s.load for s in active) - min(s.load for s in active)) if len(active) > 1 else 1.0
        failure_rate = sum(s.failures for s in active) / max(sum(s.total_tasks for s in active), 1)
        health = sum(1 for s in self._subsystems.values() if s.active) / len(self._subsystems)
        score = (load_balance * 0.4 + (1.0 - failure_rate) * 0.4 + health * 0.2)
        return round(max(0.0, min(1.0, score)), 4)

    def rebalance(self) -> Dict[str, Any]:
        active = [s for s in self._subsystems.values() if s.active]
        if not active:
            return {"rebalanced": False, "reason": "no active subsystems"}
        avg_load = sum(s.load for s in active) / len(active)
        adjustments: Dict[str, float] = {}
        for s in active:
            old = s.load
            s.load = (s.load + avg_load) / 2.0
            adjustments[s.name] = round(s.load - old, 4)
        logger.info("Rebalanced %d sub-systems (avg_load=%.4f)", len(active), avg_load)
        return {"rebalanced": True, "adjustments": adjustments, "harmony_score": self.get_harmony_score()}

    def get_status(self) -> Dict[str, Any]:
        return {
            "subsystem_count": len(self._subsystems),
            "active_count": sum(1 for s in self._subsystems.values() if s.active),
            "harmony_score": self.get_harmony_score(),
            "subsystems": {
                name: {"priority": s.priority, "load": round(s.load, 4), "tasks": s.total_tasks, "failures": s.failures, "active": s.active}
                for name, s in self._subsystems.items()
            },
            "total_tasks_dispatched": len(self._task_log),
        }

    def _on_task_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("task request ignored — expected dict")
            return
        result = self.orchestrate(data)
        if self.event_bus:
            self.event_bus.publish("orchestrator.task.result", result)
