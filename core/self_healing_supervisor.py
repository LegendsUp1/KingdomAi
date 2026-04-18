"""SOTA 2026: Self-healing supervisor.

This component integrates with the existing EventBus + ComponentRegistry.

Goals:
- Observe error events across the system.
- Produce structured diagnoses and recovery actions without unsafe runtime
  code execution.
- Optionally trigger existing recovery systems (e.g., ErrorResolutionSystem)
  via events.

This is designed to work in both GUI and headless modes.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class SelfHealingConfig:
    enabled: bool = True
    cooldown_seconds: float = 15.0
    max_event_history: int = 200
    emit_diagnosis_event: bool = True
    attempt_recovery: bool = True


class SelfHealingSupervisor:
    def __init__(self, event_bus: Any, *, config: Optional[Dict[str, Any]] = None):
        self.event_bus = event_bus
        cfg = config or {}
        self.cfg = SelfHealingConfig(
            enabled=bool(cfg.get("enabled", True)),
            cooldown_seconds=float(cfg.get("cooldown_seconds", 15.0)),
            max_event_history=int(cfg.get("max_event_history", 200)),
            emit_diagnosis_event=bool(cfg.get("emit_diagnosis_event", True)),
            attempt_recovery=bool(cfg.get("attempt_recovery", True)),
        )
        self._last_run_ts = 0.0

    def initialize(self) -> bool:
        if not self.cfg.enabled:
            return True

        try:
            # Common error channels in this codebase
            self.event_bus.subscribe("system.error", self.on_system_error)
            self.event_bus.subscribe("component.error", self.on_component_error)
            self.event_bus.subscribe("error.occurred", self.on_error_occurred)
        except Exception:
            # Some EventBus variants use subscribe_sync
            try:
                self.event_bus.subscribe_sync("system.error", self.on_system_error)
                self.event_bus.subscribe_sync("component.error", self.on_component_error)
                self.event_bus.subscribe_sync("error.occurred", self.on_error_occurred)
            except Exception as exc:
                logger.warning("SelfHealingSupervisor: failed to subscribe to error events: %s", exc)
                return False

        logger.info("✅ SelfHealingSupervisor initialized")
        return True

    def _cooldown_ok(self) -> bool:
        now = time.time()
        if (now - self._last_run_ts) < self.cfg.cooldown_seconds:
            return False
        self._last_run_ts = now
        return True

    def _collect_context(self) -> Dict[str, Any]:
        context: Dict[str, Any] = {}

        # Components
        try:
            from core.component_registry import get_registry

            context["components"] = get_registry().list_components()
        except Exception:
            context["components"] = {}

        # Event history
        try:
            if hasattr(self.event_bus, "get_event_history"):
                context["recent_events"] = self.event_bus.get_event_history(limit=self.cfg.max_event_history)
            else:
                context["recent_events"] = []
        except Exception:
            context["recent_events"] = []

        return context

    def _emit_diagnosis(self, diagnosis: Dict[str, Any]) -> None:
        if not self.cfg.emit_diagnosis_event:
            return
        try:
            self.event_bus.publish("system.self_heal.diagnosis", diagnosis)
        except Exception:
            try:
                self.event_bus.publish_sync("system.self_heal.diagnosis", diagnosis)
            except Exception:
                return

    def _attempt_recovery(self, diagnosis: Dict[str, Any]) -> None:
        if not self.cfg.attempt_recovery:
            return

        # If ErrorResolutionSystem exists, ask it to resolve the specific error.
        try:
            ers = None
            if hasattr(self.event_bus, "get_component"):
                ers = self.event_bus.get_component("error_resolution_system", silent=True)
            if ers is None:
                try:
                    from core.component_registry import get_component

                    ers = get_component("error_resolution_system")
                except Exception:
                    ers = None

            error_id = diagnosis.get("error_id")
            if ers is not None and error_id:
                # Publish event that ErrorResolutionSystem is already wired for.
                try:
                    self.event_bus.publish("error.resolve", {"error_id": error_id})
                except Exception:
                    try:
                        self.event_bus.publish_sync("error.resolve", {"error_id": error_id})
                    except Exception:
                        pass
        except Exception:
            return

    def _build_diagnosis(self, *, source: str, payload: Any) -> Dict[str, Any]:
        context = self._collect_context()
        diagnosis: Dict[str, Any] = {
            "timestamp": time.time(),
            "source": source,
            "payload": payload,
            "components": context.get("components", {}),
            "recent_events": context.get("recent_events", []),
        }

        # attempt to normalize error fields
        if isinstance(payload, dict):
            for k in ("error_id", "component", "message", "exception", "traceback"):
                if k in payload:
                    diagnosis[k] = payload.get(k)

        # Ask Ollama orchestrator for a *plan*, not code execution.
        try:
            from core.ollama_gateway import orchestrator

            prompt = {
                "task": "diagnose_and_recover",
                "instructions": (
                    "Given the recent events and component list, produce a concise diagnosis and "
                    "a recovery plan that uses existing components/events. Do NOT propose runtime code exec."
                ),
                "diagnosis": {
                    "source": source,
                    "payload": payload,
                },
                "components": diagnosis.get("components", {}),
            }
            prompt_text = "Self-heal diagnose request:\n" + json.dumps(prompt, ensure_ascii=False)[:8000]

            # orchestrator APIs vary; prefer an async-free call if present
            plan_text = None
            for attr in ("generate_text", "generate", "complete", "ask"):
                fn = getattr(orchestrator, attr, None)
                if callable(fn):
                    try:
                        res = fn(prompt_text)
                        if isinstance(res, str):
                            plan_text = res
                        elif isinstance(res, dict):
                            plan_text = str(res.get("response") or res.get("text") or "")
                        break
                    except Exception:
                        continue

            if plan_text:
                diagnosis["recovery_plan"] = plan_text
        except Exception:
            # Never let self-healing crash the app.
            pass

        return diagnosis

    def on_system_error(self, payload: Any) -> None:
        if not self._cooldown_ok():
            return
        try:
            diagnosis = self._build_diagnosis(source="system.error", payload=payload)
            self._emit_diagnosis(diagnosis)
            self._attempt_recovery(diagnosis)
        except Exception:
            logger.debug("SelfHealingSupervisor.on_system_error failed\n%s", traceback.format_exc())

    def on_component_error(self, payload: Any) -> None:
        if not self._cooldown_ok():
            return
        try:
            diagnosis = self._build_diagnosis(source="component.error", payload=payload)
            self._emit_diagnosis(diagnosis)
            self._attempt_recovery(diagnosis)
        except Exception:
            logger.debug("SelfHealingSupervisor.on_component_error failed\n%s", traceback.format_exc())

    def on_error_occurred(self, payload: Any) -> None:
        if not self._cooldown_ok():
            return
        try:
            diagnosis = self._build_diagnosis(source="error.occurred", payload=payload)
            self._emit_diagnosis(diagnosis)
            self._attempt_recovery(diagnosis)
        except Exception:
            logger.debug("SelfHealingSupervisor.on_error_occurred failed\n%s", traceback.format_exc())
