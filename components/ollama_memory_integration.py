"""Ollama-enhanced memory integration for MemPalace."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.ollama_memory_integration")

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3"

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "knowledge": ["fact", "definition", "concept", "theory", "learn", "science", "history"],
    "trading": ["trade", "stock", "crypto", "price", "market", "portfolio", "profit", "loss"],
    "coding": ["code", "function", "class", "bug", "python", "script", "api", "deploy"],
}


class OllamaMemoryIntegration:
    """Bridges MemPalace with Ollama for AI-enhanced memory operations.

    Parameters
    ----------
    event_bus:
        Optional :class:`core.event_bus.EventBus`. When provided the
        integration subscribes to ``memory.enhance.request`` so callers can
        summarise / embed / categorise memories via the bus.
    model:
        Default Ollama model identifier used when no routing is supplied.
    persistence_layer:
        Optional :class:`MemoryPersistenceLayer`. Kept as a member so
        downstream handlers that need direct memory access (e.g. a future
        ``memory.auto_enrich`` pipeline) don't have to re-look it up. The
        bootstrap in ``kingdom_ai_perfect_v2.py`` always passes this.
    inference_stack:
        Optional :class:`core.inference_stack.KingdomInferenceStack`. When
        supplied, embeddings and summarisation are served by the unified
        always-on RTX-optimised stack (GPU sentence-transformers → Ollama
        → SHA fallback) instead of going through a second, duplicate
        Ollama HTTP call. This is the **single source of truth** pathway.
    """

    def __init__(
        self,
        event_bus: Any = None,
        model: str = DEFAULT_MODEL,
        persistence_layer: Any = None,
        inference_stack: Any = None,
        dictionary_brain: Any = None,
    ) -> None:
        self.event_bus = event_bus
        self.model = model
        self.persistence_layer = persistence_layer
        self._inference_stack = inference_stack
        self._dictionary_brain = dictionary_brain
        self._ollama_available: Optional[bool] = None
        # Tool registry — populated from the dictionary brain at construction
        # time (if wired) and extended via :meth:`register_tool`. The schemas
        # conform to the Ollama native tool-calling spec so downstream calls
        # to /api/chat can include them directly.
        self._tools: Dict[str, Any] = {}
        self._tool_handlers: Dict[str, Any] = {}
        self._register_dictionary_tools()
        if event_bus:
            event_bus.subscribe("memory.enhance.request", self._on_enhance_request)
        logger.info(
            "OllamaMemoryIntegration initialised (model=%s, stack=%s, "
            "persistence=%s, dictionary_tools=%d)",
            model,
            inference_stack is not None,
            persistence_layer is not None,
            len(self._tools),
        )

    def set_inference_stack(self, stack: Any) -> None:
        """Attach an inference stack after construction (lazy bootstrap)."""
        self._inference_stack = stack

    def set_dictionary_brain(self, brain: Any) -> None:
        """Attach a dictionary brain after construction and register its tools.

        The bootstrap order is MemPalace → OllamaMemoryIntegration →
        DictionaryBrain, so callers that construct OMI early can retro-wire
        the dictionary tools here without needing to rebuild OMI.
        """
        self._dictionary_brain = brain
        self._register_dictionary_tools()

    def _register_dictionary_tools(self) -> None:
        """Expose dictionary methods as Ollama-native tool schemas.

        When the LLM sees these tools it can call them mid-stream to fetch
        historical definitions / etymology / cross-era comparisons without
        having to simulate them from its pretraining. This is the physical
        fusion of DictionaryBrain into the Ollama brain path.
        """
        brain = self._dictionary_brain
        if brain is None:
            return

        if hasattr(brain, "get_definition"):
            self._tools["dictionary.define"] = {
                "type": "function",
                "function": {
                    "name": "dictionary_define",
                    "description": (
                        "Return multi-era dictionary definitions for a word. "
                        "Covers early English (1400s+), Webster 1828, modern, "
                        "and Britannica when available."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "word": {"type": "string",
                                     "description": "The word to define."},
                            "source": {"type": "string",
                                       "description":
                                       "One of 'auto', '1828', 'early', "
                                       "'britannica', 'modern'.",
                                       "default": "auto"},
                        },
                        "required": ["word"],
                    },
                },
            }
            self._tool_handlers["dictionary_define"] = (
                lambda word, source="auto": brain.get_definition(word, source)
            )

        if hasattr(brain, "get_etymology"):
            self._tools["dictionary.trace_etymology"] = {
                "type": "function",
                "function": {
                    "name": "dictionary_trace_etymology",
                    "description": (
                        "Trace a word's etymology back through every era on "
                        "file — Proto-Indo-European roots, Latin/Greek stems, "
                        "Old/Middle English forms, and modern cognates."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "word": {"type": "string",
                                     "description": "The word to trace."},
                        },
                        "required": ["word"],
                    },
                },
            }
            self._tool_handlers["dictionary_trace_etymology"] = (
                lambda word: brain.get_etymology(word)
            )

        if hasattr(brain, "evaluate_context"):
            self._tools["dictionary.compare_eras"] = {
                "type": "function",
                "function": {
                    "name": "dictionary_compare_eras",
                    "description": (
                        "Given a sentence, compare how a target word's "
                        "meaning has shifted across eras (early English, "
                        "Webster 1828, modern). Surfaces semantic drift."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sentence": {"type": "string",
                                         "description": "Full sentence."},
                            "target_word": {"type": "string",
                                            "description":
                                            "Optional specific word; "
                                            "otherwise picks the longest."},
                        },
                        "required": ["sentence"],
                    },
                },
            }
            self._tool_handlers["dictionary_compare_eras"] = (
                lambda sentence, target_word=None:
                brain.evaluate_context(sentence, target_word)
            )

        if hasattr(brain, "semantic_search"):
            self._tools["dictionary.semantic_search"] = {
                "type": "function",
                "function": {
                    "name": "dictionary_semantic_search",
                    "description": (
                        "Semantic search across the loaded dictionary corpus "
                        "(Webster 1828 + Britannica + early English) using "
                        "the shared GPU-accelerated embedding stack."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            }
            self._tool_handlers["dictionary_semantic_search"] = (
                lambda query, top_k=5: brain.semantic_search(query, top_k)
            )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return the OpenAI/Ollama-compatible tool schema list.

        Pass this directly to ``/api/chat`` as ``tools=...`` so the Ollama
        model can emit tool-call messages that we dispatch via
        :meth:`dispatch_tool_call`.
        """
        return list(self._tools.values())

    def dispatch_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool the LLM asked for. Returns the tool's raw result."""
        fn = self._tool_handlers.get(name)
        if fn is None:
            return {"error": f"unknown tool: {name}"}
        try:
            return fn(**(arguments or {}))
        except Exception as exc:
            return {"error": str(exc), "tool": name}

    def _ollama_post(self, path: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        url = f"{OLLAMA_BASE}{path}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode()
            lines = body.strip().splitlines()
            if len(lines) == 1:
                return json.loads(lines[0])
            combined = ""
            for line in lines:
                chunk = json.loads(line)
                combined += chunk.get("response", "")
            return {"response": combined}
        except (urllib.error.URLError, OSError) as exc:
            self._ollama_available = False
            logger.warning("Ollama unavailable: %s — using fallback", exc)
            raise

    def _is_available(self) -> bool:
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
            with urllib.request.urlopen(req, timeout=5):
                self._ollama_available = True
        except (urllib.error.URLError, OSError):
            self._ollama_available = False
        return self._ollama_available

    def summarize_memory(self, memory_text: str) -> str:
        # Prefer the unified inference stack when wired — it handles routing,
        # GPU acceleration, and fall-through in one place.
        if self._inference_stack is not None:
            try:
                out = self._inference_stack.generate(
                    f"Summarize in one concise sentence:\n\n{memory_text}",
                    component="mem_palace",
                    temperature=0.2,
                    max_tokens=128,
                )
                if out:
                    return out.strip()
            except Exception:
                pass
        if self._is_available():
            try:
                result = self._ollama_post("/api/generate", {
                    "model": self.model,
                    "prompt": f"Summarize in one concise sentence:\n\n{memory_text}",
                    "stream": False,
                })
                return result.get("response", "").strip()
            except Exception:
                pass
        words = memory_text.split()
        return " ".join(words[:25]) + ("..." if len(words) > 25 else "")

    def generate_embedding(self, text: str) -> List[float]:
        # The inference stack gives us GPU sentence-transformers on creator
        # mode and a safe SHA fallback on consumer — same signature either way.
        if self._inference_stack is not None:
            try:
                vec = self._inference_stack.embed(text)
                if vec:
                    return list(vec)
            except Exception:
                pass
        if self._is_available():
            try:
                result = self._ollama_post("/api/embeddings", {
                    "model": self.model,
                    "prompt": text,
                })
                emb = result.get("embedding", [])
                if emb:
                    return emb
            except Exception:
                pass
        digest = hashlib.sha256(text.lower().encode()).hexdigest()
        return [int(c, 16) / 15.0 for c in digest[:64]]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        length = min(len(a), len(b))
        if length == 0:
            return 0.0
        dot = sum(a[i] * b[i] for i in range(length))
        mag_a = sum(x * x for x in a[:length]) ** 0.5
        mag_b = sum(x * x for x in b[:length]) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def semantic_search(self, query: str, memories: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        query_emb = self.generate_embedding(query)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for mem in memories:
            text = mem.get("value", "") or mem.get("text", "") or str(mem)
            mem_emb = self.generate_embedding(text)
            score = self._cosine_similarity(query_emb, mem_emb)
            scored.append((score, mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": s, "memory": m} for s, m in scored[:top_k]]

    def auto_categorize(self, memory_text: str) -> Dict[str, str]:
        lower = memory_text.lower()
        best_wing, best_score = "knowledge", 0
        for wing, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in lower)
            if score > best_score:
                best_wing, best_score = wing, score
        hall = re.sub(r"[^a-z0-9]+", "_", lower.split(".")[0].strip()[:30])
        return {"wing": best_wing, "hall": hall or "general"}

    def _on_enhance_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("enhance request ignored — expected dict, got %s", type(data).__name__)
            return
        action = data.get("action", "summarize")
        text = data.get("text", "")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "summarize":
                result["summary"] = self.summarize_memory(text)
            elif action == "embed":
                result["embedding"] = self.generate_embedding(text)
            elif action == "categorize":
                result.update(self.auto_categorize(text))
            elif action == "search":
                result["results"] = self.semantic_search(text, data.get("memories", []))
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("Error in enhance request")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("memory.enhance.result", result)
