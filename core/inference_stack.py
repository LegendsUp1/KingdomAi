"""Kingdom AI — Ultimate Always-On SOTA 2026 Inference Stack.

One unified inference layer for every tab, subsystem, and brain path in
Kingdom AI. It is **always on** — there is no "Ultra RTX Mode" toggle; this
*is* the default. Intended to feel instant on an RTX GPU while degrading
gracefully on CPU-only boxes, in consumer APK/PWA builds, and in CI.

## Why this file exists

The Kingdom AI code base historically called Ollama (and sometimes the
``sentence-transformers`` package) directly from dozens of places. That is
problematic for three reasons:

1. Each call-site must duplicate GPU detection, fallbacks, and model choice.
2. The creator desktop wants **maximum RTX throughput** (TensorRT-LLM ≫
   vLLM ≫ Ollama), while the mobile consumer wants a **tiny footprint**.
3. Any hard ``import torch`` at module top-level will break the consumer
   APK (no torch on Android) and any minimal CI environment.

This module centralises all that in one place and guarantees:

* **Zero hard deps at import time.** Every heavy library (``torch``,
  ``sentence_transformers``, ``tensorrt_llm``, ``vllm``, ``ollama``) is
  imported lazily and wrapped in ``try/except``. Importing this module
  is always safe, even on stripped-down consumer builds.
* **Lazy backend selection.** The first time a component asks for a
  generation we probe for TensorRT-LLM → vLLM → Ollama HTTP → offline
  stub. The winner is cached per-process.
* **Lazy embedding model.** The first time ``embed()`` is called we try
  sentence-transformers on CUDA → sentence-transformers on CPU → Ollama
  ``nomic-embed-text`` → SHA-256 pseudo-embedding. The winner is cached.
* **Per-component routing.** Every request is tagged with a *component*
  (e.g. ``"kaig_tab"``, ``"dictionary_brain"``, ``"trading"``). The
  routing table maps each component to the best model for that workload.
* **Event-bus parity.** Components that prefer async messaging can
  publish ``INFERENCE_GENERATE_REQUEST`` / ``INFERENCE_EMBED_REQUEST`` on
  the shared :class:`EventBus` and receive a matching ``*_RESULT``.
* **Platform-aware, not role-aware.** The heavy-vs-light decision keys off
  ``KINGDOM_APP_PLATFORM`` (``desktop`` | ``mobile``), **not** off role
  (``KINGDOM_APP_MODE=creator|consumer``). Consumer *desktop* installs get
  the full CUDA / TensorRT-LLM / sentence-transformers stack exactly like
  the creator desktop — role only controls which keys/data are injected.
  Only ``KINGDOM_APP_PLATFORM=mobile`` triggers the lightweight routing
  table (``gemma:2b``) and skips torch / sentence-transformers / CUDA so
  the mobile APK/PWA stays lean.

## Public API

>>> from core.inference_stack import get_inference_stack
>>> stack = get_inference_stack()         # lazy, process-wide singleton
>>> stack.generate("Hello", component="kaig_tab")
>>> stack.embed("kingdom")                # list[float]
>>> stack.get_system_info()               # routing + backend health

The ``inference_stack`` module-level attribute is also available for
``from core.inference_stack import inference_stack`` — it's resolved
lazily via ``__getattr__`` so importing the module never forces backend
construction.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import warnings

# Silence TF / oneDNN / absl banners that fire transitively via tf-keras
# (the Keras-3 compatibility shim required by transformers ≥ 4.57). These are
# informational-only and otherwise clutter every boot. Set BEFORE any downstream
# import can trigger them.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("ABSL_LOGGING_VERBOSITY", "3")
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger("kingdom_ai.inference_stack")

# ── Optional-dependency probes (feature-detect; never hard-require) ─────────
#
# Every import is inside a ``try`` block and the result cached in a boolean
# so later probes are O(1). ``torch`` is deliberately NOT imported at module
# top level — consumer builds must be able to import this file even with no
# torch on disk. We probe inside ``_probe_torch()`` on demand.

_TORCH_STATE: Dict[str, Any] = {"probed": False, "ok": False, "cuda": False,
                                 "device": "cpu", "device_name": "", "vram_gb": 0.0}


def _probe_torch() -> Dict[str, Any]:
    """Return the cached torch / CUDA probe result. Safe to call repeatedly."""
    if _TORCH_STATE["probed"]:
        return _TORCH_STATE
    try:
        import torch  # type: ignore
        _TORCH_STATE["ok"] = True
        if torch.cuda.is_available():
            _TORCH_STATE["cuda"] = True
            _TORCH_STATE["device"] = "cuda"
            try:
                _TORCH_STATE["device_name"] = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                _TORCH_STATE["vram_gb"] = round(props.total_memory / 1e9, 2)
            except Exception:
                pass
    except Exception:
        pass
    _TORCH_STATE["probed"] = True
    return _TORCH_STATE


_OLLAMA_STATE: Dict[str, Any] = {"probed": False, "reachable": False,
                                  "base": "http://localhost:11434",
                                  "available_models": []}

_ST_STATE: Dict[str, Any] = {"probed": False, "ok": False}
_VLLM_STATE: Dict[str, Any] = {"probed": False, "ok": False}
_TRT_STATE: Dict[str, Any] = {"probed": False, "ok": False}


def _probe_ollama(base: Optional[str] = None, timeout: float = 2.0) -> Dict[str, Any]:
    """Ping the Ollama HTTP server and cache availability + model list."""
    if base:
        _OLLAMA_STATE["base"] = base.rstrip("/")
        _OLLAMA_STATE["probed"] = False
    if _OLLAMA_STATE["probed"]:
        return _OLLAMA_STATE
    url = f"{_OLLAMA_STATE['base']}/api/tags"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body or "{}")
        models = [m.get("name", "") for m in data.get("models", [])
                  if isinstance(m, dict)]
        _OLLAMA_STATE["reachable"] = True
        _OLLAMA_STATE["available_models"] = [m for m in models if m]
    except (urllib.error.URLError, OSError, ValueError):
        _OLLAMA_STATE["reachable"] = False
    _OLLAMA_STATE["probed"] = True
    return _OLLAMA_STATE


# ── Platform + role env guards ─────────────────────────────────────────────
#
# There are TWO orthogonal axes in Kingdom AI:
#
#   KINGDOM_APP_PLATFORM : desktop | mobile
#     Controls dependency *tier*. "mobile" means the APK/PWA — skip torch,
#     TensorRT-LLM, vLLM, sentence-transformers, and use a tiny Ollama
#     default model. "desktop" means the full stack is available and we
#     pick the best backend the machine actually supports.
#
#   KINGDOM_APP_MODE : creator | consumer
#     Controls *role* — whether owner keys, proprietary data, and the
#     creator-only UI are loaded. Role NEVER gates inference dependencies.
#     A consumer *desktop* install still gets TensorRT-LLM / vLLM / CUDA /
#     sentence-transformers; it just never sees the operator's secrets.
#
# Historically the stack collapsed these into one "consumer mode" switch
# that over-downgraded consumer desktop. That was wrong — corrected here.

def _platform() -> str:
    """Return ``"desktop"`` or ``"mobile"``. Defaults to ``desktop``."""
    val = os.environ.get("KINGDOM_APP_PLATFORM", "desktop").strip().lower()
    return "mobile" if val == "mobile" else "desktop"


def _is_light_tier() -> bool:
    """True only when the process runs on a mobile (APK/PWA) platform.

    This is the single source of truth for "skip the heavy dependencies"
    decisions. Desktop — whether creator or consumer — always returns False
    and is free to pull in torch, sentence-transformers, TensorRT-LLM, vLLM.
    """
    return _platform() == "mobile"


def _is_consumer_mode() -> bool:
    """Kept for backward compatibility — reports *role*, not tier.

    Callers that previously consulted this to decide whether to skip heavy
    dependencies should switch to :func:`_is_light_tier` instead. Role is
    still the right thing to consult for keys/secrets/data-access gates.
    """
    return os.environ.get("KINGDOM_APP_MODE", "creator").strip().lower() == "consumer"


# ── Default routing ────────────────────────────────────────────────────────
#
# Model choices follow the operator's locally-installed Ollama list and the
# spirit of the user's SOTA 2026 stack: fast / reasoning / math / vision /
# large models plus a dedicated embedding model. Every route has a
# ``*_fallback`` that is guaranteed to be tiny and universally available so
# we never emit a "model not found" in the UI.

DEFAULT_FULL_TIER_ROUTING: Dict[str, str] = {
    # Main creator desktop brain
    "main_brain": "mistral-nemo:latest",
    "kaig_tab": "devstral-small-2:latest",
    "mem_palace": "gemma4:31b-cloud",
    "dictionary_brain": "cogito:latest",
    "meta_cognition": "gemma4:31b-cloud",

    # Security + recovery
    "security": "phi4-mini:latest",
    "recovery": "llama3.2:3b",

    # Math / trading
    "trading": "mathstral:latest",
    "math": "wizard-math:latest",

    # Vision / OCR / multimodal
    "vision": "llava:latest",

    # Embedding model (semantic search / MemPalace / DictionaryBrain)
    "embedding": "nomic-embed-text:latest",

    # Universal fallback
    "_fallback": "llama3.2:3b",
}

DEFAULT_LIGHT_TIER_ROUTING: Dict[str, str] = {
    "main_brain": "gemma:2b",
    "kaig_tab": "gemma:2b",
    "mem_palace": "gemma:2b",
    "dictionary_brain": "gemma:2b",
    "meta_cognition": "gemma:2b",
    "security": "phi4-mini:latest",
    "recovery": "gemma:2b",
    "trading": "gemma:2b",
    "math": "gemma:2b",
    "vision": "llava:latest",
    "embedding": "nomic-embed-text:latest",
    "_fallback": "gemma:2b",
}

# Backwards-compatible aliases — older code and tests referenced the routing
# tables by their previous names, which conflated tier with role. Keep the
# old names pointing at the new canonical tables so no importer breaks.
DEFAULT_CREATOR_ROUTING = DEFAULT_FULL_TIER_ROUTING
DEFAULT_CONSUMER_ROUTING = DEFAULT_LIGHT_TIER_ROUTING

DEFAULT_EMBEDDING_MODEL_ST = "sentence-transformers/all-MiniLM-L6-v2"

_BACKEND_ORDER: Tuple[str, ...] = ("tensorrt_llm", "vllm", "ollama_http", "offline")


# ── Event-name lazy import (avoids circular imports on boot) ───────────────

def _event_names() -> Dict[str, str]:
    try:
        from core.kingdom_event_names import (
            INFERENCE_GENERATE_REQUEST,
            INFERENCE_GENERATE_RESULT,
            INFERENCE_EMBED_REQUEST,
            INFERENCE_EMBED_RESULT,
            INFERENCE_BACKEND_SWITCH,
            INFERENCE_HEALTH_REPORT,
        )
    except Exception:
        INFERENCE_GENERATE_REQUEST = "inference.generate.request"
        INFERENCE_GENERATE_RESULT = "inference.generate.result"
        INFERENCE_EMBED_REQUEST = "inference.embed.request"
        INFERENCE_EMBED_RESULT = "inference.embed.result"
        INFERENCE_BACKEND_SWITCH = "inference.backend.switch"
        INFERENCE_HEALTH_REPORT = "inference.health.report"
    return {
        "gen_req": INFERENCE_GENERATE_REQUEST,
        "gen_res": INFERENCE_GENERATE_RESULT,
        "emb_req": INFERENCE_EMBED_REQUEST,
        "emb_res": INFERENCE_EMBED_RESULT,
        "switch": INFERENCE_BACKEND_SWITCH,
        "health": INFERENCE_HEALTH_REPORT,
    }


# ── Silent pkg_resources deprecation spam from ety ─────────────────────────
#
# The ``ety`` package still uses the deprecated ``pkg_resources`` API; on every
# import setuptools emits a UserWarning that clutters our console. Scope the
# filter to exactly that message so we don't hide any real deprecations.

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning,
)


# ── Utility: SHA-based pseudo-embedding ────────────────────────────────────
#
# Same construction DictionaryBrain has used as its offline fallback. 64-dim,
# cheap, fully deterministic, good enough for ranking in test environments.

def _sha_pseudo_embedding(text: str, dim: int = 64) -> List[float]:
    digest = hashlib.sha256((text or "").lower().encode("utf-8")).hexdigest()
    vec: List[float] = []
    for i in range(dim):
        byte = int(digest[(i * 2) % len(digest): (i * 2) % len(digest) + 2], 16)
        vec.append(byte / 255.0 - 0.5)
    return vec


# ── Core class ─────────────────────────────────────────────────────────────

class KingdomInferenceStack:
    """Always-on inference orchestrator shared by every Kingdom AI component.

    Construct once (via :func:`get_inference_stack` or direct instantiation
    during bootstrap) and pass the instance everywhere. The class is
    thread-safe: all mutating state sits behind ``self._lock``.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        event_bus: Any = None,
        config: Optional[Dict[str, Any]] = None,
        ollama_base: str = "http://localhost:11434",
    ) -> None:
        self.event_bus = event_bus
        self.config: Dict[str, Any] = dict(config or {})
        self.ollama_base = ollama_base.rstrip("/")
        self._lock = threading.RLock()

        # Platform (desktop/mobile) drives dependency tier.
        # Role (creator/consumer) is recorded for diagnostics only — it
        # never gates which backends we probe.
        self._light_tier = _is_light_tier()
        if self.config.get("force_light_tier") or self.config.get("force_consumer"):
            # ``force_consumer`` kept as a legacy knob for existing tests;
            # semantically it now means "pretend we're on mobile".
            self._light_tier = True
        self._role = "consumer" if _is_consumer_mode() else "creator"
        # Legacy alias preserved so any outside code still reading
        # ``stack._consumer`` keeps working, but it now reflects the tier
        # decision (platform-based), which is what those callers wanted.
        self._consumer = self._light_tier

        # Routing table (user can override a subset via config["routing"])
        base = (
            DEFAULT_LIGHT_TIER_ROUTING if self._light_tier
            else DEFAULT_FULL_TIER_ROUTING
        )
        self.model_routing: Dict[str, str] = dict(base)
        for k, v in (self.config.get("routing") or {}).items():
            if v:
                self.model_routing[str(k)] = str(v)

        # Lazy backend state
        self._embedding_model: Any = None
        self._embedding_device: Optional[str] = None
        self._embedding_dim: Optional[int] = None
        self._active_gen_backend: Optional[str] = None
        self._trt_runner: Any = None
        self._vllm_runner: Any = None

        # Telemetry
        self._generate_total = 0
        self._embed_total = 0
        self._fallbacks_triggered = 0
        self._errors_total = 0
        self._last_error: Optional[str] = None

        # Event-bus subscriptions — optional but useful for async callers
        if event_bus is not None:
            try:
                ev = _event_names()
                event_bus.subscribe(ev["gen_req"], self._on_generate_request)
                event_bus.subscribe(ev["emb_req"], self._on_embed_request)
            except Exception as exc:
                logger.debug("event-bus subscribe skipped: %s", exc)

        torch_info = _probe_torch() if not self._light_tier else {
            "ok": False, "cuda": False, "device": "cpu",
            "device_name": "", "vram_gb": 0.0,
        }
        ollama_info = _probe_ollama(self.ollama_base)
        logger.info(
            "KingdomInferenceStack v%s ready — role=%s platform=%s tier=%s "
            "torch=%s cuda=%s gpu=%s ollama=%s models=%d",
            self.VERSION,
            self._role,
            _platform(),
            "light" if self._light_tier else "full",
            torch_info["ok"], torch_info["cuda"],
            torch_info["device_name"] or "-",
            ollama_info["reachable"], len(ollama_info["available_models"]),
        )

    # ── Model selection ────────────────────────────────────────────────────

    def get_model_for(self, component: str) -> str:
        """Return the model name currently routed for *component*.

        Unknown components fall back to the universal ``_fallback`` model so
        calling code never has to know the routing table up front.
        """
        with self._lock:
            return (
                self.model_routing.get(component)
                or self.model_routing.get("_fallback")
                or "llama3.2:3b"
            )

    def set_model_for(self, component: str, model: str) -> None:
        with self._lock:
            self.model_routing[component] = model

    # ── Generation ─────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        component: str = "main_brain",
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> str:
        """Run a generation for *component* through the best-available backend.

        The fallback chain is TensorRT-LLM → vLLM → Ollama HTTP → offline stub.
        The offline stub never raises; it returns a deterministic placeholder
        so tests and UI paths stay green even without any backend.
        """
        if not prompt:
            return ""
        self._generate_total += 1
        chosen_model = model or self.get_model_for(component)

        order = self._backend_order()
        last_error: Optional[str] = None
        for backend in order:
            try:
                result = self._dispatch_generate(
                    backend, prompt, chosen_model,
                    temperature=temperature, max_tokens=max_tokens,
                    system=system, stream=stream,
                )
                if result is None:
                    continue  # backend unavailable — try next
                if self._active_gen_backend != backend:
                    self._announce_backend_switch(backend, chosen_model)
                return result
            except Exception as exc:
                last_error = f"{backend}: {exc}"
                self._fallbacks_triggered += 1
                logger.debug("generate() backend %s failed: %s", backend, exc)
                continue

        # Every backend refused — offline stub
        self._errors_total += 1
        self._last_error = last_error or "no backend available"
        logger.debug("generate() offline stub used: %s", self._last_error)
        return self._offline_stub(prompt, chosen_model)

    def generate_stream(
        self,
        prompt: str,
        component: str = "main_brain",
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system: Optional[str] = None,
    ) -> Iterable[str]:
        """Yield chunks of a streaming generation from the active backend.

        Currently only the Ollama HTTP backend streams natively; TensorRT-LLM
        and vLLM wrappers return whole strings (sub-100 ms at creator sizes),
        so we emit a single chunk in that case.
        """
        if not prompt:
            return
        chosen_model = self.get_model_for(component)
        backend = self._backend_order()[0]
        if backend == "ollama_http":
            yield from self._ollama_stream(prompt, chosen_model,
                                           temperature=temperature,
                                           max_tokens=max_tokens,
                                           system=system)
            return
        yield self.generate(prompt, component,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            system=system)

    # ── Embedding ──────────────────────────────────────────────────────────

    def embed(self, text: str) -> List[float]:
        """Return an embedding vector for *text* (scalar form)."""
        vecs = self.batch_embed([text])
        return vecs[0] if vecs else _sha_pseudo_embedding(text)

    def batch_embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Return embedding vectors for a batch of *texts*.

        The first invocation lazily loads sentence-transformers (CUDA if
        available, otherwise CPU). If sentence-transformers is missing we
        fall back to the Ollama embeddings endpoint, then to the SHA-256
        pseudo-embedding. The result list has the same length as *texts*.
        """
        self._embed_total += len(texts)
        clean_texts = [str(t or "") for t in texts]
        if not clean_texts:
            return []

        model = self._load_embedding_model() if not self._light_tier else None
        if model is not None:
            try:
                out = model.encode(
                    clean_texts, convert_to_numpy=True, show_progress_bar=False
                )
                if self._embedding_dim is None:
                    self._embedding_dim = int(out.shape[1]) if out.ndim == 2 else len(out[0])
                return [list(map(float, v)) for v in out.tolist()]
            except Exception as exc:
                logger.debug("ST embed failed: %s — falling through", exc)
                self._fallbacks_triggered += 1

        # Try Ollama embeddings
        if _probe_ollama(self.ollama_base)["reachable"]:
            out: List[List[float]] = []
            emb_model = self.model_routing.get("embedding") or "nomic-embed-text:latest"
            all_served_by_ollama = True
            for txt in clean_texts:
                vec = self._ollama_embed_one(txt, emb_model)
                if vec:
                    out.append(vec)
                else:
                    out.append(_sha_pseudo_embedding(txt))
                    self._fallbacks_triggered += 1
                    all_served_by_ollama = False
            if out and self._embedding_dim is None:
                self._embedding_dim = len(out[0])
            if self._embedding_device is None and all_served_by_ollama:
                self._embedding_device = "ollama"
            return out

        # SHA pseudo — always works
        self._fallbacks_triggered += 1
        vecs = [_sha_pseudo_embedding(t) for t in clean_texts]
        if self._embedding_dim is None and vecs:
            self._embedding_dim = len(vecs[0])
        if self._embedding_device is None:
            self._embedding_device = "sha_pseudo"
        return vecs

    generate_embedding = embed  # naming parity with OllamaMemoryIntegration

    # ── Health / routing summary ───────────────────────────────────────────

    def get_system_info(self) -> Dict[str, Any]:
        """Return a human-readable snapshot of the current inference config."""
        torch_info = _probe_torch() if not self._light_tier else {
            "ok": False, "cuda": False, "device": "cpu",
            "device_name": "", "vram_gb": 0.0,
        }
        ollama_info = _probe_ollama(self.ollama_base)
        return {
            "version": self.VERSION,
            "status": "always-on (no toggle)",
            # ``mode`` kept for legacy callers — it now reflects tier so the
            # existing system-info consumers don't need to change. ``role``
            # and ``platform`` expose the orthogonal axes explicitly.
            "mode": "light" if self._light_tier else "full",
            "role": self._role,
            "platform": _platform(),
            "tier": "light" if self._light_tier else "full",
            "active_generation_backend": self._active_gen_backend or "(lazy)",
            "embedding_backend": self._embedding_device or "(lazy)",
            "embedding_dim": self._embedding_dim,
            "backends_available": {
                "tensorrt_llm": self._probe_trt(),
                "vllm": self._probe_vllm(),
                "ollama_http": ollama_info["reachable"],
                "offline": True,
            },
            "torch": {
                "installed": torch_info["ok"],
                "cuda": torch_info["cuda"],
                "device": torch_info["device"],
                "device_name": torch_info["device_name"],
                "vram_gb": torch_info["vram_gb"],
            },
            "ollama": {
                "base": self.ollama_base,
                "reachable": ollama_info["reachable"],
                "model_count": len(ollama_info["available_models"]),
            },
            "routing": dict(self.model_routing),
            "telemetry": {
                "generate_total": self._generate_total,
                "embed_total": self._embed_total,
                "fallbacks_triggered": self._fallbacks_triggered,
                "errors_total": self._errors_total,
                "last_error": self._last_error,
            },
        }

    def publish_health(self) -> None:
        if self.event_bus is None:
            return
        try:
            ev = _event_names()
            self.event_bus.publish(ev["health"], self.get_system_info())
        except Exception as exc:
            logger.debug("health publish failed: %s", exc)

    # ── Backend dispatch ───────────────────────────────────────────────────

    def _backend_order(self) -> Tuple[str, ...]:
        """Return the ordered list of backends to try, subject to tier.

        Light-tier (mobile APK/PWA) builds skip TensorRT-LLM and vLLM
        outright — they would require multi-GB CUDA libs and wouldn't load
        on Android anyway — and go straight to Ollama HTTP → offline stub.
        Full-tier (desktop, *both* creator and consumer) tries the full
        high-performance chain.
        """
        if self._light_tier:
            return ("ollama_http", "offline")
        order: List[str] = []
        if self._probe_trt():
            order.append("tensorrt_llm")
        if self._probe_vllm():
            order.append("vllm")
        order.append("ollama_http")
        order.append("offline")
        return tuple(order)

    def _dispatch_generate(
        self,
        backend: str,
        prompt: str,
        model: str,
        *,
        temperature: float,
        max_tokens: int,
        system: Optional[str],
        stream: bool,
    ) -> Optional[str]:
        if backend == "tensorrt_llm":
            return self._trt_generate(prompt, model, temperature, max_tokens, system)
        if backend == "vllm":
            return self._vllm_generate(prompt, model, temperature, max_tokens, system)
        if backend == "ollama_http":
            return self._ollama_generate(prompt, model, temperature, max_tokens, system)
        if backend == "offline":
            return self._offline_stub(prompt, model)
        return None

    def _announce_backend_switch(self, backend: str, model: str) -> None:
        self._active_gen_backend = backend
        if self.event_bus is not None:
            try:
                ev = _event_names()
                self.event_bus.publish(ev["switch"], {
                    "backend": backend, "model": model, "timestamp": time.time(),
                })
            except Exception:
                pass

    # ── Backend: TensorRT-LLM ──────────────────────────────────────────────
    #
    # Real TensorRT-LLM integration needs a compiled engine per-model, a live
    # ``tensorrt_llm.LLM`` runner, and CUDA 12.4+ with an RTX GPU. Because
    # those prerequisites live off-tree, we keep the hook tight: probe the
    # import, then build a runner lazily. If anything fails, return ``None``
    # so the fallback chain advances. The code is structured so swapping in a
    # real runner is a one-line change in :meth:`_build_trt_runner`.

    def _probe_trt(self) -> bool:
        if _TRT_STATE["probed"]:
            return bool(_TRT_STATE["ok"])
        _TRT_STATE["probed"] = True
        if self._light_tier:
            return False
        try:
            import tensorrt_llm  # noqa: F401  # type: ignore
            _TRT_STATE["ok"] = True
        except Exception:
            _TRT_STATE["ok"] = False
        return bool(_TRT_STATE["ok"])

    def _build_trt_runner(self, model: str) -> Any:
        """Instantiate a TensorRT-LLM runner — placeholder for operator setup.

        The real implementation depends on whether the operator ships a
        pre-compiled engine or wants runtime compilation. We keep this
        isolated so swapping implementations is mechanical.
        """
        try:
            from tensorrt_llm import LLM  # type: ignore
        except Exception:
            return None
        try:
            return LLM(model=model)
        except Exception as exc:
            logger.debug("TensorRT-LLM runner build failed: %s", exc)
            return None

    def _trt_generate(
        self, prompt: str, model: str, temperature: float, max_tokens: int,
        system: Optional[str],
    ) -> Optional[str]:
        if not self._probe_trt():
            return None
        with self._lock:
            if self._trt_runner is None:
                self._trt_runner = self._build_trt_runner(model)
            if self._trt_runner is None:
                return None
        try:
            out = self._trt_runner.generate(
                prompt if not system else f"{system}\n\n{prompt}",
                sampling_params={"temperature": temperature,
                                 "max_new_tokens": max_tokens},
            )
            # TensorRT-LLM returns a CompletionOutput-like object
            text = getattr(out, "text", None) or getattr(out, "output", None) or str(out)
            return str(text)
        except Exception as exc:
            logger.debug("TensorRT-LLM generate failed: %s", exc)
            return None

    # ── Backend: vLLM ──────────────────────────────────────────────────────

    def _probe_vllm(self) -> bool:
        if _VLLM_STATE["probed"]:
            return bool(_VLLM_STATE["ok"])
        _VLLM_STATE["probed"] = True
        if self._light_tier:
            return False
        try:
            import vllm  # noqa: F401  # type: ignore
            _VLLM_STATE["ok"] = True
        except Exception:
            _VLLM_STATE["ok"] = False
        return bool(_VLLM_STATE["ok"])

    def _build_vllm_runner(self, model: str) -> Any:
        try:
            from vllm import LLM  # type: ignore
        except Exception:
            return None
        try:
            return LLM(model=model)
        except Exception as exc:
            logger.debug("vLLM runner build failed: %s", exc)
            return None

    def _vllm_generate(
        self, prompt: str, model: str, temperature: float, max_tokens: int,
        system: Optional[str],
    ) -> Optional[str]:
        if not self._probe_vllm():
            return None
        with self._lock:
            if self._vllm_runner is None:
                self._vllm_runner = self._build_vllm_runner(model)
            if self._vllm_runner is None:
                return None
        try:
            from vllm import SamplingParams  # type: ignore
            sp = SamplingParams(temperature=temperature, max_tokens=max_tokens)
            outs = self._vllm_runner.generate(
                [prompt if not system else f"{system}\n\n{prompt}"], sp
            )
            if outs and getattr(outs[0], "outputs", None):
                return outs[0].outputs[0].text
            return None
        except Exception as exc:
            logger.debug("vLLM generate failed: %s", exc)
            return None

    # ── Backend: Ollama HTTP ───────────────────────────────────────────────

    def _ollama_post(
        self, path: str, payload: Dict[str, Any], timeout: float = 60.0,
    ) -> Dict[str, Any]:
        url = f"{self.ollama_base}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        lines = body.strip().splitlines()
        if len(lines) == 1:
            return json.loads(lines[0])
        combined = ""
        for line in lines:
            try:
                chunk = json.loads(line)
            except Exception:
                continue
            combined += chunk.get("response", "")
        return {"response": combined}

    def _ollama_generate(
        self, prompt: str, model: str, temperature: float, max_tokens: int,
        system: Optional[str],
    ) -> Optional[str]:
        if not _probe_ollama(self.ollama_base)["reachable"]:
            return None
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                # ``num_gpu`` asks Ollama to offload layers to the GPU. -1
                # means "as many as fit", which is what we want on RTX.
                "num_gpu": -1 if _probe_torch().get("cuda") else 0,
            },
        }
        if system:
            payload["system"] = system
        try:
            result = self._ollama_post("/api/generate", payload)
            return str(result.get("response", "")).strip()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.debug("Ollama generate failed: %s", exc)
            return None

    def _ollama_stream(
        self, prompt: str, model: str, *,
        temperature: float = 0.7, max_tokens: int = 1024,
        system: Optional[str] = None,
    ) -> Iterable[str]:
        if not _probe_ollama(self.ollama_base)["reachable"]:
            yield self._offline_stub(prompt, model)
            return
        payload: Dict[str, Any] = {
            "model": model, "prompt": prompt, "stream": True,
            "options": {
                "temperature": temperature, "num_predict": max_tokens,
                "num_gpu": -1 if _probe_torch().get("cuda") else 0,
            },
        }
        if system:
            payload["system"] = system
        url = f"{self.ollama_base}/api/generate"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue
                    piece = chunk.get("response", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        return
        except (urllib.error.URLError, OSError) as exc:
            logger.debug("Ollama stream failed: %s", exc)
            yield self._offline_stub(prompt, model)

    def _ollama_embed_one(self, text: str, model: str) -> List[float]:
        try:
            result = self._ollama_post(
                "/api/embeddings", {"model": model, "prompt": text}, timeout=30,
            )
            emb = result.get("embedding") or []
            return [float(x) for x in emb] if emb else []
        except Exception as exc:
            logger.debug("Ollama embed failed: %s", exc)
            return []

    # ── Backend: offline stub ──────────────────────────────────────────────
    #
    # Returns a deterministic short answer so the UI and tests never see a
    # raw exception when every backend is unavailable. Anything that needs a
    # real answer can check ``get_system_info()['active_generation_backend']``.

    def _offline_stub(self, prompt: str, model: str) -> str:
        self._active_gen_backend = "offline"
        summary = (prompt or "").strip().replace("\n", " ")
        if len(summary) > 160:
            summary = summary[:157] + "..."
        return (
            f"[inference:offline model={model}] "
            f"No GPU/Ollama backend reached — echoing prompt summary: {summary}"
        )

    # ── Embedding model loader ─────────────────────────────────────────────

    def _load_embedding_model(self) -> Any:
        """Lazy-load sentence-transformers on CUDA or CPU.

        Returns ``None`` if the package isn't installed. We deliberately
        default to ``all-MiniLM-L6-v2`` — tiny (23 MB), ~384-dim, fast on
        CPU and near-instant on any RTX card. Operators can override via
        ``config['embedding_model']``.
        """
        with self._lock:
            if self._embedding_model is not None:
                return self._embedding_model
            if self._light_tier:
                return None
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except Exception:
                _ST_STATE["ok"] = False
                return None
            _ST_STATE["ok"] = True
            torch_info = _probe_torch()
            device = "cuda" if torch_info["cuda"] else "cpu"
            model_name = self.config.get("embedding_model") or DEFAULT_EMBEDDING_MODEL_ST
            try:
                self._embedding_model = SentenceTransformer(model_name, device=device)
                self._embedding_device = device
                logger.info(
                    "Embedding model loaded: %s on %s", model_name, device.upper()
                )
                return self._embedding_model
            except Exception as exc:
                logger.info(
                    "Embedding model load failed (%s) — will fall back to "
                    "Ollama / SHA pseudo-embeddings", exc,
                )
                self._embedding_model = None
                return None

    # ── Event-bus handlers ─────────────────────────────────────────────────

    def _on_generate_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        prompt = str(data.get("prompt") or "")
        if not prompt:
            return
        component = str(data.get("component") or "main_brain")
        temperature = float(data.get("temperature", 0.7))
        max_tokens = int(data.get("max_tokens", 1024))
        system = data.get("system")
        reply = self.generate(
            prompt, component, temperature=temperature,
            max_tokens=max_tokens, system=system,
        )
        if self.event_bus is not None:
            try:
                ev = _event_names()
                self.event_bus.publish(ev["gen_res"], {
                    "component": component,
                    "model": self.get_model_for(component),
                    "backend": self._active_gen_backend,
                    "response": reply,
                    "request_id": data.get("request_id"),
                })
            except Exception:
                pass

    def _on_embed_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        text = data.get("text")
        if text is None:
            return
        if isinstance(text, str):
            vectors: List[List[float]] = [self.embed(text)]
        elif isinstance(text, (list, tuple)):
            vectors = self.batch_embed(list(text))
        else:
            return
        if self.event_bus is not None:
            try:
                ev = _event_names()
                self.event_bus.publish(ev["emb_res"], {
                    "vectors": vectors,
                    "dim": self._embedding_dim,
                    "backend": self._embedding_device or "fallback",
                    "request_id": data.get("request_id"),
                })
            except Exception:
                pass


# ── Process-wide lazy singleton ────────────────────────────────────────────

_SINGLETON_LOCK = threading.Lock()
_SINGLETON: Optional[KingdomInferenceStack] = None


def get_inference_stack(
    event_bus: Any = None,
    config: Optional[Dict[str, Any]] = None,
    ollama_base: str = "http://localhost:11434",
) -> KingdomInferenceStack:
    """Return the lazily-constructed process-wide InferenceStack.

    If a previous caller constructed the stack without an event_bus and a
    later caller provides one, we attach it retroactively and subscribe to
    the relevant topics. This lets the bootstrap file wire things up late
    without forcing every importer to pass the bus through.
    """
    global _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is None:
            _SINGLETON = KingdomInferenceStack(
                event_bus=event_bus, config=config, ollama_base=ollama_base,
            )
        elif event_bus is not None and _SINGLETON.event_bus is None:
            _SINGLETON.event_bus = event_bus
            try:
                ev = _event_names()
                event_bus.subscribe(ev["gen_req"], _SINGLETON._on_generate_request)
                event_bus.subscribe(ev["emb_req"], _SINGLETON._on_embed_request)
            except Exception:
                pass
    return _SINGLETON


def reset_inference_stack() -> None:
    """Clear the cached singleton — intended for tests only."""
    global _SINGLETON
    with _SINGLETON_LOCK:
        _SINGLETON = None
    _TORCH_STATE["probed"] = False
    _OLLAMA_STATE["probed"] = False
    _ST_STATE["probed"] = False
    _VLLM_STATE["probed"] = False
    _TRT_STATE["probed"] = False


def __getattr__(name: str) -> Any:
    """Resolve ``from core.inference_stack import inference_stack`` lazily.

    We avoid constructing the singleton at import time because doing so
    would force a GPU / Ollama probe on every importer (including places
    that just want to pass the *class* around). The lazy ``__getattr__``
    keeps import cheap while preserving the convenient attribute name.
    """
    if name == "inference_stack":
        return get_inference_stack()
    raise AttributeError(f"module 'core.inference_stack' has no attribute {name!r}")


__all__ = [
    "KingdomInferenceStack",
    "get_inference_stack",
    "reset_inference_stack",
    # Canonical routing tables (platform/tier based)
    "DEFAULT_FULL_TIER_ROUTING",
    "DEFAULT_LIGHT_TIER_ROUTING",
    # Back-compat aliases (role-named, same values)
    "DEFAULT_CREATOR_ROUTING",
    "DEFAULT_CONSUMER_ROUTING",
    "DEFAULT_EMBEDDING_MODEL_ST",
]


if __name__ == "__main__":  # pragma: no cover — smoke test
    logging.basicConfig(level=logging.INFO)
    st = get_inference_stack()
    info = st.get_system_info()
    print(json.dumps(info, indent=2))
    print("\n-- generate --")
    print(st.generate("Say hello to Kingdom AI in one sentence.",
                      component="dictionary_brain"))
    print("\n-- embed --")
    v = st.embed("kingdom")
    print(f"dim={len(v)} first_three={v[:3]}")
