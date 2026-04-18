import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("KingdomAI.MoneroAdapter")

MONERO_AVAILABLE = False

try:
    from monero.wallet import Wallet
    from monero.backends.jsonrpc import JSONRPCWallet

    MONERO_AVAILABLE = True
except Exception as e:
    logger.warning("monero library not available; Monero adapter disabled: %s", e)
    MONERO_AVAILABLE = False


class MoneroWalletAdapter:
    """Thin adapter around monero-wallet-rpc via monero-python.

    This adapter assumes that monero-wallet-rpc is already running and
    has a wallet file opened. It does **not** create wallets or expose
    mnemonic seeds; it only reads the primary address so it can be used
    as a mining destination managed by external Monero tooling.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 18083,
        user: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
        use_ssl: bool = False,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.timeout = int(timeout)
        self.use_ssl = bool(use_ssl)

    def get_primary_address(self) -> Optional[str]:
        """Return the primary wallet address from monero-wallet-rpc.

        Returns None if the adapter is not available or any error occurs.
        """
        if not MONERO_AVAILABLE:
            return None
        try:
            backend = JSONRPCWallet(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                protocol="https" if self.use_ssl else "http",
                timeout=self.timeout,
            )
            wallet = Wallet(backend)
            addr = str(wallet.address())
            return addr.strip() or None
        except Exception as e:
            logger.error("Failed to query Monero primary address: %s", e)
            return None


def load_monero_adapter_from_config(config_path: Path) -> Optional[MoneroWalletAdapter]:
    """Load MoneroWalletAdapter from a JSON config file.

    Expected JSON structure (config/wallet_monero.json):

    {
      "host": "127.0.0.1",
      "port": 18083,
      "user": "rpc_username",
      "password": "rpc_password",
      "timeout": 30,
      "ssl": false
    }
    """
    if not MONERO_AVAILABLE:
        return None

    try:
        if not config_path.exists():
            logger.debug("Monero config file not found: %s", config_path)
            return None

        with open(config_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        host = data.get("host", "127.0.0.1")
        port = int(data.get("port", 18083))
        user = data.get("user") or None
        password = data.get("password") or None
        timeout = int(data.get("timeout", 30))
        use_ssl = bool(data.get("ssl", False))

        return MoneroWalletAdapter(
            host=host,
            port=port,
            user=user,
            password=password,
            timeout=timeout,
            use_ssl=use_ssl,
        )
    except Exception as e:
        logger.error("Failed to load Monero adapter config from %s: %s", config_path, e)
        return None
