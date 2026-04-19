"""Kingdom AI — Install Advisor.

Hardware-adaptive installer logic for **consumer desktop**. Every consumer
desktop machine gets the heaviest tier its hardware can actually run — it
is **not** downgraded just because the user isn't the creator. Role
(``KINGDOM_APP_MODE=consumer``) only redacts keys/secrets/data; platform
(``KINGDOM_APP_PLATFORM=desktop`` vs ``mobile``) picks the tier.

## Tiers

- **ultra** — RTX 4090-class or better. TensorRT-LLM + vLLM + FlashAttention-3 +
  sentence-transformers on CUDA. Designed for sub-100 ms responses.
- **full**  — RTX 3060+ or ≥12 GB VRAM. vLLM + sentence-transformers on CUDA +
  Ollama with CUDA offload. FlashAttention-2 if compute ≥ 8.0.
- **standard** — Any CUDA GPU with <12 GB VRAM, or CPU with ≥32 GB RAM and
  ≥8 cores. sentence-transformers on CPU, Ollama HTTP, no vLLM/TRT-LLM.
- **light**   — Anything else (low RAM, laptops, older CPUs). Ollama HTTP
  with a tiny default model; no torch/sentence-transformers. This is
  roughly the mobile tier but still running on desktop.

## Usage

Programmatic:

    from core.install_advisor import recommend_tier
    report = recommend_tier()
    print(report["tier"], report["reason"])
    print(report["pip_install_line"])

Consumer desktop first-run integration:

    from core.install_advisor import ensure_tier_ready
    ensure_tier_ready(interactive=True)

The advisor never *auto-installs* without the caller asking — it returns
the recommended pip command so the outer CLI (or an installer GUI) can
print it, prompt for confirmation, and then shell out. That keeps this
module pure-Python and trivially testable.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.install_advisor")


# ── Tier catalogue ─────────────────────────────────────────────────────────

TIERS: Dict[str, Dict[str, Any]] = {
    "ultra": {
        "label": "Ultra RTX",
        "description": (
            "RTX 4090-class GPU. TensorRT-LLM + vLLM + FlashAttention-3 + "
            "sentence-transformers on CUDA. Sub-100 ms target."
        ),
        "min_vram_gb": 20,
        "min_ram_gb": 32,
        "min_cpu_cores": 8,
        "min_cuda_compute": 8.9,  # Ada / Hopper
        "pip_packages": [
            "torch>=2.3",
            "sentence-transformers>=3,<4",
            "transformers>=4.45",
            "tokenizers>=0.20",
            "faiss-cpu",
            "chromadb",
            "lancedb",
            "vllm",
            # flash-attn must be a separate step because it needs nvcc on PATH
            # and its wheel build can take 30+ minutes. We document it in the
            # advisor output rather than embed it in the one-liner.
        ],
        "notes": [
            "After the pip line completes, install TensorRT-LLM per NVIDIA's "
            "official guide (requires CUDA 12.4+ and an RTX 40/50 or Hopper "
            "GPU): https://github.com/NVIDIA/TensorRT-LLM",
            "Consider `pip install flash-attn --no-build-isolation` for "
            "FlashAttention-3 throughput.",
        ],
    },
    "full": {
        "label": "Full Desktop",
        "description": (
            "RTX 3060+ or ≥12 GB VRAM. vLLM + sentence-transformers on CUDA. "
            "Full SOTA stack minus TensorRT-LLM."
        ),
        "min_vram_gb": 8,
        "min_ram_gb": 16,
        "min_cpu_cores": 6,
        "min_cuda_compute": 7.5,  # Turing / Ampere
        "pip_packages": [
            "torch>=2.3",
            "sentence-transformers>=3,<4",
            "transformers>=4.45",
            "tokenizers>=0.20",
            "faiss-cpu",
            "chromadb",
            "vllm",
        ],
        "notes": [
            "Ollama is picked up automatically; if not installed visit "
            "https://ollama.com to grab the installer.",
        ],
    },
    "standard": {
        "label": "Standard Desktop",
        "description": (
            "CPU-only or small-GPU machine with enough RAM to run "
            "sentence-transformers on CPU + Ollama HTTP."
        ),
        "min_vram_gb": 0,
        "min_ram_gb": 16,
        "min_cpu_cores": 4,
        "min_cuda_compute": 0.0,
        "pip_packages": [
            "torch>=2.3",
            "sentence-transformers>=3,<4",
            "transformers>=4.45",
            "faiss-cpu",
            "chromadb",
        ],
        "notes": [
            "No vLLM / TensorRT-LLM on this tier — Ollama HTTP is the "
            "only generation backend.",
        ],
    },
    "light": {
        "label": "Light Desktop",
        "description": (
            "Low-RAM or older machine. Ollama HTTP with a tiny default "
            "model; no torch/sentence-transformers. Matches the mobile "
            "dependency profile but running on a desktop."
        ),
        "min_vram_gb": 0,
        "min_ram_gb": 0,
        "min_cpu_cores": 0,
        "min_cuda_compute": 0.0,
        "pip_packages": [],
        "notes": [
            "The inference stack still runs — it just falls back to "
            "Ollama HTTP → offline stub with SHA pseudo-embeddings.",
            "Install Ollama from https://ollama.com and `ollama pull gemma:2b`.",
        ],
    },
}


# ── Hardware probe ─────────────────────────────────────────────────────────

@dataclass
class HardwareReport:
    os_name: str = ""
    os_release: str = ""
    arch: str = ""
    python_version: str = ""
    cpu_cores_physical: int = 0
    cpu_cores_logical: int = 0
    ram_gb: float = 0.0
    disk_free_gb: float = 0.0
    has_cuda: bool = False
    cuda_devices: List[Dict[str, Any]] = field(default_factory=list)
    max_vram_gb: float = 0.0
    max_cuda_compute: float = 0.0
    has_ollama: bool = False
    has_nvcc: bool = False
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "os_name": self.os_name, "os_release": self.os_release,
            "arch": self.arch, "python_version": self.python_version,
            "cpu_cores_physical": self.cpu_cores_physical,
            "cpu_cores_logical": self.cpu_cores_logical,
            "ram_gb": round(self.ram_gb, 1),
            "disk_free_gb": round(self.disk_free_gb, 1),
            "has_cuda": self.has_cuda,
            "cuda_devices": self.cuda_devices,
            "max_vram_gb": round(self.max_vram_gb, 1),
            "max_cuda_compute": self.max_cuda_compute,
            "has_ollama": self.has_ollama,
            "has_nvcc": self.has_nvcc,
            "notes": list(self.notes),
        }


def probe_hardware() -> HardwareReport:
    """Best-effort inspection of the host. Safe on any platform; never raises."""
    rep = HardwareReport()

    rep.os_name = platform.system()
    rep.os_release = platform.release()
    rep.arch = platform.machine()
    rep.python_version = sys.version.split()[0]

    # CPU cores
    try:
        rep.cpu_cores_logical = os.cpu_count() or 0
    except Exception:
        rep.cpu_cores_logical = 0
    try:
        import psutil  # type: ignore
        rep.cpu_cores_physical = psutil.cpu_count(logical=False) or 0
        rep.ram_gb = round(psutil.virtual_memory().total / 1e9, 2)
    except Exception:
        # Fallbacks that don't need psutil
        rep.cpu_cores_physical = rep.cpu_cores_logical or 0
        try:
            # Linux-only /proc/meminfo parser
            with open("/proc/meminfo", "r") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        rep.ram_gb = round(
                            int(line.split()[1]) / 1_048_576.0, 2
                        )
                        break
        except Exception:
            rep.ram_gb = 0.0

    # Disk free (on the drive holding this file)
    try:
        du = shutil.disk_usage(os.path.dirname(os.path.abspath(__file__)))
        rep.disk_free_gb = round(du.free / 1e9, 2)
    except Exception:
        rep.disk_free_gb = 0.0

    # CUDA via torch (best source — same one the inference stack uses)
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            rep.has_cuda = True
            n = torch.cuda.device_count()
            for i in range(n):
                try:
                    p = torch.cuda.get_device_properties(i)
                    cap = float(f"{p.major}.{p.minor}")
                    vram_gb = round(p.total_memory / 1e9, 2)
                    rep.cuda_devices.append({
                        "index": i,
                        "name": p.name,
                        "compute_capability": cap,
                        "vram_gb": vram_gb,
                    })
                    if vram_gb > rep.max_vram_gb:
                        rep.max_vram_gb = vram_gb
                    if cap > rep.max_cuda_compute:
                        rep.max_cuda_compute = cap
                except Exception as exc:
                    rep.notes.append(f"cuda device {i} probe failed: {exc}")
    except Exception:
        rep.has_cuda = False

    # nvcc on PATH — required for flash-attn / TensorRT-LLM
    rep.has_nvcc = shutil.which("nvcc") is not None

    # Ollama binary on PATH (any platform)
    rep.has_ollama = (
        shutil.which("ollama") is not None
        or os.path.exists("/usr/local/bin/ollama")
    )

    return rep


# ── Tier recommendation ────────────────────────────────────────────────────

def recommend_tier(
    report: Optional[HardwareReport] = None,
) -> Dict[str, Any]:
    """Return a full recommendation dict for the given hardware report.

    If *report* is omitted, :func:`probe_hardware` is called. The dict
    contains:

        tier              - "ultra" | "full" | "standard" | "light"
        label             - human-friendly tier name
        description       - one-sentence tier description
        reason            - why *this* machine got this tier
        hardware          - the raw hardware probe
        pip_install_line  - ready-to-run pip command for the tier
        post_install_notes - list of extra steps (TRT-LLM, flash-attn, …)
    """
    rep = report or probe_hardware()

    # Pick the highest tier whose thresholds are met
    chosen_key = "light"
    for key in ("ultra", "full", "standard"):
        spec = TIERS[key]
        if (rep.ram_gb >= spec["min_ram_gb"]
                and rep.cpu_cores_logical >= spec["min_cpu_cores"]):
            needs_cuda = spec["min_vram_gb"] > 0 or spec["min_cuda_compute"] > 0
            if needs_cuda:
                if not rep.has_cuda:
                    continue
                if rep.max_vram_gb < spec["min_vram_gb"]:
                    continue
                if rep.max_cuda_compute < spec["min_cuda_compute"]:
                    continue
            chosen_key = key
            break

    spec = TIERS[chosen_key]
    pip_line = ""
    if spec["pip_packages"]:
        pip_line = (
            f"{sys.executable} -m pip install --upgrade "
            + " ".join(f'"{p}"' for p in spec["pip_packages"])
        )

    reason_bits: List[str] = []
    if chosen_key == "ultra":
        reason_bits.append(
            f"{rep.max_vram_gb:.0f} GB VRAM, compute {rep.max_cuda_compute}"
        )
    elif chosen_key == "full":
        reason_bits.append(
            f"{rep.max_vram_gb:.0f} GB VRAM, compute {rep.max_cuda_compute}, "
            f"{rep.ram_gb:.0f} GB RAM"
        )
    elif chosen_key == "standard":
        reason_bits.append(
            f"no RTX-class GPU, {rep.ram_gb:.0f} GB RAM, "
            f"{rep.cpu_cores_logical} cores"
        )
    else:  # light
        reason_bits.append(
            f"{rep.ram_gb:.1f} GB RAM / {rep.cpu_cores_logical} cores — "
            "below standard thresholds"
        )
    if not rep.has_ollama:
        reason_bits.append("Ollama not detected on PATH")
    reason = "; ".join(reason_bits)

    return {
        "tier": chosen_key,
        "label": spec["label"],
        "description": spec["description"],
        "reason": reason,
        "hardware": rep.as_dict(),
        "pip_install_line": pip_line,
        "post_install_notes": list(spec.get("notes") or []),
    }


# ── Optional: interactive ensure-ready ─────────────────────────────────────

def ensure_tier_ready(
    interactive: bool = True,
    auto_accept: bool = False,
    log_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run the advisor and, with user consent, execute the pip install line.

    Parameters
    ----------
    interactive: present the recommendation and prompt for confirmation.
    auto_accept: skip the prompt (e.g. in automated installers).
    log_fn: callable used for status lines; defaults to ``print``.
    """
    log = log_fn or print
    rec = recommend_tier()
    log("\n━━━ Kingdom AI — Install Advisor ━━━")
    log(f"Recommended tier: {rec['label']}  ({rec['tier']})")
    log(f"Why: {rec['reason']}")
    log(f"Hardware: {rec['hardware']}")
    if rec["pip_install_line"]:
        log("\nProposed install line:")
        log(f"  {rec['pip_install_line']}")
    else:
        log("\nNo pip install needed for this tier.")
    for note in rec["post_install_notes"]:
        log(f"  • {note}")

    if not rec["pip_install_line"]:
        return {**rec, "executed": False}
    if auto_accept:
        accept = True
    elif not interactive:
        return {**rec, "executed": False}
    else:
        try:
            ans = input("\nRun this pip install now? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        accept = ans in ("y", "yes")
    if not accept:
        log("\nSkipped.")
        return {**rec, "executed": False}

    log("\nInstalling…")
    try:
        subprocess.check_call(rec["pip_install_line"], shell=True)
        log("Install complete.")
        return {**rec, "executed": True}
    except subprocess.CalledProcessError as exc:
        log(f"pip install failed (exit {exc.returncode}). Re-run manually "
            "if you want to inspect the error.")
        return {**rec, "executed": False, "error": str(exc)}


__all__ = [
    "HardwareReport",
    "TIERS",
    "probe_hardware",
    "recommend_tier",
    "ensure_tier_ready",
]


if __name__ == "__main__":  # pragma: no cover — smoke test
    import json
    print(json.dumps(recommend_tier(), indent=2))
