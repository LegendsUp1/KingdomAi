import logging
import subprocess
import time
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("KingdomAI.ExternalWalletAdapter")

# Track failed commands to avoid log spam - coin -> (last_fail_time, fail_count)
_failure_cache: Dict[str, Tuple[float, int]] = {}
_DEBOUNCE_SECONDS = 300  # Skip retries for 5 minutes after failure

# Cache of POW symbol -> RPC URL env var name (e.g. "XVG" -> "XVG_RPC_URL")
_node_rpc_env_map: Dict[str, str] = {}


def _load_node_rpc_env_map() -> Dict[str, str]:
    """Load mapping of PoW symbols to RPC URL env names from pow_nodes.json.

    This uses config/pow_nodes.json which already defines, per coin, which
    environment variables (e.g. XVG_RPC_URL) should be used for node RPC
    connectivity. The result is cached at module level.
    """

    global _node_rpc_env_map
    if _node_rpc_env_map:
        return _node_rpc_env_map

    try:
        base_dir = Path(__file__).resolve().parent.parent
        pow_nodes_path = base_dir / "config" / "pow_nodes.json"
        if not pow_nodes_path.exists():
            return _node_rpc_env_map

        with open(pow_nodes_path, "r", encoding="utf-8-sig") as f:
            data: Dict[str, Any] = json.load(f)

        nodes = data.get("nodes", {}) or {}
        for sym, info in nodes.items():
            try:
                if not isinstance(info, dict):
                    continue
                env_name = info.get("rpc_url_env")
                if isinstance(env_name, str) and env_name.strip():
                    _node_rpc_env_map[str(sym).upper()] = env_name.strip()
            except Exception:
                # Best-effort only; log at debug if desired in future.
                continue
    except Exception:
        # If this mapping fails to load, external wallet adapters still work
        # for coins that do not rely on RPC URL env vars.
        return _node_rpc_env_map

    return _node_rpc_env_map


class ExternalWalletAdapter:
    """Generic adapter that invokes an external wallet CLI to get an address.

    The actual command is defined in config (per coin). The CLI is expected to
    print a receive address to stdout. The adapter returns the first non-empty
    line from stdout, stripped.
    """

    def __init__(self, command: List[str], coin: str = "UNKNOWN") -> None:
        self.command = list(command)
        self.coin = coin

    def _missing_rpc_env(self) -> Optional[str]:
        """Return the RPC URL env var name if required but missing for this coin.

        This consults config/pow_nodes.json to see if the given symbol has an
        associated ``rpc_url_env`` entry, and then checks os.environ. If the
        env var is not set or empty, the name is returned so callers can
        classify the failure as a configuration issue rather than letting
        curl run with an empty URL.
        """

        mapping = _load_node_rpc_env_map()
        env_name = mapping.get(self.coin.upper())
        if not env_name:
            return None
        value = os.environ.get(env_name)
        if not isinstance(value, str) or not value.strip():
            return env_name
        return None

    def _has_empty_url(self) -> bool:
        """Check if command contains curl with empty URL placeholder."""
        if not self.command:
            return True
        cmd_str = " ".join(self.command)
        # Detect empty quoted URL: curl ... ""
        if "curl" in cmd_str and '""' in cmd_str:
            return True
        return False

    def _is_debounced(self) -> bool:
        """Check if this coin recently failed and should be skipped."""
        if self.coin not in _failure_cache:
            return False
        last_fail, _ = _failure_cache[self.coin]
        return (time.time() - last_fail) < _DEBOUNCE_SECONDS

    def _record_failure(self) -> None:
        """Record failure for debouncing."""
        now = time.time()
        if self.coin in _failure_cache:
            _, count = _failure_cache[self.coin]
            _failure_cache[self.coin] = (now, count + 1)
        else:
            _failure_cache[self.coin] = (now, 1)

    def get_address(self) -> Optional[str]:
        """Run the configured command and return the first non-empty line.

        Returns None on error.
        """
        if not self.command:
            return None

        # Skip if recently failed (debounce to prevent log spam)
        if self._is_debounced():
            return None

        # Validate environment-based RPC URL configuration if applicable.
        # SOTA 2026: Downgrade to DEBUG - most PoW coins require local full nodes
        # and missing RPC URLs are expected configuration gaps, not errors
        missing_env = self._missing_rpc_env()
        if missing_env:
            # This is a configuration gap - most PoW coins don't have public RPCs
            # Log at DEBUG level to avoid log spam for expected missing configs
            if self.coin not in _failure_cache:
                logger.debug(
                    "External wallet RPC URL env %s for %s is not set; "
                    "requires local full node or public RPC endpoint.",
                    missing_env,
                    self.coin,
                )
            self._record_failure()
            return None

        # Validate command before running - skip if empty URL detected
        if self._has_empty_url():
            # SOTA 2026: Downgrade to DEBUG - empty URLs are expected for coins
            # that don't have public RPC endpoints configured
            if self.coin not in _failure_cache:
                logger.debug(
                    "External wallet command for %s has no RPC URL configured; "
                    "requires local full node setup.",
                    self.coin,
                )
            self._record_failure()
            return None

        try:
            result = subprocess.run(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logger.error(
                    "External wallet command failed for %s (%s): %s",
                    self.coin,
                    result.returncode,
                    result.stderr.strip(),
                )
                self._record_failure()
                return None

            for line in (result.stdout or "").splitlines():
                line = line.strip()
                # Ignore empty lines and literal nulls
                if not line or line.lower() == "null":
                    continue
                # Success - clear from failure cache
                _failure_cache.pop(self.coin, None)
                return line

            # SOTA 2026: Downgrade to DEBUG if stderr indicates missing URL (curl error 3)
            # This is expected for coins without public RPC endpoints
            stderr = (result.stderr or "").strip()
            if "URL using bad/illegal format or missing URL" in stderr:
                if self.coin not in _failure_cache:
                    logger.debug(
                        "External wallet for %s has no RPC URL configured; requires local full node.",
                        self.coin,
                    )
            else:
                logger.error(
                    "External wallet command for %s produced no usable output; stdout=%r, stderr=%r",
                    self.coin,
                    (result.stdout or "").strip(),
                    stderr,
                )
            self._record_failure()
            return None
        except Exception as e:
            logger.error("Error running external wallet command for %s: %s", self.coin, e)
            self._record_failure()
            return None
