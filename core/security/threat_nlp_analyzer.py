"""
Kingdom AI — Threat NLP Analyzer
SOTA 2026: DistilBERT hostile intent classification + coercion pattern detection.

Analyzes transcribed ambient speech for:
  - Hostile intent (threats, demands, intimidation)
  - Coercion patterns ("do this or else", "give me access")
  - Extortion language
  - Social engineering attempts

Uses HuggingFace transformers (sentiment/zero-shot) when available,
falls back to keyword/pattern matching.
Dormant until protection flag "threat_nlp" is activated.
"""
import logging
import re
import threading
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from base_component import BaseComponent

logger = logging.getLogger(__name__)

HAS_TRANSFORMERS = False
try:
    import os as _os
    _os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    _os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    _os.environ.setdefault("USE_TF", "0")
    _os.environ.setdefault("USE_TORCH", "1")
    from transformers import pipeline as hf_pipeline
    HAS_TRANSFORMERS = True
    logger.info("transformers pipeline available (DistilBERT threat classification enabled)")
except (ImportError, RuntimeError, OSError) as _e:
    logger.debug("transformers pipeline not available (fallback to keyword matching): %s", _e)

# Keyword-based threat patterns (fallback when transformers unavailable)
THREAT_KEYWORDS = {
    "high": [
        r"\b(kill|murder|shoot|stab|hurt)\b.*\b(you|him|her|them)\b",
        r"\b(give me|hand over)\b.*\b(money|wallet|keys|access|password)\b",
        r"\b(shut.*down|destroy|delete|wipe)\b.*\b(system|everything|data)\b",
        r"\b(bomb|weapon|gun|knife)\b",
        r"\bor\s+(i('ll|will)|we('ll|will))\s+(kill|hurt|destroy)\b",
    ],
    "medium": [
        r"\b(threat|threaten|warn|warning)\b",
        r"\b(force|coerce|make\s+you|compel)\b",
        r"\b(ransom|extort|blackmail)\b",
        r"\b(shut\s*(it|up)|don't\s*move|freeze|hands\s*up)\b",
        r"\b(hack|breach|compromise|infiltrate)\b.*\b(system|account|wallet)\b",
        r"\b(or\s+else|consequences|regret)\b",
    ],
    "low": [
        r"\b(suspicious|weird|strange)\b.*\b(person|people|activity)\b",
        r"\b(break\s*in|intrude|trespass)\b",
        r"\b(steal|rob|theft)\b",
        r"\b(angry|furious|rage)\b",
    ],
}

# Coercion patterns
COERCION_PATTERNS = [
    r"\b(do\s+(what|as)\s+i\s+say)\b",
    r"\b(transfer|send|move)\b.*\b(all|everything|money|crypto|bitcoin)\b",
    r"\b(give\s+me\s+access|unlock|open\s+it)\b",
    r"\b(don't\s+(call|contact|tell)\s+(anyone|police|cops))\b",
    r"\b(if\s+you\s+(don't|refuse|won't))\b.*\b(i('ll|will))\b",
    r"\b(nobody\s+(has\s+to|needs\s+to)\s+(get\s+hurt|know))\b",
    r"\b(your\s+family|your\s+children|your\s+kids)\b.*\b(danger|hurt|harm)\b",
]

# Zero-shot classification labels
ZERO_SHOT_LABELS = [
    "threat or intimidation",
    "coercion or extortion",
    "normal conversation",
    "requesting help",
    "greeting or small talk",
]


