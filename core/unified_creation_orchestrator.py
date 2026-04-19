#!/usr/bin/env python3
"""
Unified Creation Orchestrator — natural-language entry point for the
Creation Engine tab.

Accepts a plain text request (exactly like the chat widget) and:

  1. Classifies intent via the Ollama brain (primary) with a deterministic
     keyword-scoring fallback using KingdomSystemRegistry.
  2. Selects the best creation capability (or a small ordered set for
     multi-engine pipelines).
  3. Dispatches through the EXISTING creation stack:
        - core.creation_orchestrator.CreationOrchestrator (for multi-engine
          pipelines)
        - direct engine method calls (for single-engine requests)
        - Event bus fan-out (for components that only listen via events)
  4. Emits:
        - creation.request           (what we heard)
        - creation.plan              (what we decided to do)
        - creation.response          (final synthesized answer)
        - creation.progress          (while running)

This is the single entry point for "chat widget in the creation tab".
No creation engine is left out — the registry is the exhaustive catalog.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import urllib.request
import urllib.error
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.kingdom_system_registry import (
    Category,
    Capability,
    KingdomSystemRegistry,
    get_registry,
)

logger = logging.getLogger("KingdomAI.UnifiedCreation")


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CreationPlan:
    request_id: str
    prompt: str
    primary_capability: str                 # registry name
    secondary_capabilities: List[str] = field(default_factory=list)
    action: Optional[str] = None            # preferred method to call
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: str = "keyword"                 # "ollama" | "keyword"
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class CreationOutcome:
    request_id: str
    success: bool
    primary: str
    result: Any
    pipeline_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0


# ──────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────

class UnifiedCreationOrchestrator:
    """Single natural-language entry point for every creation engine."""

    OLLAMA_ROUTE_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "llama3.2:latest"

    def __init__(self,
                 event_bus: Any = None,
                 registry: Optional[KingdomSystemRegistry] = None,
                 ollama_url: Optional[str] = None,
                 ollama_model: Optional[str] = None):
        self.event_bus = event_bus
        self.registry = registry or get_registry(event_bus=event_bus)
        if ollama_url:
            self.OLLAMA_ROUTE_URL = ollama_url
        if ollama_model:
            self.OLLAMA_MODEL = ollama_model
        self._lock = threading.RLock()
        self._history: List[Dict[str, Any]] = []
        # Hard cap on how long the legacy multi-engine pipeline can run per
        # request. Guarantees the GUI never freezes on a stuck engine.
        self._legacy_timeout_s: float = 8.0
        self._subscribe_events()
        logger.info("UnifiedCreationOrchestrator initialized (registry=%d caps)",
                    len(self.registry.all()))

    # ------------------------------------------------------------------ public
    def handle_natural_language(self, prompt: str,
                                attachments: Optional[Dict[str, Any]] = None
                                ) -> CreationOutcome:
        """Synchronous entry point — classify, dispatch, return outcome.

        Every call emits `creation.request` → `creation.plan` →
        `creation.response` on the event bus, even if any stage raises,
        so downstream widgets never drop a request silently.
        """
        start = time.time()
        request_id = uuid.uuid4().hex[:12]
        outcome = CreationOutcome(request_id=request_id, success=False,
                                  primary="", result=None)
        plan: Optional[CreationPlan] = None
        try:
            self._publish("creation.request",
                          {"request_id": request_id, "prompt": prompt,
                           "attachments": attachments or {}})

            try:
                plan = self._plan(prompt, request_id)
            except Exception as e:
                logger.exception("UCO _plan failed for %r", prompt)
                outcome.errors.append(f"plan: {e}")

            if plan is not None:
                self._publish("creation.plan", {
                    "request_id": request_id,
                    "primary": plan.primary_capability,
                    "secondary": plan.secondary_capabilities,
                    "action": plan.action,
                    "source": plan.source,
                    "confidence": plan.confidence,
                    "reasoning": plan.reasoning,
                })
                outcome.primary = plan.primary_capability
                try:
                    outcome = self._execute(plan) or outcome
                except Exception as e:
                    logger.exception("UCO _execute crashed")
                    outcome.errors.append(f"execute: {e}")
        finally:
            outcome.execution_time = time.time() - start
            try:
                self._publish("creation.response", {
                    "request_id": request_id,
                    "success": outcome.success,
                    "primary": outcome.primary,
                    "result": _serialize(outcome.result),
                    "errors": outcome.errors,
                    "execution_time_s": outcome.execution_time,
                })
            except Exception:
                logger.exception("UCO failed to publish creation.response")
            try:
                with self._lock:
                    self._history.append({
                        "request_id": request_id,
                        "prompt": prompt,
                        "plan": plan.__dict__ if plan else None,
                        "success": outcome.success,
                        "time_s": outcome.execution_time,
                    })
                    if len(self._history) > 200:
                        self._history = self._history[-200:]
            except Exception:
                pass
        return outcome

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def _caps_set(self) -> set:
        return {c.name for c in self.registry.all()}

    # ------------------------------------------------------------------ planning
    def _plan(self, prompt: str, request_id: str) -> CreationPlan:
        # Primary: ask Ollama brain (if reachable) to choose the capability.
        ollama_choice = self._ollama_classify(prompt)
        if ollama_choice:
            return CreationPlan(
                request_id=request_id,
                prompt=prompt,
                primary_capability=ollama_choice["primary"],
                secondary_capabilities=ollama_choice.get("secondary", []),
                action=ollama_choice.get("action"),
                parameters=ollama_choice.get("parameters", {}),
                source="ollama",
                confidence=float(ollama_choice.get("confidence", 0.8)),
                reasoning=ollama_choice.get("reasoning", ""),
            )

        # Fallback: deterministic keyword scoring over creation-relevant caps.
        candidates = self.registry.search(prompt)
        # Restrict to categories that actually "create"
        creative_cats = {
            Category.CREATION, Category.ENGINEERING, Category.SCIENCE,
            Category.MEDIA,
        }
        filtered = [c for c in candidates if c.category in creative_cats]

        # Boost for direct name/trigger hits: if the prompt mentions a
        # category-distinctive word (e.g. "pcb", "alloy", "blueprint",
        # "schematic", "storyboard"), that cap should win decisively.
        pl = prompt.lower()
        decisive = {
            "pcb": "electronics_circuit", "gerber": "electronics_circuit",
            "alloy": "metallurgy", "metallurgy": "metallurgy",
            "blueprint": "blueprint_engine",
            "storyboard": "storyboard",
            "cinema": "cinema_engine", "cinematic": "cinema_engine",
            "stl": "cad_mechanical", "gcode": "cad_mechanical",
            "floor plan": "architectural_design",
            "architectural": "architectural_design",
            "architecture": "architectural_design",
            "hz": "audio_synthesis", "sine wave": "audio_synthesis",
            "tone": "audio_synthesis",
            "dna": "biological_system", "enzyme": "biological_system",
            "exploded": "exploded_view",
            "garment": "fashion_clothing", "dress": "fashion_clothing",
        }
        for kw, target in decisive.items():
            if kw in pl and target in self._caps_set():
                # Promote the decisive candidate to the front
                filtered = ([self.registry.get(target)]
                            + [c for c in filtered if c.name != target])
                break

        if not filtered:
            # Route anything unresolved to the visual canvas (it handles
            # free-form prompts including "draw me a sunset").
            return CreationPlan(
                request_id=request_id,
                prompt=prompt,
                primary_capability="visual_creation_canvas",
                source="keyword",
                confidence=0.25,
                reasoning="no keyword match; defaulting to visual canvas",
            )

        primary = filtered[0]
        secondaries = [c.name for c in filtered[1:4]]
        return CreationPlan(
            request_id=request_id,
            prompt=prompt,
            primary_capability=primary.name,
            secondary_capabilities=secondaries,
            action=primary.actions[0] if primary.actions else None,
            source="keyword",
            confidence=0.6 if len(secondaries) else 0.75,
            reasoning=f"keyword-scored top match: {primary.name}",
        )

    # ------------------------------------------------------------------ execution
    def _execute(self, plan: CreationPlan) -> CreationOutcome:
        outcome = CreationOutcome(
            request_id=plan.request_id,
            success=False,
            primary=plan.primary_capability,
            result=None,
        )
        cap = self.registry.get(plan.primary_capability)
        if cap is None:
            outcome.errors.append(f"unknown capability {plan.primary_capability!r}")
            return outcome

        self._publish("creation.progress",
                      {"request_id": plan.request_id, "stage": "dispatch",
                       "capability": cap.name})

        # Strategy 1 — call live instance method if we have one
        if cap.instance is not None and plan.action and hasattr(cap.instance, plan.action):
            try:
                fn = getattr(cap.instance, plan.action)
                kwargs = dict(plan.parameters or {})
                if "prompt" not in kwargs and "text" not in kwargs:
                    kwargs["prompt"] = plan.prompt
                result = _call_maybe_async(fn, kwargs)
                outcome.result = result
                outcome.success = True
                outcome.pipeline_results[cap.name] = _serialize(result)
                return outcome
            except Exception as e:
                logger.exception("Direct invocation of %s.%s failed",
                                 cap.name, plan.action)
                outcome.errors.append(f"{cap.name}.{plan.action}: {e}")

        # Strategy 2 — dispatch via existing CreationOrchestrator (multi-engine)
        # Run inside a daemon thread with a hard timeout. If the thread has
        # not completed by the deadline we abandon it (daemon=True) so the
        # studio/test/GUI never freezes on a blocking engine.
        try:
            from core.creation_orchestrator import get_orchestrator
            legacy = get_orchestrator(event_bus=self.event_bus)

            container: Dict[str, Any] = {"done": False, "result": None,
                                         "err": None}

            def _run_legacy():
                try:
                    pipeline = legacy.parse_request(plan.prompt)
                    container["result"] = _run_async(
                        legacy.execute_pipeline(pipeline))
                except Exception as e:
                    container["err"] = e
                finally:
                    container["done"] = True

            t = threading.Thread(target=_run_legacy, daemon=True,
                                 name="UCOLegacyExec")
            t.start()
            t.join(timeout=self._legacy_timeout_s)

            if container["done"]:
                if container["err"] is not None:
                    outcome.errors.append(
                        f"creation_orchestrator: {container['err']}")
                else:
                    result = container["result"]
                    outcome.result = _serialize(result)
                    outcome.success = bool(getattr(result, "success", True))
                    outcome.pipeline_results["creation_orchestrator"] = \
                        _serialize(result)
                    return outcome
            else:
                # Daemon thread keeps running — abandon it, mark routing-ok.
                outcome.errors.append(
                    f"creation_orchestrator: still running after "
                    f"{self._legacy_timeout_s}s; detached")
                outcome.success = True
                outcome.result = {
                    "status": "routing_ok_detached",
                    "capability": cap.name,
                    "note": ("legacy multi-engine pipeline continues in "
                             "background; primary routing is confirmed"),
                }
                return outcome
        except Exception as e:
            logger.debug("Legacy orchestrator dispatch failed: %s", e)
            outcome.errors.append(f"creation_orchestrator: {e}")

        # Strategy 3 — raw event bus broadcast using capability's input topic.
        if self.event_bus is not None and cap.event_topics_in:
            topic = cap.event_topics_in[0]
            try:
                payload = {"request_id": plan.request_id,
                           "prompt": plan.prompt,
                           **(plan.parameters or {})}
                self.event_bus.publish(topic, payload)
                outcome.success = True
                outcome.result = {"dispatched_via_bus": topic,
                                  "capability": cap.name}
                return outcome
            except Exception as e:
                outcome.errors.append(f"bus publish {topic}: {e}")

        outcome.errors.append("no executable path for capability")
        return outcome

    # ------------------------------------------------------------------ ollama
    def _ollama_classify(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Ask the local Ollama brain to pick a capability.

        Returns None if Ollama is unreachable or reply is unparseable.
        """
        try:
            catalog = [
                {"name": c.name,
                 "description": c.description,
                 "triggers": c.triggers[:6],
                 "actions": c.actions[:4]}
                for c in self.registry.all()
                if c.category in (Category.CREATION, Category.ENGINEERING,
                                  Category.SCIENCE, Category.MEDIA)
            ]
            system = (
                "You are the Kingdom AI creation-router. Choose the single "
                "best capability for the user's request from the provided "
                "catalog. Reply with ONLY compact JSON (no prose) of shape:\n"
                '{"primary": "<name>", "secondary": ["..."], '
                '"action": "<method>", "parameters": {}, "confidence": 0.0-1.0, '
                '"reasoning": "..."}'
            )
            user = f"USER REQUEST:\n{prompt}\n\nCATALOG:\n{json.dumps(catalog)}"
            body = json.dumps({
                "model": self.OLLAMA_MODEL,
                "prompt": f"{system}\n\n{user}",
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 256},
            }).encode("utf-8")
            req = urllib.request.Request(
                self.OLLAMA_ROUTE_URL, data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            text = data.get("response") or data.get("message", {}).get("content", "")
            parsed = _extract_json(text)
            if not parsed or "primary" not in parsed:
                return None
            if parsed["primary"] not in {c.name for c in self.registry.all()}:
                return None
            return parsed
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                OSError, json.JSONDecodeError):
            return None
        except Exception as e:
            logger.debug("ollama classify unexpected error: %s", e)
            return None

    # ------------------------------------------------------------------ events
    def _subscribe_events(self) -> None:
        if self.event_bus is None:
            return
        try:
            self.event_bus.subscribe("creation.natural_language",
                                     self._on_natural_language_event)
            self.event_bus.subscribe("creation.chat", self._on_natural_language_event)
        except Exception as e:
            logger.debug("subscribe failed: %s", e)

    def _on_natural_language_event(self, data: Any) -> None:
        if isinstance(data, dict):
            prompt = data.get("prompt") or data.get("text") or ""
            self.handle_natural_language(prompt, data.get("attachments"))

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        try:
            self.event_bus.publish(topic, payload)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _call_maybe_async(fn: Callable, kwargs: Dict[str, Any]):
    try:
        result = fn(**kwargs)
    except TypeError:
        # The method doesn't accept prompt= or other kwargs -- retry positional
        vals = list(kwargs.values())
        result = fn(*vals)
    if asyncio.iscoroutine(result):
        return _run_async(result)
    return result


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    # Fast path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find the first { ... } block
    try:
        start = text.index("{")
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
    except (ValueError, json.JSONDecodeError):
        pass
    return None


def _serialize(obj: Any) -> Any:
    """Best-effort JSON-serialisable view of an arbitrary object."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        try:
            return {k: _serialize(v) for k, v in vars(obj).items()
                    if not k.startswith("_")}
        except Exception:
            pass
    try:
        return str(obj)
    except Exception:
        return repr(obj)


# ──────────────────────────────────────────────────────────────────────
# Singleton accessor
# ──────────────────────────────────────────────────────────────────────

_GLOBAL: Optional[UnifiedCreationOrchestrator] = None
_LOCK = threading.RLock()


def get_unified_creation_orchestrator(event_bus: Any = None
                                      ) -> UnifiedCreationOrchestrator:
    global _GLOBAL
    with _LOCK:
        if _GLOBAL is None:
            _GLOBAL = UnifiedCreationOrchestrator(event_bus=event_bus)
        elif event_bus is not None and _GLOBAL.event_bus is None:
            _GLOBAL.event_bus = event_bus
        return _GLOBAL
