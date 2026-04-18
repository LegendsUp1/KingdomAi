#!/usr/bin/env python3
"""
Unified Brain Router - Ollama + NemoClaw Dual-Backend Architecture

Ollama handles LLM inference (always active).
NemoClaw handles secure sandbox execution (always active when available).
Both backends process every request in parallel.  The two paths are
independent: Ollama inference runs alongside NemoClaw sandbox execution.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('kingdom_ai.unified_brain_router')


class SecurityLevel(Enum):
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"


class BackendType(Enum):
    OLLAMA = "ollama"
    NEMOCLAW = "nemoclaw"
    AUTO = "auto"


@dataclass
class RoutingDecision:
    backend: BackendType
    reason: str
    security_level: SecurityLevel
    confidence: float


class UnifiedBrainRouter:
    """
    Unified router — Ollama + NemoClaw operate simultaneously.

    - Ollama handles LLM inference (always active)
    - NemoClaw handles secure sandbox execution (always active when available)
    - Both backends process every request in parallel
    - Monitors performance and costs for both backends
    """

    def __init__(self, event_bus, ollama_connector=None, nemoclaw_bridge=None):
        self.event_bus = event_bus
        self.ollama_connector = ollama_connector
        self.nemoclaw_bridge = nemoclaw_bridge

        self.routing_stats = {
            "ollama": 0,
            "nemoclaw": 0,
            "errors": 0,
            "total_requests": 0,
        }

        self.performance_metrics = {
            "ollama_avg_latency": 0.0,
            "nemoclaw_avg_latency": 0.0,
            "ollama_success_rate": 1.0,
            "nemoclaw_success_rate": 1.0,
        }

        self.security_policies: Dict[str, SecurityLevel] = {
            "code_execution": SecurityLevel.CRITICAL,
            "file_operations": SecurityLevel.HIGH,
            "network_requests": SecurityLevel.HIGH,
            "system_commands": SecurityLevel.CRITICAL,
            "data_processing": SecurityLevel.STANDARD,
            "chat": SecurityLevel.STANDARD,
            "analysis": SecurityLevel.STANDARD,
            "financial": SecurityLevel.HIGH,
            "personal_data": SecurityLevel.HIGH,
        }

        self.cost_thresholds = {
            "nemoclaw_max_daily_requests": 100,
            "nemoclaw_cost_per_request": 0.01,
            "ollama_cost_per_request": 0.0,
        }

        self._register_event_handlers()
        logger.info("Unified Brain Router initialized — dual-backend mode")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pub(self, event: str, data: Dict[str, Any]) -> None:
        """Publish on the event bus (sync-safe)."""
        if not self.event_bus:
            return
        publish_fn = getattr(self.event_bus, "publish", None)
        if publish_fn:
            try:
                publish_fn(event, data)
            except Exception as exc:
                logger.debug("Event publish failed (%s): %s", event, exc)

    # ------------------------------------------------------------------
    # Event wiring
    # ------------------------------------------------------------------

    def _register_event_handlers(self):
        if not self.event_bus:
            return
        sub = getattr(self.event_bus, "subscribe", None)
        if sub:
            sub("brain.request", self._handle_brain_request_sync)
            sub("brain.status", self._handle_status_request_sync)
            sub("brain.config", self._handle_config_request_sync)

    def _handle_brain_request_sync(self, data: Dict[str, Any]):
        """Sync wrapper — schedules dual dispatch as a task."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._handle_brain_request(data))
            else:
                loop.run_until_complete(self._handle_brain_request(data))
        except RuntimeError:
            asyncio.run(self._handle_brain_request(data))

    def _handle_status_request_sync(self, data: Dict[str, Any]):
        self._pub("brain.status_update", self._build_status())

    def _handle_config_request_sync(self, data: Dict[str, Any]):
        if isinstance(data, dict):
            if "security_policies" in data:
                self.security_policies.update(data["security_policies"])
                logger.info("Security policies updated")
            if "cost_thresholds" in data:
                self.cost_thresholds.update(data["cost_thresholds"])
                logger.info("Cost thresholds updated")
        self._pub("brain.config_updated", {
            "security_policies": {k: v.value if isinstance(v, SecurityLevel) else v
                                  for k, v in self.security_policies.items()},
            "cost_thresholds": self.cost_thresholds,
        })

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self):
        """Initialize both backend connections."""
        if self.ollama_connector:
            try:
                await self.ollama_connector.initialize()
                logger.info("Ollama connector initialized")
            except Exception as e:
                logger.error("Ollama initialization failed: %s", e)

        if self.nemoclaw_bridge:
            try:
                await self.nemoclaw_bridge.initialize()
                logger.info("NemoClaw bridge initialized")
            except Exception as e:
                logger.error("NemoClaw initialization failed: %s", e)

        self._pub("brain.router.initialized", {
            "ollama_available": self.ollama_connector is not None,
            "nemoclaw_available": (
                self.nemoclaw_bridge.nemoclaw_available
                if self.nemoclaw_bridge else False
            ),
        })

    # ------------------------------------------------------------------
    # Dual dispatch
    # ------------------------------------------------------------------

    async def _handle_brain_request(self, data: Dict[str, Any]):
        """Dispatch to BOTH Ollama and NemoClaw simultaneously."""
        prompt = data.get("prompt", "")
        security_level = data.get("security_level", SecurityLevel.STANDARD.value)
        session_id = data.get("session_id")

        decision = RoutingDecision(
            backend=BackendType.AUTO,
            reason="Dual-backend: Ollama inference + NemoClaw execution",
            security_level=self._parse_security(security_level),
            confidence=1.0,
        )

        ollama_task = asyncio.create_task(
            self._route_to_ollama(prompt, data, decision)
        )

        nemoclaw_task = None
        if self.nemoclaw_bridge and getattr(self.nemoclaw_bridge, "nemoclaw_available", False):
            nemoclaw_task = asyncio.create_task(
                self._route_to_nemoclaw(prompt, security_level, session_id, decision)
            )

        await ollama_task
        if nemoclaw_task is not None:
            await nemoclaw_task

    async def _route_to_ollama(self, prompt: str, data: Dict[str, Any],
                               decision: RoutingDecision):
        """Dispatch to Ollama for LLM inference."""
        self.routing_stats["ollama"] += 1
        self.routing_stats["total_requests"] += 1
        try:
            if self.ollama_connector:
                self._pub("thoth.request", {"prompt": prompt, **data})
                logger.info("Dispatched to Ollama (inference)")
                self._pub("brain.route_decision", {
                    "backend": "ollama",
                    "reason": decision.reason,
                    "security_level": decision.security_level.value,
                })
            else:
                logger.error("Ollama connector not available")
                self.routing_stats["errors"] += 1
        except Exception as e:
            logger.error("Ollama dispatch failed: %s", e)
            self.routing_stats["errors"] += 1

    async def _route_to_nemoclaw(self, prompt: str, security_level: str,
                                 session_id: Optional[str],
                                 decision: RoutingDecision):
        """Dispatch to NemoClaw for sandbox execution."""
        self.routing_stats["nemoclaw"] += 1
        try:
            if self.nemoclaw_bridge and getattr(self.nemoclaw_bridge, "nemoclaw_available", False):
                response = await self.nemoclaw_bridge.send_to_nemoclaw(
                    prompt, security_level, session_id
                )
                logger.info("Dispatched to NemoClaw (sandbox execution)")
                self._pub("nemoclaw.response", response)
                self._pub("brain.route_decision", {
                    "backend": "nemoclaw",
                    "reason": decision.reason,
                    "security_level": decision.security_level.value,
                })
            else:
                logger.warning("NemoClaw bridge not available for dispatch")
                self.routing_stats["errors"] += 1
        except Exception as e:
            logger.error("NemoClaw dispatch failed: %s", e)
            self.routing_stats["errors"] += 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_security_policy(self, task_type: str, level: SecurityLevel):
        self.security_policies[task_type] = level
        logger.info("Security policy updated: %s -> %s", task_type, level.value)

    def get_routing_stats(self) -> Dict[str, Any]:
        return {
            "stats": self.routing_stats.copy(),
            "performance": self.performance_metrics.copy(),
            "timestamp": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_security(value: str) -> SecurityLevel:
        try:
            return SecurityLevel(value)
        except (ValueError, KeyError):
            return SecurityLevel.STANDARD

    def _build_status(self) -> Dict[str, Any]:
        return {
            "routing_stats": self.routing_stats,
            "performance_metrics": self.performance_metrics,
            "backends": {
                "ollama": {
                    "available": self.ollama_connector is not None,
                    "status": "connected" if self.ollama_connector else "not_configured",
                },
                "nemoclaw": {
                    "available": (
                        self.nemoclaw_bridge.nemoclaw_available
                        if self.nemoclaw_bridge else False
                    ),
                    "status": (
                        getattr(self.nemoclaw_bridge, "sandbox_status", "unknown")
                        if self.nemoclaw_bridge else "not_configured"
                    ),
                },
            },
            "security_policies": {
                k: v.value if isinstance(v, SecurityLevel) else v
                for k, v in self.security_policies.items()
            },
            "timestamp": datetime.now().isoformat(),
        }
