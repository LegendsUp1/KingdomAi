"""
Ollama Intelligent Model Orchestrator — SOTA 2026
==================================================

AI-powered model routing with VRAM-aware scheduling across dual GPUs.
Based on SOTA 2026 research: Eagle (training-free routing), LLMRouterBench,
and Ollama's new model scheduling with exact memory measurement.

Capabilities:
1. Model Registry   — knows every model's strengths, VRAM cost, speed tier
2. VRAM Manager     — tracks real-time GPU memory across RTX 4060 + RTX 3050
3. Task Router      — selects optimal model for each domain/task automatically
4. Dynamic Loader   — preloads/unloads models based on active system needs
5. Event Integration— listens for tab switches to pre-warm the right model
6. Usage Tracker    — learns which models are used most, keeps them hot

Usage:
    from core.ollama_gateway import orchestrator, get_ollama_url

    # Get the best model for a task (automatically loads it if needed)
    model = await orchestrator.get_model_for_task("trading")

    # Or let the orchestrator build the full payload
    model, options = await orchestrator.prepare_request("creation", num_predict=2048)

    # Pre-warm for a tab switch
    orchestrator.on_tab_switched("trading")
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from urllib.parse import urlencode
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

logger = logging.getLogger("KingdomAI.OllamaOrchestrator")


# ─── Ollama Environment Configuration ────────────────────────────────

_OLLAMA_ENV_DEFAULTS = {
    "OLLAMA_NUM_PARALLEL": "4",
    "OLLAMA_MAX_LOADED_MODELS": "3",
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
    "OLLAMA_MAX_QUEUE": "512",
}

def configure_ollama_env():
    applied = []
    for key, default in _OLLAMA_ENV_DEFAULTS.items():
        if key not in os.environ:
            os.environ[key] = default
            applied.append(f"{key}={default}")
    if applied:
        logger.info(f"🔧 Ollama env: {', '.join(applied)}")


def get_ollama_url() -> str:
    return os.environ.get(
        "KINGDOM_OLLAMA_BASE_URL", "http://localhost:11434"
    ).strip().rstrip("/")


OPTIMAL_OPTIONS = {"num_gpu": 999, "num_batch": 512}


def get_optimal_options(
    temperature: float = 0.7,
    num_predict: int = 500,
    num_ctx: int = 4096,
    extra: dict | None = None,
) -> dict:
    opts = {**OPTIMAL_OPTIONS, "temperature": temperature,
            "num_predict": num_predict, "num_ctx": num_ctx}
    if extra:
        opts.update(extra)
    return opts


configure_ollama_env()


def _is_truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def get_google_tpu_runtime_settings(api_key_manager: Any = None) -> Dict[str, Any]:
    """Resolve Google TPU/Vertex runtime settings from env + config + key store."""
    settings: Dict[str, Any] = {
        "enabled": False,
        "endpoint": "",
        "model": "gemini-2.0-flash",
        "project_id": "",
        "location": "us-central1",
        "api_key": "",
        "use_adc": True,
        "timeout_seconds": 120,
    }

    # 1) Environment variables (highest priority, supports WSL/systemd services)
    settings["enabled"] = _is_truthy(os.environ.get("KINGDOM_GOOGLE_TPU_ENABLED", "0"))
    settings["endpoint"] = str(os.environ.get("KINGDOM_GOOGLE_TPU_ENDPOINT", "")).strip()
    settings["model"] = str(os.environ.get("KINGDOM_GOOGLE_TPU_MODEL", settings["model"])).strip() or settings["model"]
    settings["project_id"] = str(os.environ.get("GOOGLE_CLOUD_PROJECT", "")).strip()
    settings["location"] = str(os.environ.get("GOOGLE_CLOUD_LOCATION", settings["location"])).strip() or settings["location"]
    settings["api_key"] = str(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("KINGDOM_GOOGLE_API_KEY")
        or ""
    ).strip()
    if "KINGDOM_GOOGLE_USE_ADC" in os.environ:
        settings["use_adc"] = _is_truthy(os.environ.get("KINGDOM_GOOGLE_USE_ADC", "1"))
    if "KINGDOM_GOOGLE_TPU_TIMEOUT" in os.environ:
        try:
            settings["timeout_seconds"] = max(5, int(float(os.environ.get("KINGDOM_GOOGLE_TPU_TIMEOUT", "120"))))
        except Exception:
            pass

    # 2) thoth_ai_config.json google_tpu block
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "thoth_ai_config.json"
        if cfg_path.exists():
            with cfg_path.open("r", encoding="utf-8") as fh:
                cfg_data = json.load(fh)
            tpu_cfg = cfg_data.get("google_tpu", {}) if isinstance(cfg_data, dict) else {}
            if isinstance(tpu_cfg, dict):
                settings["enabled"] = bool(tpu_cfg.get("enabled", settings["enabled"]))
                settings["endpoint"] = str(tpu_cfg.get("endpoint", settings["endpoint"])).strip() or settings["endpoint"]
                settings["model"] = str(tpu_cfg.get("model", settings["model"])).strip() or settings["model"]
                settings["project_id"] = str(tpu_cfg.get("project_id", settings["project_id"])).strip() or settings["project_id"]
                settings["location"] = str(tpu_cfg.get("location", settings["location"])).strip() or settings["location"]
                settings["api_key"] = str(tpu_cfg.get("api_key", settings["api_key"])).strip() or settings["api_key"]
                if "use_adc" in tpu_cfg:
                    settings["use_adc"] = bool(tpu_cfg.get("use_adc"))
                if "timeout_seconds" in tpu_cfg:
                    try:
                        settings["timeout_seconds"] = max(5, int(float(tpu_cfg.get("timeout_seconds"))))
                    except Exception:
                        pass
    except Exception:
        pass

    # 3) APIKeyManager services (google_tpu/google/gcp/vertex_ai)
    try:
        if api_key_manager is None:
            from core.api_key_manager import APIKeyManager
            api_key_manager = APIKeyManager.get_instance()
        for service_name in ("google_tpu", "google", "gcp", "vertex_ai"):
            service = {}
            try:
                service = api_key_manager.get_api_key(service_name) or {}
            except Exception:
                service = {}
            if not isinstance(service, dict) or not service:
                continue
            settings["api_key"] = str(
                service.get("api_key")
                or service.get("key")
                or service.get("google_api_key")
                or settings["api_key"]
            ).strip() or settings["api_key"]
            settings["project_id"] = str(service.get("project_id") or settings["project_id"]).strip() or settings["project_id"]
            settings["location"] = str(service.get("location") or service.get("region") or settings["location"]).strip() or settings["location"]
            endpoint = str(service.get("endpoint") or service.get("inference_url") or service.get("url") or "").strip()
            if endpoint:
                settings["endpoint"] = endpoint
            if "enabled" in service:
                settings["enabled"] = bool(service.get("enabled"))
            if "use_adc" in service:
                settings["use_adc"] = bool(service.get("use_adc"))
    except Exception:
        pass

    # Auto-enable when endpoint is configured and auth exists.
    if settings["endpoint"] and (settings["api_key"] or settings["use_adc"]):
        settings["enabled"] = True
    return settings


def get_google_access_token(scopes: Optional[List[str]] = None) -> Optional[str]:
    """Get ADC OAuth token for Google Cloud APIs."""
    try:
        import google.auth
        from google.auth.transport.requests import Request as GoogleAuthRequest

        creds, _project = google.auth.default(
            scopes=scopes or ["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(GoogleAuthRequest())
        return str(getattr(creds, "token", "") or "").strip() or None
    except Exception:
        return None


def _extract_text_from_google_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""
    if isinstance(payload.get("response"), str):
        return payload.get("response", "")
    if isinstance(payload.get("text"), str):
        return payload.get("text", "")
    predictions = payload.get("predictions")
    if isinstance(predictions, list) and predictions:
        first = predictions[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("content", "output_text", "response", "text"):
                if isinstance(first.get(key), str):
                    return first.get(key, "")
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            content = first.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    for part in parts:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            return part["text"]
    return ""


async def query_google_tpu_inference(
    prompt: str,
    task: str = "trading",
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    api_key_manager: Any = None,
) -> Optional[Dict[str, Any]]:
    """Call a configured Google TPU/Vertex inference endpoint."""
    settings = get_google_tpu_runtime_settings(api_key_manager=api_key_manager)
    if not settings.get("enabled") or not settings.get("endpoint"):
        return None

    endpoint = str(settings["endpoint"]).strip()
    timeout_seconds = int(settings.get("timeout_seconds", 120) or 120)
    model_name = str(model or settings.get("model") or "gemini-2.0-flash")
    ctx = context or {}

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    params: Dict[str, str] = {}
    if settings.get("use_adc", True):
        token = get_google_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    if settings.get("api_key"):
        # Keep both formats for compatibility with Gateway + direct Vertex key auth.
        headers.setdefault("x-goog-api-key", str(settings["api_key"]))
        params.setdefault("key", str(settings["api_key"]))

    is_vertex_predict = (
        "aiplatform.googleapis.com" in endpoint and
        "/endpoints/" in endpoint and
        endpoint.rstrip("/").endswith(":predict")
    )
    if is_vertex_predict:
        payload: Dict[str, Any] = {
            "instances": [{
                "prompt": prompt,
                "task": task,
                "model": model_name,
                "context": ctx,
            }],
            "parameters": {"temperature": 0.2},
        }
    else:
        payload = {
            "prompt": prompt,
            "task": task,
            "model": model_name,
            "context": ctx,
        }

    try:
        import aiohttp

        url = endpoint
        if params:
            separator = "&" if "?" in endpoint else "?"
            url = f"{endpoint}{separator}{urlencode(params)}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as response:
                text_body = await response.text()
                try:
                    data = json.loads(text_body) if text_body else {}
                except Exception:
                    data = {"raw_text": text_body}
                if response.status >= 400:
                    return {
                        "ok": False,
                        "status": response.status,
                        "backend": "google_tpu",
                        "error": data or text_body,
                    }
                return {
                    "ok": True,
                    "status": response.status,
                    "backend": "google_tpu",
                    "data": data,
                    "text": _extract_text_from_google_payload(data),
                }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "backend": "google_tpu",
            "error": str(e),
        }


# ─── Model Capability Definitions ────────────────────────────────────

class SpeedTier(Enum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


class ModelCapability(Enum):
    GENERAL = "general"
    CODE = "code"
    MATH = "math"
    VISION = "vision"
    OCR = "ocr"
    REASONING = "reasoning"
    CREATIVE = "creative"
    FINANCIAL = "financial"
    TRANSLATION = "translation"
    EMBEDDING = "embedding"
    LIGHTWEIGHT = "lightweight"


@dataclass
class ModelProfile:
    name: str
    vram_mb: int
    capabilities: Set[ModelCapability]
    speed_tier: SpeedTier
    quality_score: float  # 0-1, higher = better quality output
    is_cloud: bool = False
    param_size: str = ""
    notes: str = ""


# ─── Model Registry ──────────────────────────────────────────────────
# Every model Kingdom AI can use, with its real VRAM cost and strengths.
# VRAM sizes measured from actual ollama ps output on this hardware.

MODEL_REGISTRY: Dict[str, ModelProfile] = {
    # ── LOCAL MODELS (need VRAM) ──────────────────────────────────
    "mistral-nemo:latest": ModelProfile(
        name="mistral-nemo:latest",
        vram_mb=10000,
        capabilities={
            ModelCapability.GENERAL, ModelCapability.CODE,
            ModelCapability.REASONING, ModelCapability.CREATIVE,
            ModelCapability.FINANCIAL,
        },
        speed_tier=SpeedTier.MEDIUM,
        quality_score=0.92,
        param_size="12.2B",
        notes="Best all-rounder. Spans both GPUs. Primary brain.",
    ),
    "cogito:latest": ModelProfile(
        name="cogito:latest",
        vram_mb=5500,
        capabilities={
            ModelCapability.GENERAL, ModelCapability.CODE,
            ModelCapability.REASONING,
        },
        speed_tier=SpeedTier.MEDIUM,
        quality_score=0.85,
        param_size="8B",
        notes="Strong code and reasoning. Fits single GPU.",
    ),
    "phi4-mini:latest": ModelProfile(
        name="phi4-mini:latest",
        vram_mb=4100,
        capabilities={
            ModelCapability.GENERAL, ModelCapability.CODE,
            ModelCapability.LIGHTWEIGHT,
        },
        speed_tier=SpeedTier.FAST,
        quality_score=0.75,
        param_size="3.8B",
        notes="Fast responses, good code. Ideal for voice/quick tasks.",
    ),
    "llava:latest": ModelProfile(
        name="llava:latest",
        vram_mb=5000,
        capabilities={ModelCapability.VISION, ModelCapability.GENERAL},
        speed_tier=SpeedTier.MEDIUM,
        quality_score=0.80,
        param_size="7B",
        notes="Vision model. Required when images need to be understood.",
    ),
    "deepseek-ocr:latest": ModelProfile(
        name="deepseek-ocr:latest",
        vram_mb=7000,
        capabilities={ModelCapability.VISION, ModelCapability.OCR},
        speed_tier=SpeedTier.SLOW,
        quality_score=0.82,
        param_size="7B",
        notes="OCR specialist. Use for text extraction from images.",
    ),
    "wizard-math:latest": ModelProfile(
        name="wizard-math:latest",
        vram_mb=4500,
        capabilities={ModelCapability.MATH, ModelCapability.REASONING},
        speed_tier=SpeedTier.MEDIUM,
        quality_score=0.88,
        param_size="7B",
        notes="Math specialist. Best for calculations and formulas.",
    ),
    "qwen2-math:latest": ModelProfile(
        name="qwen2-math:latest",
        vram_mb=4800,
        capabilities={ModelCapability.MATH, ModelCapability.REASONING},
        speed_tier=SpeedTier.MEDIUM,
        quality_score=0.87,
        param_size="7B",
        notes="Math specialist. Strong quantitative reasoning.",
    ),
    "mathstral:latest": ModelProfile(
        name="mathstral:latest",
        vram_mb=4500,
        capabilities={ModelCapability.MATH, ModelCapability.REASONING},
        speed_tier=SpeedTier.MEDIUM,
        quality_score=0.86,
        param_size="7B",
        notes="Math specialist from Mistral family.",
    ),
    "olmo-3:latest": ModelProfile(
        name="olmo-3:latest",
        vram_mb=5000,
        capabilities={ModelCapability.GENERAL, ModelCapability.REASONING},
        speed_tier=SpeedTier.MEDIUM,
        quality_score=0.78,
        param_size="7B",
    ),
    "tinyllama:latest": ModelProfile(
        name="tinyllama:latest",
        vram_mb=700,
        capabilities={ModelCapability.GENERAL, ModelCapability.LIGHTWEIGHT},
        speed_tier=SpeedTier.FAST,
        quality_score=0.50,
        param_size="1.1B",
        notes="Ultra-fast. Basic tasks only. Can co-exist with bigger models.",
    ),
    "gemma:2b": ModelProfile(
        name="gemma:2b",
        vram_mb=2000,
        capabilities={ModelCapability.GENERAL, ModelCapability.LIGHTWEIGHT},
        speed_tier=SpeedTier.FAST,
        quality_score=0.58,
        param_size="2B",
        notes="Small and fast. Good for classification/routing.",
    ),
    "translategemma:latest": ModelProfile(
        name="translategemma:latest",
        vram_mb=3500,
        capabilities={ModelCapability.TRANSLATION},
        speed_tier=SpeedTier.FAST,
        quality_score=0.80,
        param_size="3B",
        notes="Translation specialist.",
    ),
    "nomic-embed-text:latest": ModelProfile(
        name="nomic-embed-text:latest",
        vram_mb=300,
        capabilities={ModelCapability.EMBEDDING},
        speed_tier=SpeedTier.FAST,
        quality_score=0.75,
        param_size="137M",
        notes="Text embeddings. Tiny VRAM footprint.",
    ),
    "functiongemma:latest": ModelProfile(
        name="functiongemma:latest",
        vram_mb=350,
        capabilities={ModelCapability.CODE, ModelCapability.LIGHTWEIGHT},
        speed_tier=SpeedTier.FAST,
        quality_score=0.55,
        param_size="300M",
    ),
    "devstral-small-2:latest": ModelProfile(
        name="devstral-small-2:latest",
        vram_mb=16000,
        capabilities={ModelCapability.CODE, ModelCapability.REASONING},
        speed_tier=SpeedTier.SLOW,
        quality_score=0.93,
        param_size="24B",
        notes="Too large for both GPUs combined. Use cloud version instead.",
    ),

    # ── CLOUD MODELS (no VRAM cost) ──────────────────────────────
    "deepseek-v3.1:671b-cloud": ModelProfile(
        name="deepseek-v3.1:671b-cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.CODE,
                      ModelCapability.REASONING, ModelCapability.MATH,
                      ModelCapability.CREATIVE, ModelCapability.FINANCIAL},
        speed_tier=SpeedTier.MEDIUM, quality_score=0.97, param_size="671B",
    ),
    "deepseek-v3.2:cloud": ModelProfile(
        name="deepseek-v3.2:cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.CODE,
                      ModelCapability.REASONING, ModelCapability.CREATIVE},
        speed_tier=SpeedTier.MEDIUM, quality_score=0.98, param_size="671B",
    ),
    "qwen3-coder:480b-cloud": ModelProfile(
        name="qwen3-coder:480b-cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.CODE, ModelCapability.REASONING},
        speed_tier=SpeedTier.MEDIUM, quality_score=0.96, param_size="480B",
    ),
    "gpt-oss:120b-cloud": ModelProfile(
        name="gpt-oss:120b-cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.CODE,
                      ModelCapability.REASONING},
        speed_tier=SpeedTier.MEDIUM, quality_score=0.94, param_size="120B",
    ),
    "kimi-k2:1t-cloud": ModelProfile(
        name="kimi-k2:1t-cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.REASONING,
                      ModelCapability.FINANCIAL},
        speed_tier=SpeedTier.SLOW, quality_score=0.96, param_size="1T",
    ),
    "qwen3-vl:235b-cloud": ModelProfile(
        name="qwen3-vl:235b-cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.VISION, ModelCapability.GENERAL},
        speed_tier=SpeedTier.MEDIUM, quality_score=0.95, param_size="235B",
    ),
    "glm-4.6:cloud": ModelProfile(
        name="glm-4.6:cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.CODE},
        speed_tier=SpeedTier.FAST, quality_score=0.88, param_size="9B",
    ),
    "glm-4.7:cloud": ModelProfile(
        name="glm-4.7:cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.CODE},
        speed_tier=SpeedTier.FAST, quality_score=0.90, param_size="9B",
    ),
    "kimi-k2-thinking:cloud": ModelProfile(
        name="kimi-k2-thinking:cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.REASONING, ModelCapability.GENERAL},
        speed_tier=SpeedTier.SLOW, quality_score=0.97, param_size="1T",
    ),
    "minimax-m2:cloud": ModelProfile(
        name="minimax-m2:cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.CREATIVE},
        speed_tier=SpeedTier.MEDIUM, quality_score=0.90, param_size="",
    ),
    "devstral-small-2:24b-cloud": ModelProfile(
        name="devstral-small-2:24b-cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.CODE, ModelCapability.REASONING},
        speed_tier=SpeedTier.MEDIUM, quality_score=0.93, param_size="24B",
    ),
    "nemotron-3-nano:30b-cloud": ModelProfile(
        name="nemotron-3-nano:30b-cloud", vram_mb=0, is_cloud=True,
        capabilities={ModelCapability.GENERAL, ModelCapability.CODE},
        speed_tier=SpeedTier.FAST, quality_score=0.85, param_size="30B",
    ),
}


# ─── Task-to-Capability Mapping ──────────────────────────────────────
# Maps each Kingdom AI domain/tab to the capabilities it needs,
# ordered by priority.  The orchestrator scores models against these.

TASK_REQUIREMENTS: Dict[str, List[ModelCapability]] = {
    "trading": [
        ModelCapability.FINANCIAL, ModelCapability.REASONING,
        ModelCapability.MATH, ModelCapability.GENERAL,
    ],
    "mining": [
        ModelCapability.GENERAL, ModelCapability.REASONING,
        ModelCapability.CODE,
    ],
    "wallet": [
        ModelCapability.GENERAL, ModelCapability.FINANCIAL,
        ModelCapability.REASONING,
    ],
    "creation": [
        ModelCapability.CREATIVE, ModelCapability.REASONING,
        ModelCapability.GENERAL,
    ],
    "creative_studio": [
        ModelCapability.CREATIVE, ModelCapability.REASONING,
        ModelCapability.VISION, ModelCapability.GENERAL,
    ],
    "cad": [
        ModelCapability.CREATIVE, ModelCapability.REASONING,
        ModelCapability.GENERAL,
    ],
    "code": [
        ModelCapability.CODE, ModelCapability.REASONING,
        ModelCapability.GENERAL,
    ],
    "thoth_ai": [
        ModelCapability.GENERAL, ModelCapability.REASONING,
        ModelCapability.CODE, ModelCapability.CREATIVE,
    ],
    "voice": [
        ModelCapability.GENERAL, ModelCapability.LIGHTWEIGHT,
    ],
    "math": [
        ModelCapability.MATH, ModelCapability.REASONING,
    ],
    "vision": [
        ModelCapability.VISION, ModelCapability.GENERAL,
    ],
    "ocr": [
        ModelCapability.OCR, ModelCapability.VISION,
    ],
    "translation": [
        ModelCapability.TRANSLATION, ModelCapability.GENERAL,
    ],
    "embedding": [
        ModelCapability.EMBEDDING,
    ],
    "vr": [
        ModelCapability.CREATIVE, ModelCapability.VISION,
        ModelCapability.GENERAL,
    ],
    "system": [
        ModelCapability.GENERAL, ModelCapability.CODE,
    ],
    "comms": [
        ModelCapability.GENERAL, ModelCapability.REASONING,
    ],
    "kaig": [
        ModelCapability.FINANCIAL, ModelCapability.REASONING,
        ModelCapability.MATH, ModelCapability.GENERAL,
    ],
    "devices": [
        ModelCapability.CODE, ModelCapability.REASONING,
        ModelCapability.GENERAL,
    ],
    "general": [
        ModelCapability.GENERAL, ModelCapability.REASONING,
    ],
}

# Tab ID → task domain mapping
TAB_TO_DOMAIN: Dict[str, str] = {
    "trading": "trading",
    "mining": "mining",
    "wallet": "wallet",
    "thoth_ai": "thoth_ai",
    "creative_studio": "creative_studio",
    "creation": "creation",
    "vr": "vr",
    "comms": "comms",
    "communications": "comms",
    "code": "code",
    "system": "system",
    "kaig": "kaig",
    "$kaig": "kaig",
    "kaig_tab": "kaig",
    "devices": "devices",
    "device_manager": "devices",
}

# Total usable VRAM across both GPUs (measured)
TOTAL_VRAM_MB = 13100
# Reserve VRAM for Diffusers/image generation
DIFFUSERS_RESERVE_MB = 2500


# ─── The Orchestrator ────────────────────────────────────────────────

class OllamaOrchestrator:
    """AI-powered model orchestrator.

    Automatically selects, loads, and manages Ollama models based on:
    - What task/tab needs to run
    - What's currently in VRAM
    - Which model is best for the job
    - Available VRAM budget
    - Usage patterns (keeps hot models loaded)
    """

    def __init__(self) -> None:
        self._url = get_ollama_url()
        self._lock = threading.Lock()

        import requests as _req
        self._http = _req.Session()
        self._http.headers.update({"Content-Type": "application/json"})

        self._loaded_models: List[Dict[str, Any]] = []
        self._loaded_ts: float = 0.0
        self._cache_ttl = 1.5

        # Installed models (refreshed once at startup)
        self._installed: Set[str] = set()
        self._installed_ts: float = 0.0

        # Usage tracking for smart model retention
        self._usage_counts: Dict[str, int] = {}
        self._last_task: str = "general"

        # Event bus reference (set by attach_event_bus)
        self._event_bus: Any = None

        # NemoClaw sandbox backend (set by attach_nemoclaw)
        self._nemoclaw_available: bool = False
        self._nemoclaw_bridge: Any = None

        self._refresh_installed_async()
        logger.info("🧠 OllamaOrchestrator initialized — AI-powered model routing active")

    # ── Public API ────────────────────────────────────────────────

    def attach_event_bus(self, event_bus: Any) -> None:
        """Connect to Kingdom AI EventBus for tab-switch preloading."""
        self._event_bus = event_bus
        try:
            event_bus.subscribe("tab.switched", self._on_tab_switched)
            event_bus.subscribe("nemoclaw.initialized", self._on_nemoclaw_status)
            event_bus.subscribe("nemoclaw.status_update", self._on_nemoclaw_status)
            logger.info("🧠 Orchestrator subscribed to tab.switched + NemoClaw events")
        except Exception as e:
            logger.debug(f"Could not subscribe to tab events: {e}")

    def attach_nemoclaw(self, bridge) -> None:
        """Register the NemoClaw bridge so orchestrator can report its availability."""
        self._nemoclaw_bridge = bridge
        self._nemoclaw_available = getattr(bridge, "nemoclaw_available", False)
        logger.info("🧠 NemoClaw bridge registered with orchestrator (available=%s)", self._nemoclaw_available)

    def _on_nemoclaw_status(self, data) -> None:
        """Update NemoClaw availability from event bus."""
        if isinstance(data, dict):
            self._nemoclaw_available = data.get("available", False)

    def get_backend_status(self) -> Dict[str, Any]:
        """Return status of all AI backends (Ollama + NemoClaw)."""
        loaded = self._get_loaded_names()
        installed = self._get_installed()
        return {
            "ollama": {
                "url": self._url,
                "loaded_models": loaded,
                "installed_count": len(installed),
            },
            "nemoclaw": {
                "available": self._nemoclaw_available,
                "bridge_attached": self._nemoclaw_bridge is not None,
            },
        }

    def get_model_for_task(self, task: str, need_vision: bool = False,
                           need_math: bool = False, need_fast: bool = False) -> str:
        """Select the best model for a task.  Thread-safe, cached.

        This is the primary entry point.  All engines should call this
        instead of hardcoding model names.

        Args:
            task: Domain name (trading, creation, code, voice, math, etc.)
            need_vision: True if images need to be analyzed
            need_math: True if heavy math/calculations required
            need_fast: True if latency matters more than quality

        Returns:
            Model name string ready for Ollama API calls.
        """
        self._usage_counts[task] = self._usage_counts.get(task, 0) + 1
        self._last_task = task

        if need_vision:
            task = "vision"
        elif need_math:
            task = "math"
        if need_fast and task not in ("vision", "math", "ocr"):
            task = "voice"

        loaded = self._get_loaded_names()
        installed = self._get_installed()
        requirements = TASK_REQUIREMENTS.get(task, TASK_REQUIREMENTS["general"])

        best = self._score_and_rank(requirements, loaded, installed, need_fast)
        if best:
            self._track_model(best)
            return best

        if loaded:
            return loaded[0]
        return "mistral-nemo:latest"

    def get_model_for_task_with_fallbacks(self, task: str, **kwargs) -> List[str]:
        """Return an ordered list of models: best first, fallbacks after."""
        loaded = self._get_loaded_names()
        installed = self._get_installed()
        requirements = TASK_REQUIREMENTS.get(task, TASK_REQUIREMENTS["general"])
        need_fast = kwargs.get("need_fast", False)

        ranked = self._score_all(requirements, loaded, installed, need_fast)

        # loaded models first (0ms switch), then cloud, then unloaded local
        in_vram = [m for m in ranked if m in loaded]
        cloud = [m for m in ranked if m not in loaded and MODEL_REGISTRY.get(m, ModelProfile("", 0, set(), SpeedTier.SLOW, 0)).is_cloud]
        unloaded = [m for m in ranked if m not in loaded and m not in cloud]

        result = in_vram + cloud + unloaded
        return result if result else ["mistral-nemo:latest"]

    def prepare_request(self, task: str, num_predict: int = 500,
                        temperature: float = 0.7, num_ctx: int = 4096,
                        **kwargs) -> Tuple[str, dict]:
        """Get model + optimized options dict in one call."""
        model = self.get_model_for_task(task, **kwargs)
        options = get_optimal_options(
            temperature=temperature,
            num_predict=num_predict,
            num_ctx=num_ctx,
        )
        return model, options

    def preload_model(self, model_name: str, keep_alive: int = -1) -> None:
        """Load a model into VRAM in a background thread."""
        def _load():
            try:
                loaded = self._get_loaded_names()
                if model_name in loaded:
                    logger.debug(f"🧠 {model_name} already in VRAM")
                    return

                vram_needed = MODEL_REGISTRY.get(model_name, ModelProfile("", 10000, set(), SpeedTier.SLOW, 0)).vram_mb
                available = self._estimate_free_vram()

                if vram_needed > available + 500:
                    evictable = self._pick_eviction_candidates(vram_needed - available)
                    for evict_model in evictable:
                        self._unload_model(evict_model)
                        logger.info(f"🧠 Evicted {evict_model} to make room for {model_name}")

                logger.info(f"🧠 Loading {model_name} into VRAM (keep_alive={keep_alive})...")
                r = self._http.post(
                    f"{self._url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "",
                        "keep_alive": keep_alive,
                        "options": {"num_gpu": 999},
                    },
                    timeout=180,
                )
                if r.status_code == 200:
                    logger.info(f"🧠 {model_name} loaded into VRAM ✓")
                    self._invalidate_cache()
                else:
                    logger.warning(f"🧠 Failed to load {model_name}: HTTP {r.status_code}")
            except Exception as e:
                logger.error(f"🧠 Preload {model_name} failed: {e}")

        if not hasattr(self, '_preload_sem'):
            self._preload_sem = threading.Semaphore(2)
        if not hasattr(self, '_preloading_models'):
            self._preloading_models = set()
        if model_name in self._preloading_models:
            return
        self._preloading_models.add(model_name)
        def _guarded_load():
            with self._preload_sem:
                try:
                    _load()
                finally:
                    self._preloading_models.discard(model_name)
        threading.Thread(target=_guarded_load, daemon=True, name=f"preload-{model_name}").start()

    def preload_for_task(self, task: str) -> None:
        """Ensure the best model for a task is loaded in VRAM."""
        model = self.get_model_for_task(task)
        profile = MODEL_REGISTRY.get(model)
        if profile and not profile.is_cloud:
            self.preload_model(model)

    def on_tab_switched(self, tab_id: str) -> None:
        """Called when user switches tabs. Pre-loads the right model."""
        domain = TAB_TO_DOMAIN.get(tab_id, "general")
        logger.info(f"🧠 Tab switched → {tab_id} (domain={domain}), preparing model...")
        self.preload_for_task(domain)

    def get_status(self) -> Dict[str, Any]:
        """Return orchestrator status for diagnostics / UI."""
        loaded = self._get_loaded_models_raw()
        installed = self._get_installed()
        return {
            "loaded_models": [
                {"name": m.get("name", "?"), "size_mb": m.get("size", 0) // (1024 * 1024),
                 "until": m.get("expires_at", "?")}
                for m in loaded
            ],
            "installed_count": len(installed),
            "total_vram_mb": TOTAL_VRAM_MB,
            "estimated_free_mb": self._estimate_free_vram(),
            "last_task": self._last_task,
            "usage_counts": dict(self._usage_counts),
        }

    # ── Scoring / Ranking ─────────────────────────────────────────

    def _score_and_rank(self, requirements: List[ModelCapability],
                        loaded: List[str], installed: Set[str],
                        need_fast: bool) -> Optional[str]:
        ranked = self._score_all(requirements, loaded, installed, need_fast)
        return ranked[0] if ranked else None

    # Capabilities that a model MUST have for certain tasks.
    # If the first requirement is a hard cap, models without it are disqualified.
    HARD_REQUIREMENT_CAPS = {
        ModelCapability.VISION, ModelCapability.OCR,
        ModelCapability.EMBEDDING, ModelCapability.TRANSLATION,
        ModelCapability.MATH,
    }

    def _score_all(self, requirements: List[ModelCapability],
                   loaded: List[str], installed: Set[str],
                   need_fast: bool) -> List[str]:
        """Score every known model against requirements, return sorted list.

        SOTA 2026 scoring (inspired by Eagle/LLMRouterBench):
        - Hard requirements: vision/OCR/embedding MUST be present or model is rejected
        - VRAM locality bonus: prefer loaded model to avoid 20-30s swap
        - Capability match: weighted by priority position
        - Quality + speed + usage history all factor in
        """
        scores: List[Tuple[float, str]] = []

        hard_cap = requirements[0] if requirements and requirements[0] in self.HARD_REQUIREMENT_CAPS else None

        for name, profile in MODEL_REGISTRY.items():
            if not profile.is_cloud and name not in installed:
                continue
            if profile.name == "devstral-small-2:latest" and profile.vram_mb > TOTAL_VRAM_MB:
                continue

            # Hard requirement gate: if task needs vision/OCR/embedding,
            # the model MUST have that capability or it's disqualified
            if hard_cap and hard_cap not in profile.capabilities:
                continue

            score = 0.0

            # Capability match (weighted by priority position)
            for i, cap in enumerate(requirements):
                weight = 1.0 - (i * 0.15)
                if cap in profile.capabilities:
                    score += max(weight, 0.3) * 20.0

            # Quality bonus
            score += profile.quality_score * 15.0

            # VRAM locality bonus: model in VRAM = instant use (0ms vs 20-30s)
            # Strong bonus but NOT so strong it overrides hard requirements
            if name in loaded:
                score += 35.0

            # Speed bonus for latency-sensitive tasks
            if need_fast:
                if profile.speed_tier == SpeedTier.FAST:
                    score += 25.0
                elif profile.speed_tier == SpeedTier.MEDIUM:
                    score += 10.0
            else:
                if profile.speed_tier == SpeedTier.FAST:
                    score += 5.0

            # Local model bonus (no network latency, no API cost)
            if not profile.is_cloud:
                score += 8.0

            # Cloud model small bonus (always available, no VRAM cost)
            if profile.is_cloud:
                score += 3.0

            # Specialist bonus: if model has the EXACT first capability,
            # and it's a specialist (few capabilities), reward it
            if requirements and requirements[0] in profile.capabilities:
                if len(profile.capabilities) <= 3:
                    score += 10.0

            scores.append((score, name))

        scores.sort(key=lambda x: -x[0])
        return [name for _, name in scores]

    # ── VRAM Management ───────────────────────────────────────────

    def _get_loaded_models_raw(self) -> List[Dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            if now - self._loaded_ts < self._cache_ttl and self._loaded_models is not None:
                return list(self._loaded_models)

        try:
            r = self._http.get(f"{self._url}/api/ps", timeout=2)
            if r.status_code == 200:
                models = r.json().get("models", [])
                with self._lock:
                    self._loaded_models = models
                    self._loaded_ts = now
                return models
        except Exception:
            pass

        with self._lock:
            return list(self._loaded_models) if self._loaded_models else []

    def _get_loaded_names(self) -> List[str]:
        return [m.get("name", "") for m in self._get_loaded_models_raw()]

    def _get_installed(self) -> Set[str]:
        now = time.monotonic()
        if self._installed and now - self._installed_ts < 300:
            return self._installed
        try:
            r = self._http.get(f"{self._url}/api/tags", timeout=3)
            if r.status_code == 200:
                names = {m["name"] for m in r.json().get("models", [])}
                self._installed = names
                self._installed_ts = now
                return names
        except Exception:
            pass
        return self._installed

    def _refresh_installed_async(self) -> None:
        def _refresh():
            self._get_installed()
        threading.Thread(target=_refresh, daemon=True).start()

    def _estimate_free_vram(self) -> int:
        loaded = self._get_loaded_models_raw()
        used = sum(m.get("size", 0) // (1024 * 1024) for m in loaded)
        return max(TOTAL_VRAM_MB - used - DIFFUSERS_RESERVE_MB, 0)

    def _pick_eviction_candidates(self, need_mb: int) -> List[str]:
        """Pick models to evict from VRAM, least-recently-used first."""
        loaded = self._get_loaded_models_raw()
        if not loaded:
            return []

        candidates = []
        for m in loaded:
            name = m.get("name", "")
            size = m.get("size", 0) // (1024 * 1024)
            usage = self._usage_counts.get(
                self._last_task, 0
            )
            candidates.append((usage, size, name))

        candidates.sort(key=lambda x: x[0])

        evict = []
        freed = 0
        for _, size, name in candidates:
            if freed >= need_mb:
                break
            evict.append(name)
            freed += size
        return evict

    def _unload_model(self, model_name: str) -> bool:
        try:
            r = self._http.post(
                f"{self._url}/api/generate",
                json={"model": model_name, "prompt": "", "keep_alive": 0},
                timeout=15,
            )
            if r.status_code == 200:
                self._invalidate_cache()
                return True
        except Exception as e:
            logger.error(f"Failed to unload {model_name}: {e}")
        return False

    def _invalidate_cache(self) -> None:
        with self._lock:
            self._loaded_ts = 0.0

    def _track_model(self, model_name: str) -> None:
        with self._lock:
            self._usage_counts[model_name] = self._usage_counts.get(model_name, 0) + 1

    # ── Event Handlers ────────────────────────────────────────────

    def _on_tab_switched(self, data: Any) -> None:
        if isinstance(data, dict):
            tab_id = data.get("tab_id", "")
        else:
            tab_id = str(data) if data else ""
        if tab_id:
            self.on_tab_switched(tab_id)


# ─── Global Singleton ────────────────────────────────────────────────

orchestrator = OllamaOrchestrator()
