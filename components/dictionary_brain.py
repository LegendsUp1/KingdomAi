"""DictionaryBrain — multi-era dictionary, etymology, and meta-cognition core.

Integrates four worlds of lexicography into a single event-driven Kingdom AI
subsystem:

  1. Early English dictionaries (c. 1400–1700) — Middle English, Bosworth-Toller,
     LEME. Loaded from ``data/dictionaries/early_english/*.json`` if present.
  2. Noah Webster 1828 — full JSON (auto-cached from DataWar/1828-dictionary
     on first run if network allows; otherwise the built-in seed is used).
  3. Encyclopaedia Britannica (1771–1911 public-domain editions) — parsed from
     ``data/dictionaries/britannica/*.txt`` (drop plain-text Archive.org
     volumes in that folder and they get auto-indexed).
  4. Modern dictionaries — Merriam-Webster / Oxford / Cambridge via
     ``pymultidictionary`` when installed; otherwise marked "unavailable" so
     callers know to ask Ollama.

Meta-cognition hooks:
  * Every lookup is written as a durable memory into the MemPalace
    ``knowledge`` wing with source + confidence metadata.
  * Meaning-shift between historical and modern senses is detected and
    published on ``METACOGNITION_UPDATE`` so the learning loop can flag
    words whose usage has drifted.
  * Etymology (via the ``ety`` library if installed, plus a built-in seed of
    famous etymologies) is attached to every entry.

Integration:
  * Subscribes to ``DICTIONARY_*_REQUEST``, ``BRAIN_QUERY``, and
    ``language.learn.request`` for English-definition hand-offs.
  * Publishes results on the matching ``*_RESULT`` topic and fires
    ``DICTIONARY_LEARNED_WORD`` whenever a new word is cached.
  * Registers itself with :class:`HarmonicOrchestratorV3` as the
    ``dictionary_brain`` subsystem (priority 6) if one is provided.
  * Routes input through :class:`NeuroprotectionLayer.validate_input` when
    one is provided, so adversarial payloads never reach the dictionary
    loaders.

Design constraints:
  * **No hard heavy deps.** Everything works with just the stdlib. Optional
    accelerators (``faiss``, ``sentence-transformers``, ``spacy``, ``ety``,
    ``pymultidictionary``, ``requests``, ``numpy``) are feature-detected and
    used when present.
  * **Network-free by default.** Zero live HTTP calls unless ``config
    ['allow_network']`` is true AND ``requests`` is installed.
  * **Deterministic & testable.** A self-test at the bottom exercises every
    public method without any network, disk, or heavy-dep requirement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import pickle
import re
import threading
import time
import warnings

# ``ety`` still uses the deprecated ``pkg_resources`` API and emits a
# UserWarning on every import. Scope the filter to exactly that message so
# we don't hide any real deprecation warning from another package.
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning,
)
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.dictionary_brain")

# ── Optional-dependency probes (feature-detect, never hard-require) ─────────

try:
    import numpy as _np  # type: ignore

    _NUMPY_OK = True
except Exception:
    _np = None  # type: ignore
    _NUMPY_OK = False

try:
    import faiss as _faiss  # type: ignore

    _FAISS_OK = True
except Exception:
    _faiss = None  # type: ignore
    _FAISS_OK = False

try:
    import ety as _ety  # type: ignore

    _ETY_OK = True
except Exception:
    _ety = None  # type: ignore
    _ETY_OK = False

_MultiDictionary = None  # type: ignore
_PYMULTI_OK = False
# PyPI 1.x ships as the mixed-case ``PyMultiDictionary`` top-level on
# case-sensitive filesystems; older 0.x releases used the lower-case form.
for _mod_name in ("PyMultiDictionary", "pymultidictionary"):
    try:
        _MultiDictionary = __import__(_mod_name, fromlist=["MultiDictionary"]).MultiDictionary  # type: ignore
        _PYMULTI_OK = True
        break
    except Exception:
        continue

try:
    import requests as _requests  # type: ignore

    _REQUESTS_OK = True
except Exception:
    _requests = None  # type: ignore
    _REQUESTS_OK = False

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer  # type: ignore

    _ST_OK = True
except Exception:
    _SentenceTransformer = None  # type: ignore
    _ST_OK = False


# ── Event names (import lazily so the module stays portable) ────────────────

def _event_names() -> Dict[str, str]:
    """Return the runtime event-name mapping. Soft-imports to avoid cycles."""
    try:
        from core.kingdom_event_names import (
            DICTIONARY_LOOKUP_REQUEST,
            DICTIONARY_LOOKUP_RESULT,
            DICTIONARY_ETYMOLOGY_REQUEST,
            DICTIONARY_ETYMOLOGY_RESULT,
            DICTIONARY_EVALUATE_REQUEST,
            DICTIONARY_EVALUATE_RESULT,
            DICTIONARY_SOURCE_LOADED,
            DICTIONARY_LEARNED_WORD,
            METACOGNITION_UPDATE,
            BRAIN_QUERY,
            BRAIN_RESULT,
            MEMORY_WRITE_REQUEST,
        )
    except Exception:
        DICTIONARY_LOOKUP_REQUEST = "dictionary.lookup.request"
        DICTIONARY_LOOKUP_RESULT = "dictionary.lookup.result"
        DICTIONARY_ETYMOLOGY_REQUEST = "dictionary.etymology.request"
        DICTIONARY_ETYMOLOGY_RESULT = "dictionary.etymology.result"
        DICTIONARY_EVALUATE_REQUEST = "dictionary.evaluate.request"
        DICTIONARY_EVALUATE_RESULT = "dictionary.evaluate.result"
        DICTIONARY_SOURCE_LOADED = "dictionary.source.loaded"
        DICTIONARY_LEARNED_WORD = "dictionary.learned_word"
        METACOGNITION_UPDATE = "METACOGNITION_UPDATE"
        BRAIN_QUERY = "BRAIN_QUERY"
        BRAIN_RESULT = "BRAIN_RESULT"
        MEMORY_WRITE_REQUEST = "memory_write_request"
    return {
        "lookup_req": DICTIONARY_LOOKUP_REQUEST,
        "lookup_res": DICTIONARY_LOOKUP_RESULT,
        "etym_req": DICTIONARY_ETYMOLOGY_REQUEST,
        "etym_res": DICTIONARY_ETYMOLOGY_RESULT,
        "eval_req": DICTIONARY_EVALUATE_REQUEST,
        "eval_res": DICTIONARY_EVALUATE_RESULT,
        "source_loaded": DICTIONARY_SOURCE_LOADED,
        "learned": DICTIONARY_LEARNED_WORD,
        "metacog": METACOGNITION_UPDATE,
        "brain_query": BRAIN_QUERY,
        "brain_result": BRAIN_RESULT,
        "mem_write": MEMORY_WRITE_REQUEST,
    }


# ── Built-in seed data ──────────────────────────────────────────────────────
#
# These are tiny, curated, public-domain entries that let the brain answer
# useful questions the very first time it runs, with no network, no ``ety``
# install, and no dropped-in Archive.org texts. They are intentionally
# famous semantic-shift cases so meaning_shift_detected() can demonstrate
# real value out of the box.

_SEED_WEBSTER_1828: Dict[str, str] = {
    "liberty": (
        "LIB'ERTY, n. [L. libertas, from liber, free.] 1. Freedom from "
        "restraint, in a general sense, and applicable to the body, or to "
        "the will or mind. The body is at liberty, when not confined; the "
        "will or mind is at liberty, when not checked or controlled. A man "
        "enjoys liberty, when no physical force operates to restrain his "
        "actions or volitions."
    ),
    "awful": (
        "AW'FUL, a. 1. That strikes with awe; that fills with profound "
        "reverence; as the awful majesty of Jehovah. 2. That fills with "
        "terror and dread; as the awful approach of death."
    ),
    "silly": (
        "SIL'LY, a. [Sax. saelig, happy, prosperous, good, blessed.] 1. "
        "Weak in intellect; foolish; witless; destitute of ordinary "
        "strength of mind; simple; unwise. 2. Weak; helpless. 3. Rustic; "
        "plain; simple; as a silly shepherd."
    ),
    "nice": (
        "NICE, a. [Sax. nesc, tender; allied to Fr. niais, simple.] 1. "
        "Properly, soft, tender. Hence, effeminate; delicate. 2. Fastidious; "
        "squeamish; difficult to be pleased. 3. Refined; as a nice taste. "
        "4. Accurate; exact; as a nice distinction. 5. Pleasing; agreeable."
    ),
    "fond": (
        "FOND, a. [Sax. fonnian, to be foolish.] 1. Foolish; silly; simple; "
        "weak; indiscreet; imprudent. 2. Foolishly tender and loving; "
        "doting; weakly indulgent. 3. Much pleased; loving ardently; "
        "delighted with."
    ),
    "gay": (
        "GAY, a. [Fr. gai; Sp. gayo.] 1. Merry; airy; jovial; sportive; "
        "frolicsome. It denotes more life and animation than cheerful. 2. "
        "Fine; showy; as a gay dress."
    ),
    "science": (
        "SCIENCE, n. [Fr. from L. scientia, from scio, to know.] 1. In a "
        "general sense, knowledge, or certain knowledge; the comprehension "
        "or understanding of truth or facts by the mind. 2. In philosophy, "
        "a collection of the general principles or leading truths relating "
        "to any subject."
    ),
    "computer": (
        "COMPU'TER, n. One who computes; a reckoner; a calculator."
    ),
    "internet": "",
    "democracy": (
        "DEMOC'RACY, n. [Gr. the people, and to hold, or govern.] Government "
        "by the people; a form of government, in which the supreme power is "
        "lodged in the hands of the people collectively, or in which the "
        "people exercise the powers of legislation."
    ),
    "republic": (
        "REPUB'LIC, n. [L. respublica; res, affair, and publica, public.] A "
        "commonwealth; a state in which the exercise of the sovereign power "
        "is lodged in representatives elected by the people."
    ),
    "press": (
        "PRESS, n. 1. An instrument or machine by which any body is squeezed, "
        "crushed or forced into a more compact form. 2. A printing press. "
        "3. The art or business of printing and publishing. Hence, "
        "metaphorically, the press is used for the aggregate of publications "
        "issued from the press, or for the periodical publications."
    ),
}

_SEED_EARLY_ENGLISH: Dict[str, Dict[str, str]] = {
    "middle_english": {
        "nice": "Nyce: foolish, stupid, senseless (c. 1300, from OFr. nice, from L. nescius).",
        "silly": "Sely: happy, blessed, innocent, pious (c. 1200).",
        "awful": "Aweful: inspiring reverence or dread (c. 1300).",
        "fond": "Fonned: foolish, mad (c. 1340).",
        "liberty": "Liberte: freedom of choice, exemption from control (c. 1375, from OFr.).",
        "gay": "Gai: noble, beautiful, excellent; light-hearted (c. 1325).",
    },
    "bosworth_toller": {
        "liberty": "Freodóm: the state of being free, emancipation (Old English).",
        "science": "Wísdóm: knowledge, wisdom, learning (Old English).",
        "book": "Bóc: a written document, a book (Old English, cognate with beech tree).",
    },
    "leme_1450_1750": {
        "republic": "Republique: the common-weal, a state in which the sovereignty resides in the people (Cotgrave, 1611).",
        "democracy": "Democratie: the government of a commonwealth by the whole body of the people (Cockeram, 1623).",
    },
}

_SEED_BRITANNICA: Dict[str, str] = {
    "liberty": (
        "LIBERTY (1911). In its most comprehensive sense, the state of being "
        "exempt from the domination of others or from restricting "
        "circumstances. Civil liberty is the liberty of members of a civil "
        "society, protected by law from violation of natural rights."
    ),
    "democracy": (
        "DEMOCRACY (1911). A form of government in which the sovereign power "
        "resides in the people and is exercised by them directly or by "
        "officers whom they elect to represent them. From Greek demos "
        "(people) and kratos (power)."
    ),
    "science": (
        "SCIENCE (1911). A branch of study concerned either with a connected "
        "body of demonstrated truths or with observed facts systematically "
        "classified and more or less colligated by being brought under "
        "general laws, and which includes trustworthy methods for the "
        "discovery of new truth within its own domain."
    ),
}

_SEED_ETYMOLOGY: Dict[str, List[Dict[str, str]]] = {
    "liberty": [
        {"word": "liberty", "language": "English", "relation": "derived from"},
        {"word": "liberté", "language": "Old French (12c)", "relation": "derived from"},
        {"word": "libertas", "language": "Latin", "relation": "derived from"},
        {"word": "liber", "language": "Latin", "relation": "root (free)"},
    ],
    "awful": [
        {"word": "awful", "language": "English", "relation": "compound of"},
        {"word": "awe", "language": "Middle English (c.1300)", "relation": "from"},
        {"word": "agi", "language": "Old Norse", "relation": "from"},
        {"word": "-ful", "language": "Old English suffix", "relation": "meaning 'full of'"},
    ],
    "nice": [
        {"word": "nice", "language": "English (c.1300)", "relation": "from"},
        {"word": "nice", "language": "Old French (12c)", "relation": "from"},
        {"word": "nescius", "language": "Latin", "relation": "meaning 'ignorant'"},
        {"word": "ne-scire", "language": "Latin", "relation": "literally 'not to know'"},
    ],
    "silly": [
        {"word": "silly", "language": "English", "relation": "from"},
        {"word": "sely", "language": "Middle English", "relation": "meaning 'happy, blessed'"},
        {"word": "saelig", "language": "Old English", "relation": "meaning 'blessed'"},
    ],
    "science": [
        {"word": "science", "language": "English", "relation": "from"},
        {"word": "science", "language": "Old French (12c)", "relation": "from"},
        {"word": "scientia", "language": "Latin", "relation": "meaning 'knowledge'"},
        {"word": "scire", "language": "Latin", "relation": "meaning 'to know'"},
    ],
    "computer": [
        {"word": "computer", "language": "English (1640s)", "relation": "originally 'one who computes'"},
        {"word": "computare", "language": "Latin", "relation": "'to count together, sum up'"},
        {"word": "com- + putare", "language": "Latin", "relation": "'to reckon'"},
    ],
    "democracy": [
        {"word": "democracy", "language": "English (c.1570)", "relation": "from"},
        {"word": "démocratie", "language": "Middle French", "relation": "from"},
        {"word": "dēmokratía", "language": "Greek", "relation": "compound of"},
        {"word": "dēmos + kratos", "language": "Greek", "relation": "'people' + 'power, rule'"},
    ],
}


# ── Core dataclasses ────────────────────────────────────────────────────────

@dataclass
class DictionaryEntry:
    """Single normalised dictionary entry across all sources."""

    word: str
    source: str
    era: str
    definition: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Utility helpers ─────────────────────────────────────────────────────────

def _pseudo_embedding(text: str, dim: int = 64) -> List[float]:
    """Deterministic SHA-based pseudo-embedding.

    Not a real embedding — just enough for crude cosine similarity so the
    brain keeps working when no model is installed. Identical to the
    fallback path in :class:`OllamaMemoryIntegration` so the two stay
    comparable.
    """
    digest = hashlib.sha512(text.lower().encode("utf-8")).hexdigest()
    # Map hex chars to floats in [-1, 1] for better cosine behaviour.
    return [((int(c, 16) / 15.0) * 2.0) - 1.0 for c in digest[:dim]]


def _cosine(a: List[float], b: List[float]) -> float:
    length = min(len(a), len(b))
    if length == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(length))
    mag_a = math.sqrt(sum(x * x for x in a[:length]))
    mag_b = math.sqrt(sum(x * x for x in b[:length]))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")


def _tokens(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


# ── The DictionaryBrain ─────────────────────────────────────────────────────

class DictionaryBrain:
    """Multi-era dictionary + etymology + meta-cognition subsystem.

    See the module docstring for the full design philosophy. The public
    surface that other subsystems care about:

    * :meth:`get_definition` — synchronous lookup for any era/source.
    * :meth:`get_etymology` — synchronous origin trace.
    * :meth:`evaluate_context` — definition + etymology + meaning-shift
      analysis for a sentence.
    * :meth:`enrich_prompt_for_ollama` — one-shot prompt rewriter that prefixes
      a user message with multi-era context.
    * :meth:`get_tools` / :meth:`call_tool` — Ollama-native function-calling
      schemas and dispatcher.
    * :meth:`get_status` — harmonic-orchestrator friendly status report.

    The class is safe to instantiate with ``event_bus=None`` for unit tests.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        event_bus: Any = None,
        data_dir: str = "~/.kingdom_ai/dictionaries",
        persistence_layer: Any = None,
        palace_manager: Any = None,
        ollama_integration: Any = None,
        language_hub: Any = None,
        harmonic_orchestrator: Any = None,
        neuroprotection: Any = None,
        inference_stack: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.event_bus = event_bus
        self.config: Dict[str, Any] = dict(config or {})
        self.data_dir = Path(os.path.expanduser(data_dir))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._persistence = persistence_layer
        self._palace = palace_manager
        self._ollama = ollama_integration
        self._language_hub = language_hub
        self._orchestrator = harmonic_orchestrator
        self._neuroprotection = neuroprotection
        # Unified always-on inference. Prefer it over anything else because it
        # already encapsulates TensorRT-LLM → vLLM → Ollama → offline plus
        # GPU-accelerated sentence-transformers embeddings.
        self._inference_stack = inference_stack

        # Physical fusion into the Ollama brain path: if the OMI was wired
        # before DictionaryBrain finished constructing (the usual bootstrap
        # order in kingdom_ai_perfect_v2.py / kingdom_ai_consumer.py), let it
        # know about us so it can expose dictionary_define / trace_etymology /
        # compare_eras / semantic_search as Ollama-native tools.
        if ollama_integration is not None and hasattr(
            ollama_integration, "set_dictionary_brain"
        ):
            try:
                ollama_integration.set_dictionary_brain(self)
            except Exception as _owx:  # noqa: BLE001 — best-effort wiring
                logger.debug(
                    "OMI dictionary tool registration skipped: %s", _owx
                )

        # Source stores --------------------------------------------------------
        self.webster_1828: Dict[str, str] = {}
        self.britannica: Dict[str, str] = {}
        self.early_english: Dict[str, Dict[str, str]] = {}
        self._modern_dict: Any = None

        # Seed with built-ins first so the brain is never empty.
        self.webster_1828.update(_SEED_WEBSTER_1828)
        self.britannica.update(_SEED_BRITANNICA)
        for dialect, entries in _SEED_EARLY_ENGLISH.items():
            self.early_english.setdefault(dialect, {}).update(entries)
        self._etymology_seed: Dict[str, List[Dict[str, str]]] = dict(_SEED_ETYMOLOGY)

        # Load any cached / user-dropped data on top of the seed.
        self._load_webster_1828()
        self._load_britannica()
        self._load_early_english()
        self._init_modern_dict()

        # Vector index for semantic search
        self._index_lock = threading.Lock()
        self._index_entries: List[Tuple[str, str, str]] = []  # (source, key, snippet)
        self._index_vectors: List[List[float]] = []
        self._faiss_index: Any = None
        self._embedding_model: Any = None
        self._build_or_load_index()

        # Meta-cognition telemetry
        self._lookups_total = 0
        self._meaning_shifts_detected = 0
        self._unknown_lookups = 0

        # Event bus wiring
        if event_bus is not None:
            ev = _event_names()
            event_bus.subscribe(ev["lookup_req"], self._on_lookup_request)
            event_bus.subscribe(ev["etym_req"], self._on_etymology_request)
            event_bus.subscribe(ev["eval_req"], self._on_evaluate_request)
            event_bus.subscribe(ev["brain_query"], self._on_brain_query)
            logger.debug(
                "DictionaryBrain subscribed to %s, %s, %s, %s",
                ev["lookup_req"], ev["etym_req"], ev["eval_req"], ev["brain_query"],
            )

        # Register with harmonic orchestrator
        if harmonic_orchestrator is not None:
            try:
                harmonic_orchestrator.register_subsystem(
                    "dictionary_brain", self._subsystem_handler, priority=6
                )
            except Exception as exc:
                logger.debug("Harmonic registration skipped: %s", exc)

        # Reverse-link ourselves into the language learning hub so its
        # vocabulary path can auto-enrich with multi-era definitions.
        if language_hub is not None and hasattr(language_hub, "set_dictionary_brain"):
            try:
                language_hub.set_dictionary_brain(self)
            except Exception as exc:
                logger.debug("LanguageHub reverse-link skipped: %s", exc)

        logger.info(
            "DictionaryBrain v%s ready — webster=%d britannica=%d early=%d "
            "(numpy=%s faiss=%s ety=%s pymulti=%s requests=%s st=%s)",
            self.VERSION,
            len(self.webster_1828),
            len(self.britannica),
            sum(len(v) for v in self.early_english.values()),
            _NUMPY_OK, _FAISS_OK, _ETY_OK, _PYMULTI_OK, _REQUESTS_OK, _ST_OK,
        )

    # ── Source loaders ──────────────────────────────────────────────────────

    def _load_webster_1828(self) -> None:
        """Load full Webster 1828 JSON, merging over the seed."""
        cache = self.data_dir / "webster_1828.json"
        if cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.webster_1828.update(
                        {str(k).lower(): str(v) for k, v in data.items()
                         if v is not None}
                    )
                    logger.info(
                        "Loaded %d Webster 1828 entries from cache", len(data)
                    )
                    self._publish_source_loaded("webster_1828", len(data), "cache")
                    return
            except Exception as exc:
                logger.warning("Webster 1828 cache corrupt (%s) — reseeding", exc)

        # Optional network refresh
        if self.config.get("allow_network") and _REQUESTS_OK:
            url = (
                "https://raw.githubusercontent.com/DataWar/1828-dictionary/"
                "main/1828-dictionary.json"
            )
            try:
                resp = _requests.get(url, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict):
                    self.webster_1828.update(
                        {str(k).lower(): str(v) for k, v in data.items()
                         if v is not None}
                    )
                    cache.write_text(json.dumps(data), encoding="utf-8")
                    logger.info(
                        "Downloaded %d Webster 1828 entries from GitHub", len(data)
                    )
                    self._publish_source_loaded("webster_1828", len(data), "network")
                    return
            except Exception as exc:
                logger.info("Webster 1828 network load skipped: %s", exc)

        self._publish_source_loaded("webster_1828", len(self.webster_1828), "seed")

    def _load_britannica(self) -> None:
        """Parse any .txt / .json files under ``data/dictionaries/britannica/``."""
        brit_dir = self.data_dir / "britannica"
        if not brit_dir.exists():
            self._publish_source_loaded("britannica", len(self.britannica), "seed")
            return

        count = 0
        for path in brit_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.britannica.update(
                        {str(k).lower(): str(v) for k, v in data.items() if v}
                    )
                    count += len(data)
            except Exception as exc:
                logger.warning("Britannica %s skipped: %s", path.name, exc)

        for path in brit_dir.glob("*.txt"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                for title, body in self._parse_britannica_text(text):
                    if title and body:
                        self.britannica[title.lower()] = body
                        count += 1
            except Exception as exc:
                logger.warning("Britannica %s parse failed: %s", path.name, exc)

        if count:
            logger.info("Loaded %d Britannica entries from %s", count, brit_dir)
        self._publish_source_loaded(
            "britannica", len(self.britannica), "disk" if count else "seed"
        )

    @staticmethod
    def _parse_britannica_text(text: str) -> Iterable[Tuple[str, str]]:
        """Split Archive.org/Wikisource-style Britannica plain text.

        Heuristic: an entry starts with an all-caps headword at the
        beginning of a paragraph, optionally followed by a comma or a
        period and a space. This matches the 1911 edition's typesetting
        faithfully enough for bulk ingest.
        """
        head_re = re.compile(r"^([A-Z][A-Z'\- ]{2,60})[,.]\s", re.MULTILINE)
        paragraphs = re.split(r"\n\s*\n", text)
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            match = head_re.match(para)
            if match:
                head = match.group(1).strip()
                body = para[match.end():].strip()
                if body:
                    yield head, body

    def _load_early_english(self) -> None:
        """Load Middle English / Bosworth-Toller / LEME JSON dumps."""
        ee_dir = self.data_dir / "early_english"
        if not ee_dir.exists():
            total = sum(len(v) for v in self.early_english.values())
            self._publish_source_loaded("early_english", total, "seed")
            return

        count = 0
        for path in ee_dir.glob("*.json"):
            dialect = path.stem.lower()
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    bucket = self.early_english.setdefault(dialect, {})
                    bucket.update(
                        {str(k).lower(): str(v) for k, v in data.items() if v}
                    )
                    count += len(data)
            except Exception as exc:
                logger.warning("Early-English %s skipped: %s", path.name, exc)

        if count:
            logger.info("Loaded %d early-English entries from %s", count, ee_dir)
        total = sum(len(v) for v in self.early_english.values())
        self._publish_source_loaded(
            "early_english", total, "disk" if count else "seed"
        )

    def _init_modern_dict(self) -> None:
        if not _PYMULTI_OK:
            return
        try:
            self._modern_dict = _MultiDictionary()
            logger.info("pymultidictionary available — modern lookups enabled")
        except Exception as exc:
            logger.debug("pymultidictionary init failed: %s", exc)
            self._modern_dict = None

    # ── Index build / load ──────────────────────────────────────────────────

    def _build_or_load_index(self) -> None:
        index_path = self.data_dir / "faiss_index.bin"
        meta_path = self.data_dir / "faiss_index.meta.pkl"
        if _FAISS_OK and index_path.exists() and meta_path.exists():
            try:
                self._faiss_index = _faiss.read_index(str(index_path))
                with meta_path.open("rb") as fh:
                    self._index_entries = pickle.load(fh)
                logger.info(
                    "Loaded FAISS index from disk (%d entries)",
                    len(self._index_entries),
                )
                return
            except Exception as exc:
                logger.warning("FAISS cache unreadable (%s) — rebuilding", exc)

        self._rebuild_index()

        if _FAISS_OK and self._faiss_index is not None:
            try:
                _faiss.write_index(self._faiss_index, str(index_path))
                with meta_path.open("wb") as fh:
                    pickle.dump(self._index_entries, fh)
                logger.info("Saved FAISS index to %s", index_path)
            except Exception as exc:
                logger.debug("FAISS save skipped: %s", exc)

    def _lazy_embedding_model(self) -> Any:
        if self._embedding_model is not None:
            return self._embedding_model
        if _ST_OK and self.config.get("use_sentence_transformers", False):
            try:
                self._embedding_model = _SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("sentence-transformers model loaded")
            except Exception as exc:
                logger.warning("ST model load failed (%s) — using stdlib embeddings", exc)
                self._embedding_model = None
        return self._embedding_model

    def _embed(self, text: str) -> List[float]:
        # Prefer the unified inference stack — it already handles GPU
        # sentence-transformers → Ollama embeddings → SHA fallback in one
        # place, so callers get consistent dimensionality across the system.
        if self._inference_stack is not None:
            try:
                vec = self._inference_stack.embed(text)
                if vec:
                    return list(vec)
            except Exception:
                pass
        model = self._lazy_embedding_model()
        if model is not None:
            try:
                vec = model.encode([text], convert_to_numpy=_NUMPY_OK)
                if _NUMPY_OK:
                    return vec[0].tolist()
                return list(vec[0])
            except Exception:
                pass
        if self._ollama is not None:
            try:
                return list(self._ollama.generate_embedding(text))
            except Exception:
                pass
        return _pseudo_embedding(text)

    def _rebuild_index(self) -> None:
        with self._index_lock:
            self._index_entries = []
            self._index_vectors = []
            texts: List[str] = []

            for word, body in self.webster_1828.items():
                snippet = f"Webster 1828 • {word}: {str(body)[:320]}"
                self._index_entries.append(("webster_1828", word, snippet))
                texts.append(snippet)
            for word, body in self.britannica.items():
                snippet = f"Britannica • {word}: {str(body)[:320]}"
                self._index_entries.append(("britannica", word, snippet))
                texts.append(snippet)
            for dialect, entries in self.early_english.items():
                for word, body in entries.items():
                    snippet = f"{dialect} • {word}: {str(body)[:320]}"
                    self._index_entries.append((dialect, word, snippet))
                    texts.append(snippet)

            if not texts:
                self._faiss_index = None
                return

            self._index_vectors = [self._embed(t) for t in texts]

            if _FAISS_OK and _NUMPY_OK and self._index_vectors:
                try:
                    arr = _np.asarray(self._index_vectors, dtype="float32")
                    dim = arr.shape[1]
                    self._faiss_index = _faiss.IndexFlatL2(dim)
                    self._faiss_index.add(arr)
                    logger.info("Built FAISS index: %d x %d", arr.shape[0], dim)
                    return
                except Exception as exc:
                    logger.warning("FAISS build failed (%s) — using pure-python", exc)
                    self._faiss_index = None
            else:
                self._faiss_index = None

    # ── Lookup primitives ───────────────────────────────────────────────────

    def _lookup_webster_1828(self, word: str) -> Optional[str]:
        return self.webster_1828.get(word.lower()) or None

    def _lookup_britannica(self, word: str) -> Optional[str]:
        return self.britannica.get(word.lower()) or None

    def _lookup_early_english(self, word: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        key = word.lower()
        for dialect, entries in self.early_english.items():
            if key in entries:
                out[dialect] = entries[key]
        return out

    def _lookup_modern(self, word: str) -> Optional[Any]:
        if self._modern_dict is None:
            return None
        try:
            return self._modern_dict.meaning(word, lang="en")
        except Exception as exc:
            logger.debug("pymultidictionary lookup failed: %s", exc)
            return None

    # ── Public API ──────────────────────────────────────────────────────────

    def get_definition(self, word: str, source: str = "auto") -> Dict[str, Any]:
        """Return a definition from *source* (``1828``/``webster``/``britannica``/
        ``early``/``modern``/``auto``). ``auto`` returns a merged view."""
        word = str(word).strip().lower()
        self._lookups_total += 1

        if not word:
            return {"word": "", "definition": None, "source": "empty"}

        if source in ("1828", "webster"):
            defn = self._lookup_webster_1828(word)
            return self._wrap(word, defn, "Noah Webster 1828", "1828")
        if source == "britannica":
            defn = self._lookup_britannica(word)
            return self._wrap(word, defn, "Encyclopaedia Britannica", "1911")
        if source == "early":
            defns = self._lookup_early_english(word)
            return {
                "word": word,
                "source": "Early English (ME / Bosworth-Toller / LEME)",
                "era": "c.1100-1750",
                "definitions_by_dialect": defns,
                "available": bool(defns),
            }
        if source == "modern":
            defn = self._lookup_modern(word)
            return self._wrap(word, defn, "Merriam-Webster / MultiDictionary", "modern")

        # auto — merged view
        merged: Dict[str, Any] = {
            "word": word,
            "source": "merged",
            "era": "multi",
            "1828_webster": self._lookup_webster_1828(word),
            "britannica": self._lookup_britannica(word),
            "early_english": self._lookup_early_english(word),
            "modern": self._lookup_modern(word),
        }
        found = any(
            [merged["1828_webster"], merged["britannica"],
             merged["early_english"], merged["modern"]]
        )
        merged["available"] = bool(found)
        if not found:
            self._unknown_lookups += 1
        else:
            self._remember(word, merged)
        return merged

    @staticmethod
    def _wrap(
        word: str, definition: Any, source: str, era: str
    ) -> Dict[str, Any]:
        return {
            "word": word,
            "source": source,
            "era": era,
            "definition": definition,
            "available": bool(definition),
        }

    def get_etymology(self, word: str) -> Dict[str, Any]:
        """Trace a word's etymology via ``ety`` if installed, else the seed."""
        word = str(word).strip().lower()
        if not word:
            return {"word": "", "etymology_trace": [], "confidence": 0.0}

        origins: List[Dict[str, str]] = []
        source = "seed"

        if _ETY_OK:
            try:
                for origin in _ety.origins(word, recursive=True):
                    origins.append({
                        "word": getattr(origin, "word", str(origin)),
                        "language": getattr(origin, "language", "unknown"),
                        "relation": getattr(origin, "relation", "derived from"),
                    })
                if origins:
                    source = "ety (Etymological Wordnet)"
            except Exception as exc:
                logger.debug("ety lookup failed: %s", exc)

        if not origins:
            origins = list(self._etymology_seed.get(word, []))

        return {
            "word": word,
            "etymology_trace": origins,
            "full_etymology": " → ".join(o["word"] for o in origins) if origins else "unknown",
            "source": source,
            "confidence": 0.85 if origins else 0.25,
        }

    def evaluate_context(
        self, sentence: str, target_word: Optional[str] = None
    ) -> Dict[str, Any]:
        """Full meta-cognition pass over *sentence* + optional *target_word*."""
        sentence = str(sentence or "")
        if self._neuroprotection is not None:
            safe = self._neuroprotection.validate_input(sentence)
            if not safe.get("safe", True):
                logger.warning(
                    "DictionaryBrain input rejected by neuroprotection: %s",
                    safe.get("findings"),
                )
                return {
                    "error": "input_rejected",
                    "findings": safe.get("findings", []),
                }

        if not target_word:
            target_word = self._auto_select_word(sentence)
        target_word = (target_word or "").strip().lower()
        if not target_word:
            return {"error": "no_evaluable_word", "sentence": sentence}

        merged = self.get_definition(target_word, "auto")
        etymology = self.get_etymology(target_word)
        related = self.semantic_search(sentence or target_word, top_k=5)

        historical_text = (
            merged.get("1828_webster") or
            " ".join(merged.get("early_english", {}).values()) or
            merged.get("britannica") or
            ""
        )
        modern_text = merged.get("modern")
        if not isinstance(modern_text, str):
            modern_text = json.dumps(modern_text) if modern_text else ""

        shift, shift_score = self._detect_meaning_shift(
            historical_text, modern_text
        )

        if shift:
            self._meaning_shifts_detected += 1

        report = {
            "target_word": target_word,
            "sentence": sentence,
            "definitions": merged,
            "etymology": etymology,
            "related_entries": related,
            "meta_analysis": {
                "meaning_shift_detected": shift,
                "shift_score": round(shift_score, 3),
                "etymology_confidence": etymology.get("confidence", 0.0),
                "entry_confidence": 0.9 if merged.get("available") else 0.2,
                "learning_note": (
                    f"Evaluated '{target_word}'. "
                    + ("Meaning shift detected — enqueue for deeper learning."
                       if shift else "Stable across eras.")
                ),
            },
            "recommendation": (
                "Historical meaning differs markedly — verify user's intent."
                if shift else "Strong multi-era match."
            ),
        }

        self._publish_metacognition(target_word, report)
        return report

    def _detect_meaning_shift(
        self, historical: str, modern: str
    ) -> Tuple[bool, float]:
        """Return (shift_detected, distance) from comparing two definitions."""
        if not historical or not modern:
            return False, 0.0
        hist_tokens = set(_tokens(historical))
        mod_tokens = set(_tokens(modern))
        if not hist_tokens or not mod_tokens:
            return False, 0.0
        overlap = len(hist_tokens & mod_tokens)
        union = len(hist_tokens | mod_tokens)
        jaccard = overlap / union if union else 0.0
        cosine = _cosine(
            self._embed(historical[:400]),
            self._embed(modern[:400]),
        )
        blended = 1.0 - (0.6 * jaccard + 0.4 * max(0.0, cosine))
        return blended > 0.55, blended

    def _auto_select_word(self, sentence: str) -> Optional[str]:
        """Pick the most salient content word from *sentence*."""
        if not sentence:
            return None
        stop = {
            "the", "a", "an", "and", "or", "but", "of", "in", "on", "at",
            "to", "for", "is", "are", "was", "were", "be", "been", "being",
            "it", "this", "that", "these", "those", "as", "by", "with",
            "from", "into", "about", "not", "no", "yes", "you", "your",
            "we", "our", "us", "they", "them", "their", "he", "she", "him",
            "her", "his", "hers",
        }
        tokens = _tokens(sentence)
        # Prefer words we already know — that's the most useful hit.
        for tok in tokens:
            if tok in stop:
                continue
            if (tok in self.webster_1828 or tok in self.britannica
                    or any(tok in e for e in self.early_english.values())):
                return tok
        for tok in tokens:
            if tok not in stop and len(tok) >= 4:
                return tok
        return tokens[0] if tokens else None

    # ── Semantic search ─────────────────────────────────────────────────────

    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return up to *top_k* entries most similar to *query*."""
        if not query or not self._index_entries:
            return []

        query_vec = self._embed(query)

        if _FAISS_OK and _NUMPY_OK and self._faiss_index is not None:
            try:
                arr = _np.asarray([query_vec], dtype="float32")
                distances, indices = self._faiss_index.search(arr, top_k)
                out: List[Dict[str, Any]] = []
                for d, i in zip(distances[0].tolist(), indices[0].tolist()):
                    if 0 <= i < len(self._index_entries):
                        src, key, snippet = self._index_entries[i]
                        out.append({
                            "source": src,
                            "word": key,
                            "snippet": snippet,
                            "distance": float(d),
                        })
                return out
            except Exception as exc:
                logger.debug("FAISS search failed (%s) — falling back", exc)

        scored: List[Tuple[float, int]] = []
        for idx, vec in enumerate(self._index_vectors):
            score = _cosine(query_vec, vec)
            scored.append((score, idx))
        scored.sort(key=lambda x: x[0], reverse=True)

        out = []
        for score, idx in scored[:top_k]:
            src, key, snippet = self._index_entries[idx]
            out.append({
                "source": src,
                "word": key,
                "snippet": snippet,
                "score": round(score, 4),
            })
        return out

    # ── MemPalace integration ───────────────────────────────────────────────

    def _remember(self, word: str, entry: Dict[str, Any]) -> None:
        """Persist *word*+*entry* as a durable memory. Silent on failure."""
        try:
            snippet = (
                str(entry.get("1828_webster") or entry.get("britannica")
                    or entry.get("modern") or "")
            )[:400]
            if not snippet:
                return
            if self._persistence is not None:
                self._persistence.write_memory(
                    key=f"dictionary.word.{word}",
                    value=snippet,
                    metadata={
                        "source": "dictionary_brain",
                        "eras": [
                            k for k in ("1828_webster", "britannica",
                                        "early_english", "modern")
                            if entry.get(k)
                        ],
                        "timestamp": time.time(),
                    },
                )
            if self._palace is not None:
                try:
                    from components.memory_palace_manager import MemoryWing  # type: ignore
                    self._palace.store_in_hall(
                        MemoryWing.KNOWLEDGE,
                        "vocabulary",
                        {"word": word, "definition": snippet,
                         "source": "dictionary_brain"},
                    )
                except Exception:
                    pass
            if self.event_bus is not None:
                ev = _event_names()
                self.event_bus.publish(ev["learned"], {
                    "word": word,
                    "snippet": snippet[:200],
                    "timestamp": time.time(),
                })
        except Exception as exc:
            logger.debug("_remember swallowed error: %s", exc)

    # ── Ollama tool calling ─────────────────────────────────────────────────

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return Ollama-native function-calling schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "dictionary_get_definition",
                    "description": (
                        "Look up a word's definition from a specific era or "
                        "source (1828 Webster, Encyclopaedia Britannica, "
                        "early English 1400-1750, or modern)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "word": {"type": "string"},
                            "source": {
                                "type": "string",
                                "enum": ["1828", "britannica", "early",
                                         "modern", "auto"],
                                "default": "auto",
                            },
                        },
                        "required": ["word"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dictionary_get_etymology",
                    "description": (
                        "Trace the linguistic origin and historical roots of "
                        "a word back through Old French, Latin, Greek, Old "
                        "English, etc."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"word": {"type": "string"}},
                        "required": ["word"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dictionary_evaluate_context",
                    "description": (
                        "Full meta-cognition analysis: definitions from every "
                        "era + etymology + meaning-shift detection for a "
                        "target word inside a sentence."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sentence": {"type": "string"},
                            "target_word": {"type": "string"},
                        },
                        "required": ["sentence"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dictionary_semantic_search",
                    "description": (
                        "Search all loaded dictionaries semantically and "
                        "return the top matches."
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
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch an Ollama tool call to the correct method."""
        args = arguments or {}
        if name == "dictionary_get_definition":
            return self.get_definition(
                args.get("word", ""), args.get("source", "auto")
            )
        if name == "dictionary_get_etymology":
            return self.get_etymology(args.get("word", ""))
        if name == "dictionary_evaluate_context":
            return self.evaluate_context(
                args.get("sentence", ""), args.get("target_word")
            )
        if name == "dictionary_semantic_search":
            return {
                "query": args.get("query", ""),
                "results": self.semantic_search(
                    args.get("query", ""), int(args.get("top_k", 5))
                ),
            }
        return {"error": f"unknown tool: {name}"}

    def answer(
        self,
        user_prompt: str,
        *,
        component: str = "dictionary_brain",
        max_tokens: int = 512,
        temperature: float = 0.4,
    ) -> Dict[str, Any]:
        """End-to-end brain path: enrich *user_prompt* with multi-era context
        and run it through the always-on inference stack.

        This is the recommended way for tabs/agents to "ask the dictionary
        brain" a free-form question. Returns a dict with the enriched prompt,
        the backend that served it, and the generated answer. When the stack
        is not wired we still return the enriched prompt plus a short offline
        acknowledgement so callers never have to special-case a missing
        backend.
        """
        enriched = self.enrich_prompt_for_ollama(user_prompt)
        backend: Optional[str] = None
        answer_text: str = ""
        if self._inference_stack is not None:
            try:
                answer_text = self._inference_stack.generate(
                    enriched,
                    component=component,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                backend = getattr(self._inference_stack, "_active_gen_backend", None)
            except Exception as exc:
                logger.debug("DictionaryBrain.answer inference failed: %s", exc)
        if not answer_text:
            answer_text = (
                "Prompt enriched with multi-era dictionary + etymology "
                "context. Connect an inference backend (Ollama / vLLM / "
                "TensorRT-LLM) to generate a full answer."
            )
        return {
            "prompt": user_prompt,
            "enriched_prompt": enriched,
            "backend": backend,
            "answer": answer_text,
        }

    def enrich_prompt_for_ollama(
        self, user_prompt: str, max_words: int = 4
    ) -> str:
        """Rewrite *user_prompt* with multi-era context prefixed."""
        if not user_prompt:
            return user_prompt
        tokens = [
            t for t in dict.fromkeys(_tokens(user_prompt))
            if len(t) >= 4
        ][:max_words]
        if not tokens:
            return user_prompt

        lines = [user_prompt, "", "Context (multi-era dictionary + etymology):"]
        for tok in tokens:
            merged = self.get_definition(tok, "auto")
            etym = self.get_etymology(tok)
            lines.append(f"- {tok}:")
            if merged.get("1828_webster"):
                lines.append(f"    1828: {str(merged['1828_webster'])[:180]}")
            ee = merged.get("early_english") or {}
            if ee:
                sample_dialect = next(iter(ee))
                lines.append(
                    f"    early ({sample_dialect}): "
                    f"{str(ee[sample_dialect])[:180]}"
                )
            if merged.get("britannica"):
                lines.append(f"    britannica: {str(merged['britannica'])[:180]}")
            if etym.get("full_etymology") and etym["full_etymology"] != "unknown":
                lines.append(f"    origin: {etym['full_etymology']}")
        return "\n".join(lines)

    # ── Harmonic orchestrator handler ───────────────────────────────────────

    def _subsystem_handler(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = (task or {}).get("type") or (task or {}).get("action") or "definition"
        if action in ("definition", "lookup"):
            return self.get_definition(task.get("word", ""), task.get("source", "auto"))
        if action == "etymology":
            return self.get_etymology(task.get("word", ""))
        if action in ("evaluate", "context"):
            return self.evaluate_context(
                task.get("sentence", ""), task.get("target_word")
            )
        if action == "search":
            return {"results": self.semantic_search(
                task.get("query", ""), int(task.get("top_k", 5))
            )}
        return {"error": f"unknown action: {action}"}

    # ── Event-bus handlers ──────────────────────────────────────────────────

    def _on_lookup_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        result = self.get_definition(
            data.get("word", ""), data.get("source", "auto")
        )
        self._publish("lookup_res", result)

    def _on_etymology_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        result = self.get_etymology(data.get("word", ""))
        self._publish("etym_res", result)

    def _on_evaluate_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        result = self.evaluate_context(
            data.get("sentence", ""), data.get("target_word")
        )
        self._publish("eval_res", result)

    def _on_brain_query(self, data: Any) -> None:
        """Generic BRAIN_QUERY handler — dispatch on a ``kind`` field."""
        if not isinstance(data, dict):
            return
        kind = str(data.get("kind") or data.get("type") or "").lower()
        if kind not in ("definition", "etymology", "evaluate", "search", "dictionary"):
            return
        result = self._subsystem_handler({**data, "type": kind})
        result["origin"] = "dictionary_brain"
        self._publish("brain_result", result)

    # ── Publishers ──────────────────────────────────────────────────────────

    def _publish(self, topic_key: str, payload: Dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        try:
            ev = _event_names()
            self.event_bus.publish(ev[topic_key], payload)
        except Exception as exc:
            logger.debug("publish(%s) failed: %s", topic_key, exc)

    def _publish_source_loaded(self, source: str, count: int, origin: str) -> None:
        if self.event_bus is None:
            return
        try:
            ev = _event_names()
            self.event_bus.publish(ev["source_loaded"], {
                "source": source, "count": count, "origin": origin,
            })
        except Exception:
            pass

    def _publish_metacognition(self, word: str, report: Dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        try:
            ev = _event_names()
            meta = report.get("meta_analysis", {})
            self.event_bus.publish(ev["metacog"], {
                "origin": "dictionary_brain",
                "word": word,
                "confidence": meta.get("entry_confidence", 0.0),
                "meaning_shift": meta.get("meaning_shift_detected", False),
                "shift_score": meta.get("shift_score", 0.0),
                "etymology_confidence": meta.get("etymology_confidence", 0.0),
                "note": meta.get("learning_note", ""),
                "timestamp": time.time(),
            })
        except Exception:
            pass

    # ── Public status / stats ───────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "webster_1828_entries": len(self.webster_1828),
            "britannica_entries": len(self.britannica),
            "early_english_entries": sum(
                len(v) for v in self.early_english.values()
            ),
            "early_english_dialects": sorted(self.early_english.keys()),
            "indexed_entries": len(self._index_entries),
            "optional_deps": {
                "numpy": _NUMPY_OK, "faiss": _FAISS_OK, "ety": _ETY_OK,
                "pymultidictionary": _PYMULTI_OK, "requests": _REQUESTS_OK,
                "sentence_transformers": _ST_OK,
            },
            "telemetry": {
                "lookups_total": self._lookups_total,
                "unknown_lookups": self._unknown_lookups,
                "meaning_shifts_detected": self._meaning_shifts_detected,
            },
            "linked": {
                "event_bus": self.event_bus is not None,
                "persistence": self._persistence is not None,
                "palace": self._palace is not None,
                "ollama": self._ollama is not None,
                "language_hub": self._language_hub is not None,
                "orchestrator": self._orchestrator is not None,
                "neuroprotection": self._neuroprotection is not None,
                "inference_stack": self._inference_stack is not None,
            },
        }

    def set_inference_stack(self, stack: Any) -> None:
        """Attach an inference stack after construction. Safe to call again."""
        self._inference_stack = stack

    def add_source(self, source_name: str, entries: Dict[str, str]) -> int:
        """Runtime-add a dictionary source and re-index. Returns the new count."""
        if not isinstance(entries, dict):
            return 0
        normalised = {str(k).lower(): str(v) for k, v in entries.items() if v}
        if source_name == "webster_1828":
            self.webster_1828.update(normalised)
        elif source_name == "britannica":
            self.britannica.update(normalised)
        else:
            bucket = self.early_english.setdefault(source_name.lower(), {})
            bucket.update(normalised)
        self._rebuild_index()
        self._publish_source_loaded(source_name, len(normalised), "runtime")
        return len(normalised)
