"""Safety layer protecting AI cognitive processes from overload and corruption."""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("kingdom_ai.neuroprotection_layer")

MAX_COGNITIVE_LOAD = 100.0
CIRCUIT_BREAKER_THRESHOLD = 0.85
ANOMALY_PATTERNS: List[str] = [
    "\\x00" * 10,
    "DROP TABLE",
    "<script>",
    "eval(",
    "__import__(",
    "os.system(",
    "subprocess.call(",
]


class _CircuitBreaker:
    __slots__ = ("component", "tripped", "trip_count", "tripped_at", "cooldown_sec")

    def __init__(self, component: str, cooldown_sec: float = 30.0) -> None:
        self.component = component
        self.tripped: bool = False
        self.trip_count: int = 0
        self.tripped_at: float = 0.0
        self.cooldown_sec = cooldown_sec

    def trip(self) -> None:
        self.tripped = True
        self.trip_count += 1
        self.tripped_at = time.monotonic()

    def check_reset(self) -> bool:
        if self.tripped and (time.monotonic() - self.tripped_at) >= self.cooldown_sec:
            self.tripped = False
            return True
        return False


class NeuroprotectionLayer:
    """Monitors cognitive load and guards against overload, corruption, and adversarial input."""

    def __init__(self, event_bus: Any = None, cooldown_sec: float = 30.0) -> None:
        self.event_bus = event_bus
        self._cooldown_sec = cooldown_sec
        self._load: float = 0.0
        self._breakers: Dict[str, _CircuitBreaker] = {}
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._anomaly_log: List[Dict[str, Any]] = []
        self._blocked_hashes: Set[str] = set()
        if event_bus:
            event_bus.subscribe("neuroprotection.check.request", self._on_check_request)
        logger.info("NeuroprotectionLayer initialised (cooldown=%.1fs)", cooldown_sec)

    def check_cognitive_load(self) -> Dict[str, Any]:
        for br in self._breakers.values():
            br.check_reset()
        active_breakers = sum(1 for br in self._breakers.values() if br.tripped)
        utilisation = self._load / MAX_COGNITIVE_LOAD
        return {
            "current_load": round(self._load, 2),
            "max_load": MAX_COGNITIVE_LOAD,
            "utilisation": round(utilisation, 4),
            "active_breakers": active_breakers,
            "total_breakers": len(self._breakers),
            "status": "overloaded" if utilisation > CIRCUIT_BREAKER_THRESHOLD else "nominal",
        }

    def validate_input(self, data: Any) -> Dict[str, Any]:
        text = str(data) if not isinstance(data, str) else data
        findings: List[str] = []
        for pattern in ANOMALY_PATTERNS:
            if pattern.lower() in text.lower():
                findings.append(f"Blocked pattern detected: {pattern[:20]}")
        data_hash = hashlib.sha256(text.encode(errors="replace")).hexdigest()[:16]
        if data_hash in self._blocked_hashes:
            findings.append("Previously blocked content hash")
        if len(text) > 100_000:
            findings.append(f"Oversized input ({len(text)} chars)")
        is_safe = len(findings) == 0
        if not is_safe:
            self._blocked_hashes.add(data_hash)
            self._anomaly_log.append({"timestamp": time.time(), "hash": data_hash, "findings": findings})
            logger.warning("Input validation failed: %s", "; ".join(findings))
        return {"safe": is_safe, "findings": findings, "hash": data_hash}

    def enforce_circuit_breaker(self, component: str) -> Dict[str, Any]:
        if component not in self._breakers:
            self._breakers[component] = _CircuitBreaker(component, self._cooldown_sec)
        br = self._breakers[component]
        if br.tripped:
            if br.check_reset():
                logger.info("Circuit breaker for '%s' auto-reset", component)
                return {"component": component, "tripped": False, "action": "auto_reset"}
            return {"component": component, "tripped": True, "action": "already_tripped", "trip_count": br.trip_count}
        self._request_counts[component] += 1
        load_metrics = self.check_cognitive_load()
        if load_metrics["utilisation"] > CIRCUIT_BREAKER_THRESHOLD:
            br.trip()
            self._load = max(self._load - 10.0, 0.0)
            logger.warning("Circuit breaker TRIPPED for '%s' (load=%.2f)", component, self._load)
            return {"component": component, "tripped": True, "action": "tripped", "trip_count": br.trip_count}
        return {"component": component, "tripped": False, "action": "passed", "requests": self._request_counts[component]}

    def add_load(self, amount: float) -> float:
        self._load = min(self._load + amount, MAX_COGNITIVE_LOAD)
        return self._load

    def reduce_load(self, amount: float) -> float:
        self._load = max(self._load - amount, 0.0)
        return self._load

    def get_protection_status(self) -> Dict[str, Any]:
        for br in self._breakers.values():
            br.check_reset()
        return {
            "cognitive_load": self.check_cognitive_load(),
            "circuit_breakers": {
                name: {"tripped": br.tripped, "trip_count": br.trip_count}
                for name, br in self._breakers.items()
            },
            "anomalies_detected": len(self._anomaly_log),
            "blocked_hashes": len(self._blocked_hashes),
        }

    def _on_check_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("check request ignored — expected dict")
            return
        action = data.get("action", "status")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "status":
                result["data"] = self.get_protection_status()
            elif action == "load":
                result["data"] = self.check_cognitive_load()
            elif action == "validate":
                result["data"] = self.validate_input(data.get("input", ""))
            elif action == "circuit_breaker":
                result["data"] = self.enforce_circuit_breaker(data.get("component", "unknown"))
            elif action == "add_load":
                self.add_load(data.get("amount", 5.0))
                result["data"] = self.check_cognitive_load()
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("Neuroprotection check failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("neuroprotection.status.update", result)
