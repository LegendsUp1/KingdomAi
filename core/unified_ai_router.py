"""
Unified AI Router - Bridges legacy ai.request to brain.request and deduplicates ai.response.

This module ensures:
1. All ai.request events are converted to brain.request for BrainRouter handling
2. All ai.response events are deduplicated and emitted as ai.response.unified
3. Thread-safe UI updates via the unified response event
"""

import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class UnifiedAIRouter:
    """Routes all AI requests through BrainRouter and deduplicates responses."""

    def __init__(self, event_bus: Any):
        """Initialize the Unified AI Router.

        Args:
            event_bus: The application's event bus for pub/sub
        """
        self.event_bus = event_bus
        self.logger = logger
        self._initialized = False

        # Deduplication state
        self._seen_response_ids: Dict[str, float] = {}  # request_id -> timestamp
        self._response_lock = threading.Lock()
        self._dedup_window_seconds = 2.0  # Reduced: redundant publishers removed

        self._seen_delta_seq: Dict[str, int] = {}
        self._seen_delta_ids: Dict[str, float] = {}
        self._streaming_requests: Set[str] = set()

        # Track active requests for logging/debugging
        self._active_requests: Set[str] = set()
        # Track speak flag for each request
        self._request_speak_flags: Dict[str, bool] = {}
        self._capability_snapshot: Dict[str, Any] = {}
        self._capability_snapshot_ts: float = 0.0
        self._capability_snapshot_ttl_s: float = 300.0  # SOTA 2026: Cache for 5 minutes (was 30s)
        self._awareness_covered_routes: Set[str] = set()
        self._awareness_route_hits: Dict[str, float] = {}

        # NemoClaw awareness (populated via event bus status updates)
        self._nemoclaw_available: bool = False
        self._nemoclaw_stats: Dict[str, int] = {"responses_bridged": 0}

    def _ensure_correlation_id(self, data: Dict[str, Any], request_id: str) -> str:
        """Return a stable correlation id for pipeline telemetry."""
        cid = data.get("correlation_id") if isinstance(data, dict) else None
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
        if isinstance(request_id, str) and request_id.strip() and request_id != "unknown":
            return request_id
        return f"ai-{uuid.uuid4().hex}"

    def _emit_pipeline_telemetry(
        self,
        stage: str,
        request_id: str,
        correlation_id: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit lightweight, non-blocking pipeline telemetry."""
        if not self.event_bus:
            return
        payload: Dict[str, Any] = {
            "stage": stage,
            "component": "UnifiedAIRouter",
            "request_id": request_id,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if isinstance(extra, dict):
            payload.update(extra)
        try:
            self.event_bus.publish("ai.pipeline.telemetry", payload)
        except Exception as e:
            self.logger.debug(f"Telemetry publish failed (non-critical): {e}")

    def _get_capability_snapshot(self) -> Dict[str, Any]:
        """Return cached capability snapshot. SOTA 2026: Lightweight, long-cached."""
        now = time.time()
        if self._capability_snapshot and (now - self._capability_snapshot_ts) < self._capability_snapshot_ttl_s:
            return self._capability_snapshot
        # Build a lightweight snapshot without expensive imports/scans
        local_snapshot = {
            "schema_version": "v1",
            "timestamp": datetime.utcnow().isoformat(),
            "python_version": sys.version.split(" ")[0],
            "platform": sys.platform,
            "ollama_url": os.environ.get("KINGDOM_OLLAMA_BASE_URL", "http://localhost:11434"),
            "router": "UnifiedAIRouter",
            "nemoclaw_available": self._nemoclaw_available,
            "nemoclaw_stats": dict(self._nemoclaw_stats),
        }
        self._capability_snapshot = local_snapshot
        self._capability_snapshot_ts = now
        return local_snapshot

    def _inject_awareness(self, data: Dict[str, Any], route_name: str) -> None:
        """Inject awareness metadata into existing request payloads."""
        if not isinstance(data, dict):
            return
        if not data.get("awareness_snapshot"):
            data["awareness_snapshot"] = self._get_capability_snapshot()
        data["system_wide_unified_context"] = True
        data["awareness_route"] = route_name
        self._awareness_covered_routes.add(route_name)
        self._awareness_route_hits[route_name] = time.time()

    def _inject_engine_chain_hint(self, data: Dict[str, Any]) -> None:
        """Attach whole-studio chain hint ONLY for creation/visual requests."""
        if not isinstance(data, dict):
            return
        prompt = str(data.get("prompt") or data.get("message") or data.get("text") or "").strip().lower()
        if not prompt:
            return
        # SOTA 2026 FIX: Only parse for creation-related prompts to avoid overhead
        _creation_keywords = ("create", "generate", "design", "build", "draw", "render",
                             "make", "animate", "fabricate", "blueprint", "schematic")
        if not any(kw in prompt for kw in _creation_keywords):
            return
        try:
            from core.creation_orchestrator import get_orchestrator
            orch = get_orchestrator(event_bus=self.event_bus)
            pipeline = orch.parse_request(prompt)
            if pipeline and getattr(pipeline, "tasks", None):
                data["preferred_engine_chain"] = [t.engine.value for t in pipeline.tasks]
                data["preferred_engine_ops"] = [t.operation for t in pipeline.tasks]
                data["routing_policy"] = (getattr(pipeline, "metadata", {}) or {}).get("routing_policy", "whole_studio_semantic_v1")
        except Exception as e:
            self.logger.debug(f"Engine chain hint unavailable: {e}")

    def _handle_capability_report(self, data: Any) -> None:
        """Emit router-side capability coverage report."""
        if not self.event_bus:
            return
        reason = "manual"
        if isinstance(data, dict):
            reason = str(data.get("reason", reason))
        payload = {
            "source": "UnifiedAIRouter",
            "schema_version": "v1",
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "awareness_covered_routes": sorted(self._awareness_covered_routes),
            "awareness_route_hits": dict(self._awareness_route_hits),
            "snapshot": self._get_capability_snapshot(),
        }
        try:
            self.event_bus.publish("kingdom.capabilities.reported", payload)
        except Exception as e:
            self.logger.debug(f"capabilities.report publish failed: {e}")

    def initialize(self) -> bool:
        """Initialize the router by subscribing to events.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            self.logger.warning("UnifiedAIRouter already initialized")
            return True

        if not self.event_bus:
            self.logger.error("UnifiedAIRouter requires an event bus")
            return False

        try:
            # Subscribe to legacy ai.request and bridge to brain.request
            subscribe_fn = getattr(self.event_bus, "subscribe", None)
            subscribe_sync_fn = getattr(self.event_bus, "subscribe_sync", None)

            # Prefer subscribe_sync for synchronous handling
            sub = subscribe_sync_fn if subscribe_sync_fn else subscribe_fn

            if sub:
                # Track ai.request metadata without forwarding to avoid duplicate inference.
                sub("ai.request", self._track_ai_request_metadata)
                sub("brain.request", self._track_brain_request_metadata)
                sub("kingdom.brain.request", self._track_brain_request_metadata)
                sub("visual.request", self._track_brain_request_metadata)
                sub("creative.request", self._track_brain_request_metadata)
                sub("voice.ai.request", self._track_brain_request_metadata)
                sub("trading.ai.request", self._track_brain_request_metadata)
                sub("mining.ai.request", self._track_brain_request_metadata)
                sub("code.generate.request", self._track_brain_request_metadata)
                sub("kingdom.capabilities.snapshot", self._handle_capability_snapshot)
                sub("kingdom.capabilities.report", self._handle_capability_report)
                sub("ai.response", self._handle_ai_response)
                sub("ai.response.delta", self._handle_ai_response_delta)
                # NemoClaw events — track responses and status for all tabs
                sub("nemoclaw.response", self._handle_nemoclaw_response)
                sub("nemoclaw.status_update", self._handle_nemoclaw_status_update)
                sub("nemoclaw.initialized", self._handle_nemoclaw_status_update)
                self.logger.info("✅ UnifiedAIRouter subscribed to ai.request metadata + ai.response dedup + NemoClaw")
            else:
                self.logger.error("❌ No subscribe method available on event bus")
                return False

            self._initialized = True
            try:
                self.event_bus.publish("kingdom.capabilities.refresh", {
                    "reason": "unified_router_startup",
                    "source": "UnifiedAIRouter",
                })
            except Exception:
                pass
            self.logger.info("✅ UnifiedAIRouter initialized - unified response + request telemetry active")
            return True

        except Exception as e:
            self.logger.error(f"❌ UnifiedAIRouter initialization failed: {e}")
            return False

    def _track_ai_request_metadata(self, data: Any) -> None:
        """Track request metadata and bridge ai.request to brain.request."""
        if not isinstance(data, dict):
            return
        self._inject_awareness(data, "ai.request")
        self._inject_engine_chain_hint(data)
        request_id = data.get("request_id") or f"ai_{int(time.time() * 1000)}"
        speak_flag = bool(data.get("speak", True))
        with self._response_lock:
            self._active_requests.add(request_id)
            self._request_speak_flags[request_id] = speak_flag
        if str(request_id).startswith("identity_"):
            self.logger.info("🔵 Tracked identity request %s (speak=%s)", request_id, speak_flag)
        try:
            if self.event_bus:
                # Bridge legacy ai.request traffic into BrainRouter's canonical path.
                brain_payload = dict(data)
                brain_payload["request_id"] = request_id
                brain_payload.setdefault("source_event", "ai.request")
                brain_payload.setdefault("source", "UnifiedAIRouter")
                self.event_bus.publish("brain.request", brain_payload)
                self.event_bus.publish("learning.request", {
                    "request_id": request_id,
                    "prompt": data.get("prompt") or data.get("message") or data.get("text") or "",
                    "source_tab": data.get("source_tab"),
                    "source": data.get("source"),
                    "model": data.get("model"),
                    "awareness_snapshot": data.get("awareness_snapshot") or self._get_capability_snapshot(),
                    "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
                })
        except Exception as e:
            self.logger.debug(f"learning.request publish failed: {e}")

    def _track_brain_request_metadata(self, data: Any) -> None:
        """Track direct brain request paths so learning sees all tab routes."""
        if not isinstance(data, dict):
            return
        route_name = str(
            data.get("awareness_route")
            or data.get("source_event")
            or data.get("source")
            or data.get("domain")
            or "brain.request"
        )
        self._inject_awareness(data, route_name)
        self._inject_engine_chain_hint(data)
        request_id = data.get("request_id") or f"brain_{int(time.time() * 1000)}"
        try:
            if self.event_bus:
                self.event_bus.publish("learning.request", {
                    "request_id": request_id,
                    "prompt": data.get("prompt") or data.get("message") or data.get("text") or "",
                    "source_tab": data.get("source_tab") or data.get("domain"),
                    "source": data.get("source") or "brain_request",
                    "model": data.get("model"),
                    "awareness_snapshot": data.get("awareness_snapshot") or self._get_capability_snapshot(),
                    "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
                })
        except Exception as e:
            self.logger.debug(f"brain learning.request publish failed: {e}")

    def _handle_capability_snapshot(self, data: Any) -> None:
        """Cache latest capability snapshot for request/learning enrichment."""
        if not isinstance(data, dict):
            return
        snapshot = data.get("snapshot")
        if isinstance(snapshot, dict):
            self._capability_snapshot = snapshot
            self._capability_snapshot_ts = time.time()

    def _handle_ai_response(self, data: Any) -> None:
        """Deduplicate ai.response and emit ai.response.unified.

        Args:
            data: The ai.response event payload
        """
        try:
            self._handle_ai_response_inner(data)
        except Exception as e:
            import traceback
            self.logger.error(
                "❌ UnifiedAIRouter._handle_ai_response CRASHED: %s\n%s",
                e, traceback.format_exc(),
            )

    def _handle_ai_response_inner(self, data: Any) -> None:
        self.logger.info("🔵 UnifiedAIRouter received ai.response (request_id=%s)", 
                         data.get("request_id") if isinstance(data, dict) else "non-dict")
        if not isinstance(data, dict):
            self.logger.warning("ai.response received non-dict payload, ignoring")
            return

        request_id = data.get("request_id") or "unknown"
        correlation_id = self._ensure_correlation_id(data, request_id)
        now = time.time()

        is_streaming = False

        with self._response_lock:
            # Check if we've already processed this request_id recently
            if request_id in self._seen_response_ids:
                last_seen = self._seen_response_ids[request_id]
                if now - last_seen < self._dedup_window_seconds:
                    self.logger.debug(
                        f"🔇 DEDUP: Skipping duplicate ai.response for {request_id} "
                        f"(seen {now - last_seen:.2f}s ago)"
                    )
                    return

            # Mark this response as seen
            self._seen_response_ids[request_id] = now

            # Clean up old entries to prevent memory leak
            self._cleanup_seen_responses(now)

            # Remove from active requests and get speak flag
            self._active_requests.discard(request_id)
            # Get speak flag deterministically:
            # 1) request-tracked flag
            # 2) ai.response payload
            # 3) source heuristics for voice-originated requests
            should_speak_flag = self._request_speak_flags.pop(request_id, None)
            if should_speak_flag is None:
                payload_speak = data.get("speak", None)
                if payload_speak is None:
                    source_tab = str(data.get("source_tab", "") or "").strip().lower()
                    source_name = str(data.get("source", "") or "").strip().lower()
                    should_speak = source_tab in {"voice", "thoth_ai", "chat"} or "voice" in source_name or "always_on" in source_name
                else:
                    should_speak = bool(payload_speak)
            else:
                should_speak = bool(should_speak_flag)
            if str(request_id).startswith("identity_"):
                self.logger.info(
                    "Identity voice route: should_speak(before)=%s flag=%s payload_speak=%s source_tab=%s source=%s",
                    should_speak,
                    should_speak_flag,
                    data.get("speak", None),
                    data.get("source_tab", None),
                    data.get("source", None),
                )
                should_speak = True

            is_streaming = request_id in self._streaming_requests
            if is_streaming:
                self._streaming_requests.discard(request_id)
                self._seen_delta_seq.pop(request_id, None)
                self._seen_delta_ids.pop(request_id, None)

        # Build unified response payload
        unified_payload = {
            "request_id": request_id,
            "correlation_id": correlation_id,
            "response": data.get("response") or data.get("text") or data.get("message") or "",
            "query": data.get("query") or data.get("prompt") or "",
            "model": data.get("model") or "unknown",
            "sender": data.get("sender") or "Kingdom AI",
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
            "success": data.get("success", True),
            "error": data.get("error"),
            "sentience": data.get("sentience"),
            "domain": data.get("domain"),
            "latency_ms": data.get("latency_ms"),
            "awareness_snapshot": data.get("awareness_snapshot"),
        }

        # Remove None values
        unified_payload = {k: v for k, v in unified_payload.items() if v is not None}

        self.logger.info(
            "📤 UNIFIED: Publishing ai.response.unified for %s (response length: %d)",
            request_id,
            len(str(unified_payload.get("response", ""))),
        )
        self._emit_pipeline_telemetry(
            stage="ai_response_unified",
            request_id=request_id,
            correlation_id=correlation_id,
            extra={
                "is_streaming": is_streaming,
                "response_length": len(str(unified_payload.get("response", ""))),
                "model": unified_payload.get("model"),
                "should_speak": bool(should_speak),
            },
        )
        try:
            # Publish the deduplicated unified response
            self.event_bus.publish("ai.response.unified", unified_payload)
            self.event_bus.publish("learning.response", {
                "request_id": request_id,
                "query": unified_payload.get("query", ""),
                "response": unified_payload.get("response", ""),
                "model": unified_payload.get("model", "unknown"),
                "domain": unified_payload.get("domain"),
                "awareness_snapshot": unified_payload.get("awareness_snapshot"),
                "success": unified_payload.get("success", True),
                "timestamp": unified_payload.get("timestamp"),
            })

            response_text = unified_payload.get("response", "")
            
            self.logger.warning(
                "VOICE_PATH_CHECK: should_speak=%s is_streaming=%s response_text_len=%d request_id=%s",
                should_speak, is_streaming, len(response_text) if response_text else 0, request_id,
            )
            if should_speak:
                if response_text and len(response_text) > 0:
                    source_tab = str(data.get("source_tab", "") or "").strip().lower()
                    source_name = str(data.get("source", "") or "").strip().lower()
                    speech_priority = (
                        "high"
                        if (source_tab == "voice" or source_name == "always_on_voice")
                        else "normal"
                    )
                    self.event_bus.publish("voice.speak", {
                        "text": response_text,
                        "priority": speech_priority,
                        "source": "unified_router",
                        "request_id": request_id,
                    })
                    self.logger.info(f"🔊 Published voice.speak for {request_id} (speak=True, streaming={is_streaming})")
            else:
                self.logger.debug(f"📵 Skipped voice.speak for {request_id} (speak=False)")

            # Store in memory for continuous learning
            try:
                self.event_bus.publish("memory.store", {
                    "type": "chat_history",
                    "data": {
                        "message": response_text,
                        "role": "assistant",
                        "model": unified_payload.get("model"),
                        "request_id": request_id,
                    },
                    "metadata": {
                        "source": "unified_router",
                        "role": "assistant",
                        "request_id": request_id,
                    },
                })
            except Exception as mem_err:
                self.logger.debug(f"Memory store failed (non-critical): {mem_err}")

        except Exception as e:
            self.logger.error(f"❌ Failed to publish ai.response.unified: {e}")

    def _handle_ai_response_delta(self, data: Any) -> None:
        if not isinstance(data, dict):
            self.logger.warning("ai.response.delta received non-dict payload, ignoring")
            return

        request_id = data.get("request_id") or "unknown"
        correlation_id = self._ensure_correlation_id(data, request_id)
        delta_text = data.get("delta") or data.get("text") or ""
        if not delta_text:
            return

        seq = data.get("seq")
        now = time.time()

        with self._response_lock:
            last_seq = self._seen_delta_seq.get(request_id)
            if isinstance(seq, int) and last_seq is not None and seq <= last_seq:
                return
            if isinstance(seq, int):
                self._seen_delta_seq[request_id] = seq
            self._seen_delta_ids[request_id] = now
            self._streaming_requests.add(request_id)
            self._cleanup_seen_deltas(now)

        delta_payload = {
            "request_id": request_id,
            "correlation_id": correlation_id,
            "delta": delta_text,
            "seq": seq,
            "model": data.get("model") or "unknown",
            "sender": data.get("sender") or "Kingdom AI",
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
            "success": data.get("success", True),
        }
        delta_payload = {k: v for k, v in delta_payload.items() if v is not None}

        try:
            self.event_bus.publish("ai.response.delta.unified", delta_payload)
            self._emit_pipeline_telemetry(
                stage="ai_response_delta_unified",
                request_id=request_id,
                correlation_id=correlation_id,
                extra={"delta_length": len(str(delta_text))},
            )
        except Exception as e:
            self.logger.error(f"❌ Failed to publish ai.response.delta.unified: {e}")

        try:
            self.event_bus.publish("voice.speak.delta", {
                "text": delta_text,
                "priority": "normal",
                "source": "unified_router",
                "request_id": request_id,
            })
        except Exception as e:
            self.logger.debug(f"voice.speak.delta publish failed (non-critical): {e}")

    def _cleanup_seen_deltas(self, now: float) -> None:
        cutoff = now - (self._dedup_window_seconds * 2)
        expired = [rid for rid, ts in self._seen_delta_ids.items() if ts < cutoff]
        for rid in expired:
            self._seen_delta_ids.pop(rid, None)
            self._seen_delta_seq.pop(rid, None)
            self._streaming_requests.discard(rid)

    def _cleanup_seen_responses(self, now: float) -> None:
        """Remove old entries from seen responses dict.

        Args:
            now: Current timestamp
        """
        cutoff = now - (self._dedup_window_seconds * 2)
        expired = [rid for rid, ts in self._seen_response_ids.items() if ts < cutoff]
        for rid in expired:
            del self._seen_response_ids[rid]

    # ------------------------------------------------------------------
    # NemoClaw Integration Handlers
    # ------------------------------------------------------------------

    def _handle_nemoclaw_response(self, data: Any) -> None:
        """Track NemoClaw responses and bridge them into the unified pipeline."""
        if not isinstance(data, dict):
            return
        self._nemoclaw_stats["responses_bridged"] = self._nemoclaw_stats.get("responses_bridged", 0) + 1
        request_id = data.get("request_id", "")
        self.logger.info("🐾 NemoClaw response received for %s — bridging to ai.response", request_id)
        if data.get("response") and self.event_bus:
            self.event_bus.publish("ai.response", {
                "request_id": request_id,
                "response": data.get("response", ""),
                "model": "nemoclaw-sandbox",
                "domain": data.get("domain", "general"),
                "backend": "nemoclaw",
                "success": data.get("success", True),
                "timestamp": datetime.utcnow().isoformat(),
            })

    def _handle_nemoclaw_status_update(self, data: Any) -> None:
        """Update local NemoClaw availability flag from bridge events."""
        if not isinstance(data, dict):
            return
        available = data.get("available", False)
        prev = self._nemoclaw_available
        self._nemoclaw_available = available
        if available and not prev:
            self.logger.info("🐾 NemoClaw ACTIVE — dual-backend mode (Ollama + NemoClaw) for all tabs")
        elif not available and prev:
            self.logger.warning("🐾 NemoClaw went offline — Ollama continues, NemoClaw sandbox paused")

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics.

        Returns:
            Dict with router stats
        """
        with self._response_lock:
            return {
                "initialized": self._initialized,
                "active_requests": len(self._active_requests),
                "seen_responses": len(self._seen_response_ids),
                "dedup_window_seconds": self._dedup_window_seconds,
                "nemoclaw_available": self._nemoclaw_available,
                "nemoclaw_stats": dict(self._nemoclaw_stats),
            }


# Global instance for easy access
_unified_router: Optional[UnifiedAIRouter] = None


def get_unified_router() -> Optional[UnifiedAIRouter]:
    """Get the global UnifiedAIRouter instance."""
    return _unified_router


def initialize_unified_router(event_bus: Any) -> UnifiedAIRouter:
    """Initialize and return the global UnifiedAIRouter.

    Args:
        event_bus: The application's event bus

    Returns:
        The initialized UnifiedAIRouter instance
    """
    global _unified_router
    if _unified_router is None:
        _unified_router = UnifiedAIRouter(event_bus)
        _unified_router.initialize()
    return _unified_router