class ThreatNLPAnalyzer(BaseComponent):
    """
    Natural Language Processing analyzer for detecting hostile intent
    in ambient transcribed speech.

    Receives transcription segments from AmbientTranscriber and evaluates
    them for threat indicators. Results feed into CreatorShield.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # ML pipeline (loaded lazily)
        self._classifier = None
        self._zero_shot = None

        # Compiled regex patterns
        self._threat_patterns: Dict[str, List[re.Pattern]] = {}
        self._coercion_patterns: List[re.Pattern] = []
        self._compile_patterns()

        # Analysis history
        self._analysis_history: deque = deque(maxlen=200)
        self._lock = threading.Lock()

        self._subscribe_events()
        self._initialized = True
        logger.info("ThreatNLPAnalyzer initialized (transformers=%s)", HAS_TRANSFORMERS)

    def _compile_patterns(self) -> None:
        for severity, patterns in THREAT_KEYWORDS.items():
            self._threat_patterns[severity] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
        self._coercion_patterns = [
            re.compile(p, re.IGNORECASE) for p in COERCION_PATTERNS
        ]

    # ------------------------------------------------------------------
    # ML model loading
    # ------------------------------------------------------------------

    def _ensure_classifier(self) -> bool:
        if self._classifier is not None:
            return True
        if not HAS_TRANSFORMERS:
            return False
        try:
            self._classifier = hf_pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1,  # CPU
            )
            logger.info("Sentiment classifier loaded (DistilBERT)")
            return True
        except Exception as e:
            logger.warning("Classifier load failed: %s", e)
            return False

    def _ensure_zero_shot(self) -> bool:
        if self._zero_shot is not None:
            return True
        if not HAS_TRANSFORMERS:
            return False
        try:
            self._zero_shot = hf_pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=-1,
            )
            logger.info("Zero-shot classifier loaded (BART-MNLI)")
            return True
        except Exception as e:
            logger.debug("Zero-shot load failed (optional): %s", e)
            return False

    # ------------------------------------------------------------------
    # Text analysis
    # ------------------------------------------------------------------

    def analyze_text(self, text: str, speaker: str = "unknown") -> Dict[str, Any]:
        """
        Analyze text for hostile intent and coercion.

        Returns:
            Dict with keys: is_threat, is_coercion, severity, confidence,
            details, matched_patterns
        """
        if not self._is_active():
            return {"is_threat": False, "is_coercion": False, "severity": "none"}

        if not text or len(text.strip()) < 3:
            return {"is_threat": False, "is_coercion": False, "severity": "none"}

        result: Dict[str, Any] = {
            "text": text[:200],
            "speaker": speaker,
            "is_threat": False,
            "is_coercion": False,
            "severity": "none",
            "confidence": 0.0,
            "details": [],
            "matched_patterns": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 1. Keyword/pattern matching (always available)
        pattern_result = self._pattern_match(text)
        if pattern_result["is_threat"]:
            result.update(pattern_result)

        coercion_result = self._coercion_match(text)
        if coercion_result["is_coercion"]:
            result["is_coercion"] = True
            result["matched_patterns"].extend(coercion_result.get("matched_patterns", []))
            if not result["is_threat"]:
                result["is_threat"] = True
                result["severity"] = "high"
                result["confidence"] = max(result["confidence"], 0.7)
            result["details"].append("Coercion pattern detected")

        # 2. ML classification (if available)
        if self._ensure_classifier():
            ml_result = self._ml_classify(text)
            # Combine ML and pattern results
            if ml_result.get("negative_sentiment", 0) > 0.85:
                result["confidence"] = max(result["confidence"], ml_result["negative_sentiment"] * 0.6)
                result["details"].append(f"Negative sentiment: {ml_result['negative_sentiment']:.2f}")

        # 3. Zero-shot classification (if available)
        if result["is_threat"] and self._ensure_zero_shot():
            zs_result = self._zero_shot_classify(text)
            if zs_result:
                result["details"].append(f"Zero-shot: {zs_result}")

        # Record and publish if threat detected
        if result["is_threat"] or result["is_coercion"]:
            self._record_analysis(result)
            self._publish_threat(result)

        return result

    def _pattern_match(self, text: str) -> Dict[str, Any]:
        """Match text against threat keyword patterns."""
        result: Dict[str, Any] = {
            "is_threat": False,
            "severity": "none",
            "confidence": 0.0,
            "matched_patterns": [],
            "details": [],
        }

        for severity in ("high", "medium", "low"):
            for pattern in self._threat_patterns.get(severity, []):
                match = pattern.search(text)
                if match:
                    result["is_threat"] = True
                    result["severity"] = severity
                    result["matched_patterns"].append(match.group())
                    conf_map = {"high": 0.85, "medium": 0.6, "low": 0.4}
                    result["confidence"] = max(result["confidence"], conf_map.get(severity, 0.3))
                    result["details"].append(f"Keyword match ({severity}): {match.group()}")
                    if severity == "high":
                        return result  # High severity — no need to keep searching

        return result

    def _coercion_match(self, text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"is_coercion": False, "matched_patterns": []}
        for pattern in self._coercion_patterns:
            match = pattern.search(text)
            if match:
                result["is_coercion"] = True
                result["matched_patterns"].append(match.group())
        return result

    def _ml_classify(self, text: str) -> Dict[str, float]:
        """Run sentiment classification."""
        try:
            result = self._classifier(text[:512])[0]
            label = result.get("label", "").upper()
            score = result.get("score", 0)
            return {
                "label": label,
                "score": score,
                "negative_sentiment": score if label == "NEGATIVE" else 1 - score,
            }
        except Exception as e:
            logger.debug("ML classify error: %s", e)
            return {"negative_sentiment": 0}

    def _zero_shot_classify(self, text: str) -> Optional[str]:
        """Run zero-shot classification for threat type."""
        try:
            result = self._zero_shot(text[:512], ZERO_SHOT_LABELS, multi_label=False)
            top_label = result["labels"][0]
            top_score = result["scores"][0]
            if top_label in ("threat or intimidation", "coercion or extortion") and top_score > 0.5:
                return f"{top_label} ({top_score:.2f})"
            return None
        except Exception as e:
            logger.debug("Zero-shot error: %s", e)
            return None

    # ------------------------------------------------------------------
    # Detection management
    # ------------------------------------------------------------------

    def _record_analysis(self, result: Dict) -> None:
        with self._lock:
            self._analysis_history.append(result)

    def _publish_threat(self, result: Dict) -> None:
        if not self.event_bus:
            return

        if result.get("is_coercion"):
            self.event_bus.publish("security.nlp.coercion", result)

        severity = result.get("severity", "none")
        if severity in ("high", "medium"):
            self.event_bus.publish("security.nlp.hostile_intent", result)

        logger.info(
            "NLP threat detected: severity=%s, coercion=%s, conf=%.2f, text='%s'",
            severity, result.get("is_coercion"), result.get("confidence", 0),
            result.get("text", "")[:80],
        )

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("threat_nlp")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("security.nlp.analyze_text", self._handle_analyze)
        self.event_bus.subscribe("security.transcription.segment", self._handle_transcript)

    def _handle_analyze(self, data: Any) -> None:
        if isinstance(data, dict):
            text = data.get("text", "")
            speaker = data.get("speaker", "unknown")
            self.analyze_text(text, speaker)

    def _handle_transcript(self, data: Any) -> None:
        if isinstance(data, dict):
            text = data.get("text", "")
            speaker = data.get("speaker", "unknown")
            if text:
                self.analyze_text(text, speaker)

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "transformers_available": HAS_TRANSFORMERS,
            "classifier_loaded": self._classifier is not None,
            "zero_shot_loaded": self._zero_shot is not None,
            "analysis_count": len(self._analysis_history),
        }
