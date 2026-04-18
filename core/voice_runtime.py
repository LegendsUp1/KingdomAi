"""
Voice / XTTS inference runtime (SOTA 2026 isolation model)
============================================================

**Coqui XTTS** pulls a heavy, version-sensitive stack (numpy/numba/librosa/torch/transformers).
Industry practice (and this project’s original design) keeps that stack **out of** the main
application venv (`kingdom-venv`) so trading/GUI/JAX stacks stay stable.

**Intended runtimes for cloned voice (pick one):**

1. **Conda** ``kingdom-voice`` — ``setup_voice_isolated_env.sh`` (Dec 19th–style pins + Redis client).
2. **Repo-local venv** ``voice_runtime_env/`` — ``scripts/bootstrap_voice_runtime_venv.sh`` installs
   ``requirements-voice.txt`` only there.
3. **Explicit override** — ``KINGDOM_VOICE_PYTHON=/path/to/python`` (Easy Store / “New folder” mirror paths).

The **main** ``kingdom-venv`` must **not** be used for XTTS unless you deliberately set
``KINGDOM_ALLOW_MAIN_VENV_XTTS=1`` (debug only).

Redis + ``redis_voice_service.py`` remains the production bridge: the **voice env** runs the
service; the **app env** publishes ``voice.speak``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_voice_inference_python(repo_root: Optional[Path] = None) -> Optional[str]:
    """Return a Python executable dedicated to voice/TTS, or ``None`` to fall back to conda.

    Order:
    1. ``KINGDOM_VOICE_PYTHON`` if it points to an existing file.
    2. ``<repo>/voice_runtime_env/bin/python`` (or ``python3``).
    3. Legacy names for older checkouts / Easy Store copies.
    """
    root = repo_root or get_repo_root()

    env_p = os.environ.get("KINGDOM_VOICE_PYTHON", "").strip()
    if env_p:
        cand = Path(env_p).expanduser()
        if cand.is_file():
            return str(cand.resolve())

    candidates = (
        root / "voice_runtime_env" / "bin" / "python",
        root / "voice_runtime_env" / "bin" / "python3",
        root / "kingdom_voice_env" / "bin" / "python",
    )
    for cand in candidates:
        if cand.is_file():
            return str(cand.resolve())

    return None
