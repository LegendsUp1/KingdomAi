"""Kingdom AI — UnifiedBrainRouter.

Single brain path that fuses DictionaryBrain, MemPalace, LanguageLearningHub,
HarmonicOrchestratorV3, NeuroprotectionLayer, and the always-on
KingdomInferenceStack into one coherent ``ask()`` call. The goal is that
every Kingdom AI tab, tool, or consumer launcher speaks to *one* entry
point instead of stitching together five cooperating-but-separate
subsystems.

Pipeline (per request):

1. **Neuroprotection pre-check.** If a NeuroprotectionLayer is wired we
   run the inbound text through its validator. Refusals short-circuit
   the whole chain.
2. **Dictionary enrichment.** Multi-era definitions + etymology are
   prepended to the prompt via
   :meth:`DictionaryBrain.enrich_prompt_for_ollama`. Optional; skipped
   quietly if the brain isn't wired.
3. **MemPalace recall.** The raw prompt is searched against the shared
   vector store (via :class:`MemPalaceBridge`). Up to ``top_k`` hits get
   spliced into the system message so the model sees prior context.
4. **Language hub context.** If the caller supplies ``source_lang`` /
   ``target_lang`` the hub's translation layer is consulted and attached
   as a separate context block.
5. **Inference stack generation.** The enriched prompt goes to
   :meth:`KingdomInferenceStack.generate` with the per-component model
   routing. Backend is recorded in the trace.
6. **Writeback.** The final ``{prompt, answer}`` pair is stored through
   the MemPalace bridge and — optionally — fired through the harmonic
   orchestrator so downstream learning hooks see it.

The router is safe to construct with **any** subset of collaborators; it
skips missing stages transparently. That's intentional: consumer desktop
and creator desktop share this class, as does the mobile light tier which
will receive it with only ``inference_stack`` wired in.

Consumer role (``KINGDOM_APP_MODE=consumer``) is respected automatically
— it never gates dependencies (that's the PLATFORM axis) but it *does*
get injected into the system prompt as a persona note so tool results
stay scoped.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.unified_brain_router")


def _event_names() -> Dict[str, str]:
    """Lazy-import the event-name constants so this module stays cheap to import."""
    try:
        from core.kingdom_event_names import (
            BRAIN_ASK_REQUEST,
            BRAIN_ASK_RESULT,
            BRAIN_WRITEBACK,
            BRAIN_TOOL_CALL,
            BRAIN_TOOL_RESULT,
        )
    except Exception:
        BRAIN_ASK_REQUEST = "brain.ask.request"
        BRAIN_ASK_RESULT = "brain.ask.result"
        BRAIN_WRITEBACK = "brain.writeback"
        BRAIN_TOOL_CALL = "brain.tool.call"
        BRAIN_TOOL_RESULT = "brain.tool.result"
    return {
        "ask_req": BRAIN_ASK_REQUEST,
        "ask_res": BRAIN_ASK_RESULT,
        "writeback": BRAIN_WRITEBACK,
        "tool_call": BRAIN_TOOL_CALL,
        "tool_res": BRAIN_TOOL_RESULT,
    }


class UnifiedBrainRouter:
    """Single-entry brain path shared by creator desktop and consumer desktop.

    Parameters mirror the subsystem instances that the bootstrap already
    constructs. None of them are required — the router degrades gracefully
    stage-by-stage. This matters because:

    * The mobile light tier (KINGDOM_APP_PLATFORM=mobile) constructs the
      router with only ``inference_stack``.
    * Headless services (e.g. the consumer secure-protection loop that
      doesn't need MemPalace) can wire a strict subset.

    Thread-safe: the writeback bookkeeping lives behind ``self._lock``.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        event_bus: Any = None,
        *,
        inference_stack: Any = None,
        dictionary_brain: Any = None,
        ollama_memory_integration: Any = None,
        mempalace_bridge: Any = None,
        language_hub: Any = None,
        harmonic_orchestrator: Any = None,
        neuroprotection: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.event_bus = event_bus
        self.inference_stack = inference_stack
        self.dictionary_brain = dictionary_brain
        self.ollama = ollama_memory_integration
        self.mempalace_bridge = mempalace_bridge
        self.language_hub = language_hub
        self.orchestrator = harmonic_orchestrator
        self.neuroprotection = neuroprotection
        self.config: Dict[str, Any] = dict(config or {})
        self._lock = threading.RLock()

        self._role = (os.environ.get("KINGDOM_APP_MODE", "creator")
                      .strip().lower() or "creator")
        self._platform = (os.environ.get("KINGDOM_APP_PLATFORM", "desktop")
                          .strip().lower() or "desktop")

        # Telemetry
        self._ask_total = 0
        self._recall_hits_total = 0
        self._writeback_total = 0
        self._refusals_total = 0

        # Tool registry — populated via :meth:`register_tool`. DictionaryBrain
        # and MemPalace auto-register themselves below when available.
        self._tools: Dict[str, Callable[..., Any]] = {}
        self._auto_register_builtin_tools()

        if event_bus is not None:
            try:
                ev = _event_names()
                event_bus.subscribe(ev["ask_req"], self._on_ask_request)
                event_bus.subscribe(ev["tool_call"], self._on_tool_call)
            except Exception as exc:
                logger.debug("event-bus subscribe skipped: %s", exc)

        logger.info(
            "UnifiedBrainRouter v%s ready — role=%s platform=%s "
            "stack=%s dict=%s mempalace=%s omi=%s lang=%s orchestrator=%s neuro=%s",
            self.VERSION, self._role, self._platform,
            inference_stack is not None, dictionary_brain is not None,
            mempalace_bridge is not None, ollama_memory_integration is not None,
            language_hub is not None, harmonic_orchestrator is not None,
            neuroprotection is not None,
        )

    # ── Public API ────────────────────────────────────────────────────────

    def ask(
        self,
        prompt: str,
        *,
        component: str = "main_brain",
        temperature: float = 0.6,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        top_k_memory: int = 3,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        store_result: bool = True,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run *prompt* through the full unified brain pipeline.

        Returns a dict with:
        ``prompt``, ``enriched_prompt``, ``answer``, ``backend``,
        ``trace`` (per-stage dict), ``request_id``.
        """
        rid = request_id or uuid.uuid4().hex[:12]
        trace: Dict[str, Any] = {
            "request_id": rid,
            "started_at": time.time(),
            "role": self._role,
            "platform": self._platform,
            "stages": [],
        }
        with self._lock:
            self._ask_total += 1

        if not prompt:
            return {
                "prompt": prompt, "enriched_prompt": "", "answer": "",
                "backend": None, "trace": trace, "request_id": rid,
            }

        # Stage 1 — neuroprotection
        allowed, reason = self._neuroprotect(prompt)
        trace["stages"].append({"name": "neuroprotection",
                                "allowed": allowed, "reason": reason})
        if not allowed:
            with self._lock:
                self._refusals_total += 1
            return {
                "prompt": prompt, "enriched_prompt": prompt, "answer": "",
                "backend": "refused",
                "refused": True, "refusal_reason": reason,
                "trace": trace, "request_id": rid,
            }

        # Stage 2 — dictionary enrichment
        enriched = self._dictionary_enrich(prompt)
        trace["stages"].append({"name": "dictionary_enrichment",
                                "delta_chars": len(enriched) - len(prompt)})

        # Stage 3 — mempalace recall
        recall_blocks = self._mempalace_recall(prompt, top_k=top_k_memory)
        trace["stages"].append({"name": "mempalace_recall",
                                "hits": len(recall_blocks)})
        if recall_blocks:
            with self._lock:
                self._recall_hits_total += len(recall_blocks)
            lines = ["", "Relevant prior memory:"]
            for r in recall_blocks:
                lines.append(f"- {r}")
            enriched = enriched + "\n".join(lines)

        # Stage 4 — language translation context
        if source_lang and target_lang and self.language_hub is not None:
            try:
                tr = self.language_hub.translate(prompt, source_lang, target_lang)
                if isinstance(tr, dict) and tr.get("translation"):
                    enriched = (
                        f"{enriched}\n\n"
                        f"[translation {source_lang}→{target_lang}] "
                        f"{tr['translation']}"
                    )
                trace["stages"].append({"name": "language_hub",
                                        "source": source_lang,
                                        "target": target_lang})
            except Exception as exc:
                trace["stages"].append({"name": "language_hub",
                                        "error": str(exc)[:80]})

        # Stage 5 — persona note (role-aware, *not* tier-aware)
        persona = self._persona_system()
        effective_system = (
            f"{persona}\n\n{system}" if system else persona
        ) if persona else system

        # Stage 6 — inference
        answer, backend = self._generate(
            enriched,
            component=component,
            temperature=temperature,
            max_tokens=max_tokens,
            system=effective_system,
        )
        trace["stages"].append({"name": "inference",
                                "backend": backend,
                                "chars": len(answer)})

        # Stage 7 — writeback
        if store_result and answer:
            self._writeback(prompt, answer, rid)
            trace["stages"].append({"name": "writeback", "stored": True})

        trace["finished_at"] = time.time()
        result = {
            "prompt": prompt,
            "enriched_prompt": enriched,
            "answer": answer,
            "backend": backend,
            "trace": trace,
            "request_id": rid,
        }

        if self.event_bus is not None:
            try:
                ev = _event_names()
                self.event_bus.publish(ev["ask_res"], result)
            except Exception:
                pass
        return result

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "version": self.VERSION,
                "role": self._role,
                "platform": self._platform,
                "stages_live": {
                    "neuroprotection": self.neuroprotection is not None,
                    "dictionary_brain": self.dictionary_brain is not None,
                    "mempalace_bridge": self.mempalace_bridge is not None,
                    "language_hub": self.language_hub is not None,
                    "orchestrator": self.orchestrator is not None,
                    "inference_stack": self.inference_stack is not None,
                    "ollama_memory_integration": self.ollama is not None,
                },
                "tools": sorted(self._tools.keys()),
                "telemetry": {
                    "ask_total": self._ask_total,
                    "recall_hits_total": self._recall_hits_total,
                    "writeback_total": self._writeback_total,
                    "refusals_total": self._refusals_total,
                },
            }

    # ── Tool registry ─────────────────────────────────────────────────────

    def register_tool(self, name: str, fn: Callable[..., Any]) -> None:
        """Expose ``fn`` under ``name`` so tabs + the LLM can call it."""
        if not callable(fn):
            raise TypeError(f"tool {name!r} must be callable")
        with self._lock:
            self._tools[str(name)] = fn

    def call_tool(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        fn = self._tools.get(name)
        if fn is None:
            return {"ok": False, "error": f"unknown tool: {name}"}
        try:
            out = fn(**kwargs)
            return {"ok": True, "tool": name, "result": out}
        except Exception as exc:
            return {"ok": False, "tool": name, "error": str(exc)}

    def _auto_register_builtin_tools(self) -> None:
        """Register Dictionary + MemPalace tool surfaces automatically."""
        if self.dictionary_brain is not None:
            db = self.dictionary_brain
            if hasattr(db, "get_definition"):
                self.register_tool(
                    "dictionary.define",
                    lambda word, source="auto": db.get_definition(word, source),
                )
            if hasattr(db, "get_etymology"):
                self.register_tool(
                    "dictionary.trace_etymology",
                    lambda word: db.get_etymology(word),
                )
            if hasattr(db, "evaluate_context"):
                self.register_tool(
                    "dictionary.compare_eras",
                    lambda sentence, target_word=None: db.evaluate_context(
                        sentence, target_word
                    ),
                )
            if hasattr(db, "semantic_search"):
                self.register_tool(
                    "dictionary.semantic_search",
                    lambda query, top_k=5: db.semantic_search(query, top_k),
                )
        if self.mempalace_bridge is not None:
            mb = self.mempalace_bridge
            if hasattr(mb, "read_memory"):
                self.register_tool(
                    "memory.recall",
                    lambda query, top_k=5: mb.read_memory(query, top_k),
                )
            if hasattr(mb, "write_memory"):
                self.register_tool(
                    "memory.store",
                    lambda key, value: mb.write_memory(key, value),
                )

    # ── Stage helpers ─────────────────────────────────────────────────────

    def _neuroprotect(self, prompt: str) -> tuple[bool, str]:
        if self.neuroprotection is None:
            return True, ""
        try:
            if hasattr(self.neuroprotection, "validate_input"):
                verdict = self.neuroprotection.validate_input(prompt)
                if isinstance(verdict, dict):
                    allowed = bool(verdict.get("allowed", True))
                    reason = str(verdict.get("reason", ""))
                    return allowed, reason
                if isinstance(verdict, bool):
                    return verdict, ("" if verdict else "neuroprotection refused")
            # Unknown shape — let it through but flag it in the trace.
            return True, "neuroprotection: unknown interface"
        except Exception as exc:
            return True, f"neuroprotection-error:{exc}"

    def _dictionary_enrich(self, prompt: str) -> str:
        if self.dictionary_brain is None:
            return prompt
        try:
            if hasattr(self.dictionary_brain, "enrich_prompt_for_ollama"):
                return self.dictionary_brain.enrich_prompt_for_ollama(prompt)
        except Exception as exc:
            logger.debug("dictionary enrich failed: %s", exc)
        return prompt

    def _mempalace_recall(self, prompt: str, top_k: int = 3) -> List[str]:
        if self.mempalace_bridge is None:
            return []
        try:
            hits = self.mempalace_bridge.read_memory(prompt, top_k=top_k)
        except Exception as exc:
            logger.debug("mempalace recall failed: %s", exc)
            return []
        if not hits:
            return []
        out: List[str] = []
        for h in hits if isinstance(hits, list) else []:
            if isinstance(h, dict):
                txt = h.get("value") or h.get("memory") or h.get("text") or ""
            else:
                txt = str(h)
            txt = str(txt).strip()
            if txt:
                out.append(txt[:240])
        return out[:top_k]

    def _persona_system(self) -> Optional[str]:
        """Build a short role-aware system prefix.

        Role (``creator``/``consumer``) drives which secrets/data-access
        flags the model is allowed to acknowledge. We never stuff actual
        secrets into the prompt — this is purely a scoping hint.
        """
        if self._role == "consumer":
            return (
                "You are Kingdom AI running in consumer mode. You do not "
                "have access to the operator's private keys, wallet "
                "addresses, or proprietary data. Respond as the user's own "
                "local assistant."
            )
        return None

    def _generate(
        self,
        enriched_prompt: str,
        *,
        component: str,
        temperature: float,
        max_tokens: int,
        system: Optional[str],
    ) -> tuple[str, Optional[str]]:
        if self.inference_stack is None:
            return (
                "[unified-brain] inference stack not wired — returning "
                "enriched prompt only.",
                None,
            )
        try:
            out = self.inference_stack.generate(
                enriched_prompt,
                component=component,
                temperature=temperature,
                max_tokens=max_tokens,
                system=system,
            )
            backend = getattr(self.inference_stack, "_active_gen_backend", None)
            return (str(out or ""), backend)
        except Exception as exc:
            logger.debug("unified generate failed: %s", exc)
            return (f"[unified-brain] generate error: {exc}", None)

    def _writeback(self, prompt: str, answer: str, rid: str) -> None:
        with self._lock:
            self._writeback_total += 1
        # MemPalace write — best effort
        if self.mempalace_bridge is not None:
            try:
                self.mempalace_bridge.write_memory(
                    key=f"brain.qa.{rid}",
                    value=f"Q: {prompt}\nA: {answer}",
                )
            except Exception as exc:
                logger.debug("mempalace writeback failed: %s", exc)
        # Event broadcast
        if self.event_bus is not None:
            try:
                ev = _event_names()
                self.event_bus.publish(ev["writeback"], {
                    "request_id": rid,
                    "prompt": prompt,
                    "answer": answer,
                    "timestamp": time.time(),
                })
            except Exception:
                pass

    # ── Event handlers ────────────────────────────────────────────────────

    def _on_ask_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        prompt = str(data.get("prompt") or "")
        if not prompt:
            return
        self.ask(
            prompt,
            component=str(data.get("component") or "main_brain"),
            temperature=float(data.get("temperature", 0.6)),
            max_tokens=int(data.get("max_tokens", 1024)),
            system=data.get("system"),
            top_k_memory=int(data.get("top_k_memory", 3)),
            source_lang=data.get("source_lang"),
            target_lang=data.get("target_lang"),
            store_result=bool(data.get("store_result", True)),
            request_id=data.get("request_id"),
        )

    def _on_tool_call(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        name = str(data.get("tool") or "")
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        result = self.call_tool(name, **args)
        if self.event_bus is not None:
            try:
                ev = _event_names()
                self.event_bus.publish(ev["tool_res"], {
                    "tool": name,
                    "request_id": data.get("request_id"),
                    **result,
                })
            except Exception:
                pass


# ── Process-wide lazy singleton ────────────────────────────────────────────

_SINGLETON_LOCK = threading.Lock()
_SINGLETON: Optional[UnifiedBrainRouter] = None


def get_unified_brain_router(
    event_bus: Any = None, **kwargs: Any
) -> UnifiedBrainRouter:
    """Return the lazily-constructed process-wide router.

    Subsequent calls reuse the first instance; providing an ``event_bus``
    on a later call attaches it retroactively if the first caller didn't
    have one.
    """
    global _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is None:
            _SINGLETON = UnifiedBrainRouter(event_bus=event_bus, **kwargs)
        elif event_bus is not None and _SINGLETON.event_bus is None:
            _SINGLETON.event_bus = event_bus
            try:
                ev = _event_names()
                event_bus.subscribe(ev["ask_req"], _SINGLETON._on_ask_request)
                event_bus.subscribe(ev["tool_call"], _SINGLETON._on_tool_call)
            except Exception:
                pass
    return _SINGLETON


def reset_unified_brain_router() -> None:
    """Clear the cached singleton — intended for tests only."""
    global _SINGLETON
    with _SINGLETON_LOCK:
        _SINGLETON = None


__all__ = [
    "UnifiedBrainRouter",
    "get_unified_brain_router",
    "reset_unified_brain_router",
]
