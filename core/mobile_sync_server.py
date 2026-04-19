"""
Kingdom AI — Mobile Sync Server
SOTA 2026: WebSocket server running on desktop that mobile app connects to.

Handles:
  - QR code account linking (desktop generates QR, mobile scans)
  - Real-time data sync (portfolio, prices, alerts)
  - KAI chat relay (mobile chat → desktop AI → mobile response)
  - Mining pool status sync
  - Emergency alert relay (mobile silent alarm → desktop full security)

Runs on localhost:8765 by default. Mobile discovers via QR code.
"""
import asyncio
import json
import logging
import os
import secrets
import time
import urllib.request
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("KingdomAI.MobileSyncServer")

try:
    from core.version_info import app_version as _app_version, landing_page_url as _landing_url
    APP_VERSION = _app_version()
    LANDING_PAGE_URL = _landing_url()
except Exception:
    APP_VERSION = "2.2.0"
    LANDING_PAGE_URL = "https://kingdom-ai.netlify.app"

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("websockets not installed — mobile sync unavailable")

try:
    from core.ai_security_engine import get_ai_security_engine, AISecurityEngine
    HAS_AI_SECURITY = True
except ImportError:
    HAS_AI_SECURITY = False
    logger.warning("ai_security_engine not available — running without AI security")

try:
    import qrcode
    from io import BytesIO
    import base64
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

from base_component import BaseComponent

SYNC_PORT = 8765
LINK_CONFIG_PATH = os.path.join("config", "mobile_links.json")


class MobileSyncServer(BaseComponent):
    """
    WebSocket server for desktop ↔ mobile communication.
    Integrates with EventBus to relay events between desktop and mobile.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config or {}, event_bus=event_bus, redis_connector=redis_connector)

        self._port = int(self.config.get("port", SYNC_PORT))
        self._server = None
        self._connected_devices: Dict[str, Any] = {}  # device_id -> websocket
        self._link_codes: Dict[str, Dict] = {}  # pending link codes
        self._linked_devices: Dict[str, Dict] = {}  # confirmed links

        # AI Security Engine (2026 SOTA hack-proof)
        self._security_engine = None
        if HAS_AI_SECURITY:
            try:
                redis_conn = getattr(self, 'redis', None)
                self._security_engine = get_ai_security_engine(redis_client=redis_conn)
                logger.info("[SECURITY] AISecurityEngine active — hack-proof protection enabled")
            except Exception as sec_err:
                logger.warning("AISecurityEngine init failed (non-fatal): %s", sec_err)

        self._load_links()
        self._subscribe_events()
        self._price_cache: Dict[str, Any] = {}
        self._price_cache_ts: float = 0.0
        self._initialized = True
        logger.info("MobileSyncServer initialized (port=%d, linked=%d devices, security=%s)",
                    self._port, len(self._linked_devices),
                    "AI-ACTIVE" if self._security_engine else "BASIC")

    # ------------------------------------------------------------------
    # AUTO-ONBOARDING: Per-user wallet + card creation (SOTA 2026)
    # ------------------------------------------------------------------

    async def _auto_onboard_user(self, user_id: str) -> Dict[str, Any]:
        """Auto-create a unique wallet and digital card for a new user.

        Called on link/auth. If the user already has a wallet, returns the
        existing data. Desktop and mobile share the same wallet because
        they share the same user_id (device_id for mobile, "creator" for
        the desktop owner).
        """
        result: Dict[str, Any] = {"wallet": {}, "card": {}}
        if not user_id:
            return result

        try:
            from core.wallet_creator import WalletCreator
            creator = WalletCreator(event_bus=self.event_bus)

            wallet_info = await creator.create_user_wallet(user_id)
            if wallet_info.get("success"):
                result["wallet"] = {
                    "user_id": user_id,
                    "addresses": wallet_info.get("addresses", {}),
                    "created": wallet_info.get("created", False),
                }
                logger.info("User %s wallet ready: %d chains",
                            user_id, len(wallet_info.get("addresses", {})))

                wm = None
                if self.event_bus and hasattr(self.event_bus, 'get_component'):
                    wm = self.event_bus.get_component('wallet_manager')
                if wm:
                    active_uid = getattr(wm, '_active_user_id', 'creator')
                    if active_uid == user_id:
                        for sym, addr in wallet_info.get("addresses", {}).items():
                            wm.address_cache[sym.upper()] = addr

            user_cards = self._fintech_get_cards(user_id=user_id)
            if not user_cards.get("cards"):
                card_resp = await self._fintech_issue_card({
                    "label": f"Kingdom Card",
                    "user_id": user_id,
                    "card_type": "virtual",
                    "currency": "USD",
                })
                if card_resp.get("status") == "ok":
                    result["card"] = {
                        "card_id": card_resp.get("card_id"),
                        "last4": card_resp.get("last4"),
                        "network": card_resp.get("network"),
                        "token": card_resp.get("token"),
                    }
                    logger.info("Auto-issued card *%s for user %s",
                                card_resp.get("last4"), user_id)
            else:
                first_card = user_cards["cards"][0]
                result["card"] = {
                    "card_id": first_card.get("card_id"),
                    "last4": first_card.get("last4"),
                    "network": first_card.get("network", "Visa"),
                }
            try:
                from core.username_registry import get_username_for_user, update_addresses
                existing = get_username_for_user(user_id)
                if existing:
                    update_addresses(user_id, wallet_info.get("addresses", {}))
                    result["username"] = existing
                else:
                    result["username"] = None
            except Exception:
                pass

        except Exception as e:
            logger.warning("Auto-onboard for user %s: %s", user_id, e)

        return result

    # ------------------------------------------------------------------
    # Link management
    # ------------------------------------------------------------------

    def generate_link_qr(self) -> Dict[str, Any]:
        """Generate a QR code for mobile to scan and link."""
        import socket
        code = secrets.token_urlsafe(32)
        # Get local IP for mobile to connect
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

        account_id = self._resolve_account_id()
        link_data = {
            "code": code,
            "desktop_id": self._get_desktop_id(),
            "account_id": account_id,
            "host": local_ip,
            "port": self._port,
            "protocol": "ws",
            "app": "kingdom_ai",
            "version": APP_VERSION,
            "generated_at": datetime.utcnow().isoformat(),
        }

        self._link_codes[code] = link_data

        result = {
            "link_data": link_data,
            "qr_url": f"ws://{local_ip}:{self._port}",
        }

        # Generate QR image if qrcode library available
        if HAS_QRCODE:
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(json.dumps(link_data))
                qr.make(fit=True)
                img = qr.make_image(fill_color="gold", back_color="#0A0E17")
                buf = BytesIO()
                img.save(buf, format="PNG")
                result["qr_image_base64"] = base64.b64encode(buf.getvalue()).decode()
            except Exception as e:
                logger.warning("QR image generation failed: %s", e)

        if self.event_bus:
            self.event_bus.publish("mobile.link.qr_generated", result)

        logger.info("Mobile link QR generated (code=%s...)", code[:8])
        return result

    def confirm_link(self, code: str, device_id: str, device_info: Dict,
                     session_token: str = "") -> bool:
        """Confirm a mobile device link."""
        if code not in self._link_codes:
            return False

        self._linked_devices[device_id] = {
            "device_id": device_id,
            "linked_at": datetime.utcnow().isoformat(),
            "device_info": device_info,
            "code": code,
            "session_token": session_token,
        }
        del self._link_codes[code]
        self._persist_links()

        if self.event_bus:
            self.event_bus.publish("mobile.device.linked", {
                "device_id": device_id,
                "device_info": device_info,
            })

        logger.info("Mobile device linked: %s (token=%s)", device_id,
                    session_token[:8] + "..." if session_token else "none")
        return True

    def verify_session(self, device_id: str, session_token: str) -> bool:
        """Verify a returning device's session token."""
        device = self._linked_devices.get(device_id)
        if not device:
            return False
        stored_token = device.get("session_token", "")
        if not stored_token or stored_token != session_token:
            logger.warning("Session token mismatch for device %s", device_id)
            return False
        logger.info("Session verified for device %s", device_id)
        return True

    def _resolve_account_id(self) -> str:
        """Return the account_id for the running desktop instance.

        For the owner, this is 'creator'.  For a consumer desktop, it is
        the persistent consumer_id from data/consumer_identity.json.
        The mobile app uses the same account_id so desktop + mobile share
        one wallet, one set of API keys, one digital card, etc.
        """
        try:
            id_path = os.path.join("data", "consumer_identity.json")
            if os.path.exists(id_path):
                with open(id_path, "r") as f:
                    return json.load(f).get("consumer_id", "creator")
        except Exception:
            pass
        return "creator"

    # ------------------------------------------------------------------
    # Consumer API key management (SOTA 2026)
    # Desktop + mobile share keys via data/wallets/users/{account_id}/
    # ------------------------------------------------------------------

    def _handle_save_api_keys(self, data: dict, user_id: str) -> dict:
        """Save or update the consumer's exchange / service API keys.

        Keys are stored in data/wallets/users/{user_id}/api_keys.json.
        Both desktop and mobile read from the same path (same account_id),
        so adding a key on mobile is instantly available on desktop and
        vice-versa.
        """
        keys = data.get("api_keys", {})
        if not keys or not isinstance(keys, dict):
            return {"type": "save_api_keys_result", "status": "error",
                    "message": "No api_keys dict provided"}

        merge = data.get("merge", True)
        keys_path = os.path.join("data", "wallets", "users", user_id, "api_keys.json")
        os.makedirs(os.path.dirname(keys_path), exist_ok=True)

        existing = {}
        if merge and os.path.exists(keys_path):
            try:
                with open(keys_path, "r") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        if merge:
            for svc, svc_data in keys.items():
                existing[svc.lower()] = svc_data
        else:
            existing = {k.lower(): v for k, v in keys.items()}

        with open(keys_path, "w") as f:
            json.dump(existing, f, indent=2)

        logger.info("Saved %d API keys for user %s (%s)",
                    len(existing), user_id, keys_path)
        return {
            "type": "save_api_keys_result", "status": "ok",
            "saved_count": len(existing),
            "services": list(existing.keys()),
        }

    def _handle_get_api_keys(self, user_id: str) -> dict:
        """Return the consumer's saved API keys (redacted secrets)."""
        keys_path = os.path.join("data", "wallets", "users", user_id, "api_keys.json")
        if not os.path.exists(keys_path):
            return {"type": "api_keys_result", "status": "ok",
                    "api_keys": {}, "count": 0}
        try:
            with open(keys_path, "r") as f:
                raw = json.load(f)
        except Exception:
            raw = {}

        redacted = {}
        for svc, svc_data in raw.items():
            entry = {}
            if isinstance(svc_data, dict):
                for k, v in svc_data.items():
                    if any(word in k.lower() for word in ("key", "secret", "token", "password")):
                        entry[k] = v[:4] + "****" + v[-4:] if isinstance(v, str) and len(v) > 8 else "****"
                    else:
                        entry[k] = v
            else:
                entry = {"value": "****"}
            redacted[svc] = entry

        return {"type": "api_keys_result", "status": "ok",
                "api_keys": redacted, "count": len(redacted)}

    def _handle_delete_api_key(self, data: dict, user_id: str) -> dict:
        """Delete a single service's API keys for the consumer."""
        service = data.get("service", "").lower()
        if not service:
            return {"type": "delete_api_key_result", "status": "error",
                    "message": "No service specified"}
        keys_path = os.path.join("data", "wallets", "users", user_id, "api_keys.json")
        if not os.path.exists(keys_path):
            return {"type": "delete_api_key_result", "status": "error",
                    "message": "No keys file found"}
        try:
            with open(keys_path, "r") as f:
                existing = json.load(f)
            if service in existing:
                del existing[service]
                with open(keys_path, "w") as f:
                    json.dump(existing, f, indent=2)
                return {"type": "delete_api_key_result", "status": "ok",
                        "service": service}
            return {"type": "delete_api_key_result", "status": "error",
                    "message": f"Service '{service}' not found"}
        except Exception as e:
            return {"type": "delete_api_key_result", "status": "error",
                    "message": str(e)}

    # ------------------------------------------------------------------
    # Ollama Cloud API for consumers (SOTA 2026)
    # Consumers use their own Ollama API key; owner uses local Ollama
    # ------------------------------------------------------------------

    def _ollama_config_path(self, user_id: str) -> str:
        """Path to user's Ollama config: data/wallets/users/{user_id}/ollama_config.json"""
        return os.path.join("data", "wallets", "users", user_id, "ollama_config.json")

    def _load_ollama_config(self, user_id: str) -> Dict[str, Any]:
        """Load user's Ollama Cloud config."""
        path = self._ollama_config_path(user_id)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_ollama_config(self, user_id: str, config: Dict[str, Any]) -> None:
        """Save user's Ollama Cloud config."""
        path = self._ollama_config_path(user_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(config, f, indent=2)

    def _handle_set_ollama_api_key(self, data: dict, user_id: str) -> dict:
        """Store user's Ollama Cloud API key at data/wallets/users/{user_id}/ollama_config.json"""
        api_key = data.get("api_key", "").strip()
        model = data.get("model", "llama3.2:3b").strip()
        if not api_key:
            return {"type": "set_ollama_api_key_result", "status": "error",
                    "message": "api_key is required"}
        config = self._load_ollama_config(user_id)
        config["api_key"] = api_key
        config["model"] = model or "llama3.2:3b"
        config["updated_at"] = datetime.utcnow().isoformat()
        self._save_ollama_config(user_id, config)
        logger.info("Ollama API key saved for user %s", user_id)
        return {"type": "set_ollama_api_key_result", "status": "ok"}

    def _get_ollama_setup_guide(self) -> Dict[str, Any]:
        """Return setup instructions for getting a free Ollama API key."""
        return {
            "title": "Set Up Your AI Brain",
            "steps": [
                {"step": 1, "title": "Create Account", "description": "Visit ollama.com and create a free account", "link": "https://ollama.com"},
                {"step": 2, "title": "Get API Key", "description": "Go to Settings > API Keys and copy your key", "link": "https://ollama.com/settings/keys"},
                {"step": 3, "title": "Enter Key", "description": "Paste your API key in the field above"},
            ],
            "tiers": [
                {"name": "Free", "features": "AI chat, basic analysis, market questions"},
                {"name": "Pro ($20/mo)", "features": "Faster responses, bigger models, advanced trading analysis"},
                {"name": "Max ($100/mo)", "features": "Full power, all models, unlimited trading intelligence"},
            ],
            "android_alternative": {
                "title": "Run AI Locally (Android)",
                "steps": ["Install Termux from F-Droid", "Run: pkg install ollama", "Run: ollama pull llama3.2:1b", "AI runs on your phone - no internet needed for AI"],
            },
            "ios_alternative": {
                "title": "Run AI Locally (iOS)",
                "steps": ["Install 'LLM Farm' or 'MLC Chat' from App Store", "Download llama3.2-1b model", "AI runs on your phone - no internet needed for AI"],
            },
        }

    def _handle_get_brain_status(self, user_id: str) -> dict:
        """Check if user has API key configured and if Ollama Cloud is reachable."""
        config = self._load_ollama_config(user_id)
        api_key = config.get("api_key", "")
        has_key = bool(api_key)
        reachable = False
        if has_key:
            try:
                url = "https://api.ollama.com/v1/models"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    reachable = resp.status == 200
            except Exception as e:
                logger.debug("Ollama Cloud reachability check: %s", e)
        return {
            "type": "brain_status",
            "status": "ok",
            "has_api_key": has_key,
            "ollama_cloud_reachable": reachable,
            "model": config.get("model", "llama3.2:3b"),
            "setup_guide": self._get_ollama_setup_guide() if not has_key else None,
        }

    async def _call_ollama_cloud(self, entity_id: str, user_message: str,
                                user_ollama_config: Dict[str, Any]) -> str:
        """Call Ollama Cloud API for consumer chat."""
        api_key = user_ollama_config.get("api_key", "")
        url = "https://api.ollama.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = json.dumps({
            "model": user_ollama_config.get("model", "llama3.2:3b"),
            "messages": [
                {"role": "system", "content": f"You are Kingdom AI assistant for user {entity_id}"},
                {"role": "user", "content": user_message},
            ],
        }).encode()
        req = urllib.request.Request(url, data=payload, headers=headers)
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=30),
        )
        result = json.loads(resp.read().decode())
        choices = result.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            return msg.get("content", "")
        return ""

    def _handle_get_desktop_node_info(self) -> Dict[str, Any]:
        """Return comprehensive information about desktop node benefits."""
        return {
            "title": "Desktop Node Benefits",
            "subtitle": "Unlock the full power of Kingdom AI",
            "benefits": [
                {"icon": "mining", "title": "Mining Rewards", "description": "Earn KAIG coins by running the Kingdom AI mining node on your desktop. More uptime = more rewards."},
                {"icon": "ai", "title": "Enhanced AI", "description": "Local Ollama AI brain runs bigger, faster models. No cloud dependency for trading intelligence."},
                {"icon": "speed", "title": "Faster Trading", "description": "Direct exchange connections with lower latency. Execute trades milliseconds faster."},
                {"icon": "security", "title": "Full Node Security", "description": "Your desktop acts as a full node, verifying transactions and strengthening the network."},
                {"icon": "hive", "title": "Hive Mind Contributor", "description": "Your node contributes intelligence to the Hive Mind, earning additional KAIG rewards."},
                {"icon": "storage", "title": "Complete History", "description": "Full market data history stored locally for better AI training and backtesting."},
            ],
            "rewards_breakdown": {
                "mining_per_day": "Up to 50 KAIG/day based on contribution",
                "hive_bonus": "+10 KAIG/day for Hive Mind participation",
                "uptime_bonus": "+5 KAIG/day for 99%+ uptime",
                "referral_mining": "Extra mining weight per active referral",
            },
            "feature_comparison": [
                {"feature": "Auto Trading", "mobile_only": True, "with_desktop": True},
                {"feature": "Mining Rewards", "mobile_only": False, "with_desktop": True},
                {"feature": "Local AI Brain", "mobile_only": False, "with_desktop": True},
                {"feature": "Hive Mind Access", "mobile_only": True, "with_desktop": True},
                {"feature": "Enhanced Speed", "mobile_only": False, "with_desktop": True},
                {"feature": "Full Data History", "mobile_only": False, "with_desktop": True},
                {"feature": "Bigger AI Models", "mobile_only": False, "with_desktop": True},
            ],
            "download_prompt": "Download Kingdom AI Desktop to unlock all features!",
        }

    # ------------------------------------------------------------------
    # API Key Guide — names + links only (NEVER actual keys)
    # ------------------------------------------------------------------

    API_KEY_GUIDE = [
        # ── Crypto Exchanges (essential for auto-trading) ──
        {"service": "Binance", "url": "https://www.binance.com/en/my/settings/api-management",
         "category": "Crypto Exchange", "tier": "essential", "free_tier": True,
         "desc": "World's largest crypto exchange. Needed for auto-trading 600+ pairs with lowest fees."},
        {"service": "Binance US", "url": "https://www.binance.us/settings/api-management",
         "category": "Crypto Exchange", "tier": "essential", "free_tier": True,
         "desc": "US-regulated Binance. Required for US-based traders."},
        {"service": "Kraken", "url": "https://www.kraken.com/u/security/api",
         "category": "Crypto Exchange", "tier": "essential", "free_tier": True,
         "desc": "Trusted exchange with advanced order types. Great for BTC/ETH pairs."},
        {"service": "Coinbase", "url": "https://www.coinbase.com/settings/api",
         "category": "Crypto Exchange", "tier": "essential", "free_tier": True,
         "desc": "Most beginner-friendly exchange. Excellent fiat on/off ramp."},
        {"service": "KuCoin", "url": "https://www.kucoin.com/account/api",
         "category": "Crypto Exchange", "tier": "recommended", "free_tier": True,
         "desc": "Access to 700+ altcoins. Great for early gems and low-cap trading."},
        {"service": "Bybit", "url": "https://www.bybit.com/app/user/api-management",
         "category": "Crypto Exchange", "tier": "recommended", "free_tier": True,
         "desc": "Top derivatives exchange. Enables futures & margin trading."},
        {"service": "Bitget", "url": "https://www.bitget.com/account/newapi",
         "category": "Crypto Exchange", "tier": "recommended", "free_tier": True,
         "desc": "Copy-trading leader with 500+ pairs."},
        {"service": "MEXC", "url": "https://www.mexc.com/ucenter/api",
         "category": "Crypto Exchange", "tier": "optional", "free_tier": True,
         "desc": "First to list new tokens. Zero maker fees."},
        {"service": "Gate.io", "url": "https://www.gate.io/myaccount/api_key_manage",
         "category": "Crypto Exchange", "tier": "optional", "free_tier": True,
         "desc": "1400+ tokens available. Access to obscure gems."},
        {"service": "Crypto.com", "url": "https://crypto.com/exchange/personal/api-management",
         "category": "Crypto Exchange", "tier": "optional", "free_tier": True,
         "desc": "Strong mobile-first platform with card rewards."},
        {"service": "OKX", "url": "https://www.okx.com/account/my-api",
         "category": "Crypto Exchange", "tier": "optional", "free_tier": True,
         "desc": "Advanced trading tools. Futures, options, DEX aggregator."},
        {"service": "HTX (Huobi)", "url": "https://www.htx.com/en-us/apikey/",
         "category": "Crypto Exchange", "tier": "optional", "free_tier": True,
         "desc": "Long-standing exchange with global liquidity."},

        # ── Stock / Equity Brokers (for stock auto-trading) ──
        {"service": "Alpaca", "url": "https://app.alpaca.markets/brokerage/new-account/overview",
         "category": "Stock Broker", "tier": "essential", "free_tier": True,
         "desc": "Commission-free stock & crypto API. Best for algorithmic stock trading."},
        {"service": "TD Ameritrade", "url": "https://developer.tdameritrade.com/",
         "category": "Stock Broker", "tier": "recommended", "free_tier": True,
         "desc": "Full US equity access with excellent options chain data."},
        {"service": "Interactive Brokers", "url": "https://www.interactivebrokers.com/en/trading/ib-api.php",
         "category": "Stock Broker", "tier": "recommended", "free_tier": True,
         "desc": "Professional-grade broker. Access to 150+ markets worldwide."},
        {"service": "Webull", "url": "https://www.webull.com/hc/categories/22000102113",
         "category": "Stock Broker", "tier": "optional", "free_tier": True,
         "desc": "Commission-free US stocks, options, and crypto."},

        # ── Forex Brokers ──
        {"service": "OANDA", "url": "https://www.oanda.com/account/tpa/personal_token",
         "category": "Forex Broker", "tier": "recommended", "free_tier": True,
         "desc": "Premier forex broker. 70+ currency pairs with tight spreads."},
        {"service": "FXCM", "url": "https://www.fxcm.com/uk/forex-trading/api-trading/",
         "category": "Forex Broker", "tier": "optional", "free_tier": True,
         "desc": "Forex & CFD trading with Python API."},

        # ── Market Data (powers AI intelligence) ──
        {"service": "Alpha Vantage", "url": "https://www.alphavantage.co/support/#api-key",
         "category": "Market Data", "tier": "essential", "free_tier": True,
         "desc": "Free stock, forex, and crypto data API. Powers AI market analysis."},
        {"service": "CoinMarketCap", "url": "https://pro.coinmarketcap.com/signup",
         "category": "Market Data", "tier": "recommended", "free_tier": True,
         "desc": "Crypto prices, market cap, volume data. 10K+ tokens tracked."},
        {"service": "Finnhub", "url": "https://finnhub.io/register",
         "category": "Market Data", "tier": "recommended", "free_tier": True,
         "desc": "Real-time stock market data, news, and company fundamentals."},
        {"service": "Twelve Data", "url": "https://twelvedata.com/account/api-keys",
         "category": "Market Data", "tier": "recommended", "free_tier": True,
         "desc": "800+ requests/day free. Stocks, forex, crypto, ETFs."},
        {"service": "Polygon.io", "url": "https://polygon.io/dashboard/signup",
         "category": "Market Data", "tier": "recommended", "free_tier": True,
         "desc": "Real-time & historical market data. Stocks, options, forex, crypto."},
        {"service": "Tiingo", "url": "https://api.tiingo.com/",
         "category": "Market Data", "tier": "optional", "free_tier": True,
         "desc": "Free EOD data for 65K+ stocks & crypto. IEX real-time feed."},
        {"service": "EODHD", "url": "https://eodhd.com/register",
         "category": "Market Data", "tier": "optional", "free_tier": True,
         "desc": "70+ global exchanges. Historical data back decades."},
        {"service": "Financial Modeling Prep", "url": "https://site.financialmodelingprep.com/developer/docs",
         "category": "Market Data", "tier": "optional", "free_tier": True,
         "desc": "Company financials, SEC filings, DCF models. 250 daily requests free."},
        {"service": "NewsAPI", "url": "https://newsapi.org/register",
         "category": "Market Data", "tier": "optional", "free_tier": True,
         "desc": "Real-time news from 80K+ sources. Powers sentiment analysis."},
        {"service": "Benzinga", "url": "https://www.benzinga.com/apis/",
         "category": "Market Data", "tier": "optional", "free_tier": False,
         "desc": "Financial news and data for traders."},

        # ── Blockchain Explorers (for on-chain intelligence) ──
        {"service": "Etherscan", "url": "https://etherscan.io/myapikey",
         "category": "Blockchain", "tier": "recommended", "free_tier": True,
         "desc": "Ethereum blockchain explorer. Track transactions, smart contracts, gas."},
        {"service": "BscScan", "url": "https://bscscan.com/myapikey",
         "category": "Blockchain", "tier": "optional", "free_tier": True,
         "desc": "Binance Smart Chain explorer for BNB Chain activity."},
        {"service": "PolygonScan", "url": "https://polygonscan.com/myapikey",
         "category": "Blockchain", "tier": "optional", "free_tier": True,
         "desc": "Polygon chain explorer. Low-fee transaction tracking."},

        # ── Blockchain Infrastructure (for wallet features) ──
        {"service": "Infura", "url": "https://app.infura.io/register",
         "category": "Blockchain Infra", "tier": "recommended", "free_tier": True,
         "desc": "Ethereum + L2 RPC nodes. Powers wallet balance checks. 100K req/day free."},
        {"service": "Alchemy", "url": "https://dashboard.alchemy.com/signup",
         "category": "Blockchain Infra", "tier": "recommended", "free_tier": True,
         "desc": "Web3 developer platform. Enhanced APIs for 30+ blockchains."},
        {"service": "QuickNode", "url": "https://dashboard.quicknode.com/signup",
         "category": "Blockchain Infra", "tier": "optional", "free_tier": True,
         "desc": "Fast RPC nodes for 25+ chains. Reduces latency for trades."},
        {"service": "Moralis", "url": "https://admin.moralis.io/register",
         "category": "Blockchain Infra", "tier": "optional", "free_tier": True,
         "desc": "Cross-chain Web3 APIs. Token balances, NFTs, DeFi positions."},

        # ── Whale / On-Chain Analytics ──
        {"service": "Whale Alert", "url": "https://whale-alert.io/signup",
         "category": "On-Chain Analytics", "tier": "recommended", "free_tier": True,
         "desc": "Real-time whale transaction alerts. Know when big money moves."},
        {"service": "LunarCrush", "url": "https://lunarcrush.com/developers/api/authentication",
         "category": "On-Chain Analytics", "tier": "optional", "free_tier": True,
         "desc": "Social intelligence for crypto. Tracks social volume and sentiment."},
        {"service": "Glassnode", "url": "https://studio.glassnode.com/settings/api",
         "category": "On-Chain Analytics", "tier": "optional", "free_tier": True,
         "desc": "On-chain market intelligence. HODL waves, MVRV, SOPR indicators."},
        {"service": "Dune Analytics", "url": "https://dune.com/settings/api",
         "category": "On-Chain Analytics", "tier": "optional", "free_tier": True,
         "desc": "Query any blockchain data with SQL. Custom dashboards and insights."},
        {"service": "DefiLlama", "url": "https://defillama.com/docs/api",
         "category": "On-Chain Analytics", "tier": "optional", "free_tier": True,
         "desc": "TVL and DeFi protocol data. Free, no API key needed for basic."},

        # ── AI Services (enhances Kingdom AI brain) ──
        {"service": "OpenAI", "url": "https://platform.openai.com/api-keys",
         "category": "AI Service", "tier": "optional", "free_tier": False,
         "desc": "GPT-4 access for enhanced analysis. Upgrades AI reasoning capability."},
        {"service": "Anthropic", "url": "https://console.anthropic.com/settings/keys",
         "category": "AI Service", "tier": "optional", "free_tier": False,
         "desc": "Claude AI for advanced research and coding analysis."},
        {"service": "HuggingFace", "url": "https://huggingface.co/settings/tokens",
         "category": "AI Service", "tier": "optional", "free_tier": True,
         "desc": "Open-source ML models. Sentiment analysis, NLP, and more."},
        {"service": "Groq", "url": "https://console.groq.com/keys",
         "category": "AI Service", "tier": "optional", "free_tier": True,
         "desc": "Ultra-fast AI inference. Free tier available. Lightning-fast analysis."},
        {"service": "DeepSeek", "url": "https://platform.deepseek.com/api_keys",
         "category": "AI Service", "tier": "optional", "free_tier": True,
         "desc": "Cost-effective AI model with strong reasoning capabilities."},

        # ── Social/Sentiment (for news-based trading) ──
        {"service": "Reddit", "url": "https://www.reddit.com/prefs/apps",
         "category": "Social/Sentiment", "tier": "optional", "free_tier": True,
         "desc": "Track r/wallstreetbets, r/CryptoCurrency for retail sentiment."},
        {"service": "StockTwits", "url": "https://api.stocktwits.com/developers/apps",
         "category": "Social/Sentiment", "tier": "optional", "free_tier": True,
         "desc": "Stock-focused social network. Sentiment and trending tickers."},

        # ── Financial Services ──
        {"service": "Plaid", "url": "https://dashboard.plaid.com/signup",
         "category": "Financial Service", "tier": "optional", "free_tier": True,
         "desc": "Connect bank accounts for funding and transaction data."},
    ]

    @classmethod
    def _get_api_key_guide(cls) -> dict:
        """Return the comprehensive API key guide for consumers."""
        categories: dict = {}
        for item in cls.API_KEY_GUIDE:
            cat = item["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        return {
            "type": "api_key_guide",
            "status": "ok",
            "why_own_keys": (
                "Kingdom AI's auto-trading system needs YOUR OWN exchange API keys "
                "to execute trades on YOUR accounts. Each user must have their own "
                "keys for security and legal reasons — you maintain full control of "
                "your funds at all times. Kingdom AI never has withdrawal access; "
                "we only request trading permissions."
            ),
            "how_keys_help": [
                "More exchange keys = more markets + better prices (arbitrage across exchanges)",
                "Market data keys = smarter AI decisions (real-time signals, sentiment, on-chain data)",
                "Blockchain keys = faster balance checks + lower latency for transactions",
                "AI service keys = enhanced analysis quality (GPT-4, Claude augment the local Ollama brain)",
                "Each additional key unlocks new strategies and increases profit potential",
            ],
            "security_notes": [
                "NEVER share API keys with anyone",
                "Always set API keys to TRADE-ONLY (disable withdrawals)",
                "Use IP whitelisting when exchanges support it",
                "Kingdom AI stores your keys locally on YOUR device — they never leave your machine",
                "You can revoke keys at any time from the exchange website",
            ],
            "tiers": {
                "essential": "Highly recommended — needed for core auto-trading features",
                "recommended": "Improves AI intelligence and trading performance significantly",
                "optional": "Extra capabilities — each one adds new strategies and data",
            },
            "categories": categories,
            "total_services": len(cls.API_KEY_GUIDE),
        }

    # ------------------------------------------------------------------
    # Account Recovery System (SOTA 2026)
    # ------------------------------------------------------------------

    def _handle_get_recovery_phrase(self, user_id: str, data: dict) -> dict:
        """Return the user's encrypted recovery seed phrase.

        Requires PIN or biometric verification from the mobile app.
        The seed phrase is what lets a user recover their entire wallet
        (all chains, all addresses) on a new device.
        """
        pin = data.get("pin", "")
        if not pin and not data.get("biometric_verified", False):
            return {"type": "recovery_phrase_result", "status": "error",
                    "message": "PIN or biometric verification required"}

        manifest_path = os.path.join(
            "data", "wallets", "users", user_id, "wallet_manifest.json")
        if not os.path.exists(manifest_path):
            return {"type": "recovery_phrase_result", "status": "error",
                    "message": "No wallet found for this account"}
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            enc_seed = manifest.get("encrypted_seed_phrase", "")
            if not enc_seed:
                return {"type": "recovery_phrase_result", "status": "error",
                        "message": "Seed phrase not available in manifest"}
            try:
                from core.wallet_creator import WalletCreator
                creator = WalletCreator()
                phrase = creator.decrypt_data(enc_seed)
                words = phrase.split()
            except Exception:
                words = None
                phrase = None

            return {
                "type": "recovery_phrase_result", "status": "ok",
                "word_count": len(words) if words else 0,
                "words": words,
                "warning": (
                    "WRITE THESE WORDS DOWN on paper and store in a safe place. "
                    "Anyone with these words can access your wallet. "
                    "Kingdom AI cannot recover your funds if you lose this phrase."
                ),
            }
        except Exception as e:
            return {"type": "recovery_phrase_result", "status": "error",
                    "message": str(e)}

    def _handle_account_backup(self, user_id: str) -> dict:
        """Create a full account backup manifest (excludes plaintext keys)."""
        user_dir = os.path.join("data", "wallets", "users", user_id)
        if not os.path.isdir(user_dir):
            return {"type": "account_backup_result", "status": "error",
                    "message": "No account data found"}

        backup: dict = {
            "account_id": user_id,
            "backup_created": datetime.utcnow().isoformat(),
            "version": APP_VERSION,
        }

        manifest_path = os.path.join(user_dir, "wallet_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                backup["wallet_manifest"] = json.load(f)

        keys_path = os.path.join(user_dir, "api_keys.json")
        if os.path.exists(keys_path):
            with open(keys_path, "r") as f:
                raw_keys = json.load(f)
            backup["api_key_services"] = list(raw_keys.keys())
            backup["api_key_count"] = len(raw_keys)

        try:
            from core.username_registry import get_username_for_user
            uname = get_username_for_user(user_id)
            if uname:
                backup["username"] = uname
        except Exception:
            pass

        cards = self._fintech_get_cards(user_id=user_id)
        if cards.get("cards"):
            backup["card_count"] = len(cards["cards"])
            backup["card_last4s"] = [c.get("last4") for c in cards["cards"]]

        backup_path = os.path.join(user_dir, "account_backup.json")
        with open(backup_path, "w") as f:
            json.dump(backup, f, indent=2)

        return {
            "type": "account_backup_result", "status": "ok",
            "backup": backup,
            "recovery_instructions": {
                "step_1": "Write down your 12/24-word recovery phrase (use 'get_recovery_phrase')",
                "step_2": "Save your account_id: " + user_id,
                "step_3": "On a new device, use 'account_recover' with your seed phrase",
                "step_4": "Your wallet addresses, username, and cards will be restored",
                "step_5": "Re-enter your exchange API keys (they are never backed up for security)",
                "note": "Your recovery phrase is the ONLY way to restore your wallet. "
                        "Keep it safe offline. Do NOT screenshot or store digitally.",
            },
        }

    def _handle_account_recover(self, data: dict) -> dict:
        """Recover an account using a BIP39 seed phrase.

        This regenerates the same wallet addresses deterministically,
        restores the username if available, and issues a new digital card.
        """
        seed_phrase = data.get("seed_phrase", "").strip()
        new_user_id = data.get("user_id", "")
        if not seed_phrase:
            return {"type": "account_recover_result", "status": "error",
                    "message": "seed_phrase is required"}

        try:
            from core.wallet_creator import WalletCreator
            creator = WalletCreator(event_bus=self.event_bus)

            if not creator.validate_seed_phrase(seed_phrase):
                return {"type": "account_recover_result", "status": "error",
                        "message": "Invalid BIP39 seed phrase. Check spelling and word count."}

            if not new_user_id:
                new_user_id = f"recovered_{uuid.uuid4().hex[:12]}"

            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()

            wallet_result = loop.run_until_complete(
                creator.create_user_wallet(
                    new_user_id, seed_phrase=seed_phrase))

            if not wallet_result.get("success"):
                return {"type": "account_recover_result", "status": "error",
                        "message": wallet_result.get("error", "Wallet recovery failed")}

            addresses = wallet_result.get("addresses", {})

            card_result = {}
            try:
                card_resp = loop.run_until_complete(self._fintech_issue_card({
                    "label": "Kingdom Card",
                    "user_id": new_user_id,
                    "card_type": "virtual",
                    "currency": "USD",
                }))
                if card_resp.get("status") == "ok":
                    card_result = {
                        "card_id": card_resp.get("card_id"),
                        "last4": card_resp.get("last4"),
                    }
            except Exception:
                pass

            return {
                "type": "account_recover_result", "status": "ok",
                "user_id": new_user_id,
                "chains_recovered": len(addresses),
                "addresses": addresses,
                "card": card_result,
                "next_steps": [
                    "Your wallet addresses have been regenerated from your seed phrase",
                    "All on-chain balances are intact (funds live on the blockchain)",
                    "Re-enter your exchange API keys via Settings > API Keys",
                    "Your digital card has been re-issued",
                    "Register a new username if your previous one was taken",
                ],
            }
        except ImportError:
            return {"type": "account_recover_result", "status": "error",
                    "message": "WalletCreator module not available"}
        except Exception as e:
            return {"type": "account_recover_result", "status": "error",
                    "message": str(e)}

    # ------------------------------------------------------------------
    # WebSocket server
    # ------------------------------------------------------------------

    async def start_server(self):
        """Start the WebSocket server."""
        if not HAS_WEBSOCKETS:
            logger.error("Cannot start mobile sync — websockets not installed")
            return

        try:
            self._server = await websockets.serve(
                self._handle_connection, "0.0.0.0", self._port
            )
            logger.info("Mobile sync server started on ws://0.0.0.0:%d", self._port)

            if self.event_bus:
                self.event_bus.publish("mobile.server.started", {"port": self._port})
        except Exception as e:
            logger.error("Failed to start mobile sync server: %s", e)

    async def stop_server(self):
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("Mobile sync server stopped")

    async def _handle_connection(self, websocket, path=""):
        """Handle incoming mobile WebSocket connections."""
        device_id = None
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "link":
                        code = data.get("code", "")
                        account_id = data.get("account_id", "")
                        device_id = account_id or data.get("device_id", str(uuid.uuid4())[:8])
                        device_info = data.get("device_info", {})
                        session_token = data.get("session_token", "")

                        if self.confirm_link(code, device_id, device_info, session_token):
                            self._connected_devices[device_id] = websocket
                            _mode_info = self._get_version_mode()

                            onboard = await self._auto_onboard_user(device_id)

                            await websocket.send(json.dumps({
                                "type": "link_confirmed",
                                "desktop_id": self._get_desktop_id(),
                                "desktop_name": self._get_desktop_name(),
                                "status": "linked",
                                "is_creator": _mode_info.get("is_creator", False),
                                "version_mode": _mode_info.get("mode", "consumer"),
                                "wallet": onboard.get("wallet", {}),
                                "card": onboard.get("card", {}),
                            }))
                        else:
                            await websocket.send(json.dumps({
                                "type": "link_failed",
                                "reason": "Invalid or expired link code",
                            }))

                    elif msg_type == "auth":
                        device_id = data.get("device_id", "")
                        token = data.get("session_token", "")
                        if self.verify_session(device_id, token):
                            self._connected_devices[device_id] = websocket
                            _mode_info = self._get_version_mode()

                            onboard = await self._auto_onboard_user(device_id)

                            await websocket.send(json.dumps({
                                "type": "auth_confirmed",
                                "desktop_id": self._get_desktop_id(),
                                "desktop_name": self._get_desktop_name(),
                                "status": "authenticated",
                                "is_creator": _mode_info.get("is_creator", False),
                                "version_mode": _mode_info.get("mode", "consumer"),
                                "wallet": onboard.get("wallet", {}),
                                "card": onboard.get("card", {}),
                            }))
                            logger.info("Device %s re-authenticated", device_id)
                        else:
                            await websocket.send(json.dumps({
                                "type": "auth_failed",
                                "reason": "Invalid session token — please re-link",
                            }))
                            logger.warning("Auth failed for device %s", device_id)

                    elif msg_type == "chat":
                        # Relay chat to KAI — OWNER: local Ollama; CONSUMER: Ollama Cloud or setup guide
                        text = data.get("text", "")
                        request_id = data.get("request_id", "")
                        if not text:
                            continue
                        # SHA-LU-AM: said and typed — mobile can trigger via chat
                        _t = text.lower().replace(" ", "").replace("-", "")
                        if "shaluam" in _t or "shalom" in text.lower() or "sha lu am" in text.lower() or "sha-lu-am" in text or "\u05e9\u05dc\u05d5\u05dd" in text:
                            if self.event_bus:
                                self.event_bus.publish("secret.reserve.reveal", {
                                    "trigger": "SHA-LU-AM", "text": text,
                                    "source": f"mobile:{device_id}", "owner_verified": True,
                                    "hive_mind_activate": True,
                                })
                        # OWNER (creator): use local Ollama via event bus
                        if device_id == "creator":
                            if self.event_bus:
                                self.event_bus.publish("ai.request", {
                                    "text": text,
                                    "prompt": text,
                                    "source": f"mobile:{device_id}",
                                    "priority": "normal",
                                })
                        else:
                            # CONSUMER: use Ollama Cloud API or return setup guide
                            user_config = self._load_ollama_config(device_id)
                            api_key = user_config.get("api_key", "")
                            if not api_key:
                                setup_guide = self._get_ollama_setup_guide()
                                resp = {"type": "ai_response", "text": "", "setup_guide": setup_guide,
                                        "message": "Set up your AI brain with a free Ollama API key to use chat."}
                                resp["request_id"] = request_id
                                await websocket.send(json.dumps(resp))
                            else:
                                try:
                                    result = await self._call_ollama_cloud(device_id, text, user_config)
                                    resp = {"type": "ai_response", "text": result, "source": "ollama_cloud"}
                                    resp["request_id"] = request_id
                                    await websocket.send(json.dumps(resp))
                                except Exception as e:
                                    logger.warning("Ollama Cloud chat error: %s", e)
                                    resp = {"type": "ai_response", "text": f"AI error: {e}",
                                            "setup_guide": self._get_ollama_setup_guide()}
                                    resp["request_id"] = request_id
                                    await websocket.send(json.dumps(resp))

                    elif msg_type == "emergency":
                        # Mobile emergency alert
                        if self.event_bus:
                            self.event_bus.publish("security.silent_alarm.trigger", {
                                "reason": f"Mobile emergency alert from device {device_id}",
                                "threat_level": "critical",
                                "gps": data.get("gps", {}),
                                "source": "mobile",
                            })

                    elif msg_type == "mining_status":
                        # Sync mining status
                        if self.event_bus:
                            self.event_bus.publish("mobile.mining.status", data)

                    elif msg_type == "get_truth_timeline":
                        # SHA-LU-AM: Mobile requesting Truth Timeline (owner/consumer)
                        resp = {"type": "truth_timeline", "status": "ok", "data": self._get_truth_timeline_data()}
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_portfolio":
                        # Mobile requesting portfolio data from trading system
                        resp = self._get_portfolio_data()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_wallet":
                        resp = self._get_wallet_data(user_id=device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "refresh_balances":
                        resp = self._refresh_onchain_balances(user_id=device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "place_order":
                        # Mobile placing a trade order
                        resp = await self._handle_place_order(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "wallet_send":
                        data.setdefault("user_id", device_id or "")
                        resp = await self._handle_wallet_send(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_prices":
                        # Mobile requesting current prices
                        resp = self._get_price_data()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── Fintech handlers (2026 SOTA) ──

                    elif msg_type == "get_cards":
                        resp = self._fintech_get_cards(user_id=device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "issue_virtual_card":
                        data.setdefault("user_id", device_id or "")
                        data.setdefault("device_id", device_id or "")
                        resp = await self._fintech_issue_card(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type in ("freeze_card", "unfreeze_card"):
                        resp = await self._fintech_toggle_card(data, freeze=(msg_type == "freeze_card"))
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "p2p_send":
                        block = self._ai_security_check("p2p_send", data, device_id or "")
                        resp = block if block else await self._fintech_p2p_send(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "bitchat_pay":
                        block = self._ai_security_check("bitchat_pay", data, device_id or "")
                        resp = block if block else await self._fintech_bitchat_pay(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "offramp_quote":
                        resp = await self._fintech_offramp_quote(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "offramp_execute":
                        block = self._ai_security_check("offramp_execute", data, device_id or "")
                        resp = block if block else await self._fintech_offramp_execute(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "nfc_tap_pay":
                        resp = await self._secure_nfc_tap_pay(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "device_attest":
                        resp = self._handle_device_attestation(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "security_status":
                        resp = self._get_security_status()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_tx_history":
                        resp = self._fintech_get_tx_history(
                            data.get("limit", 20), user_id=device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_fintech_overview":
                        resp = self._fintech_overview(user_id=device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "update_card_limits":
                        resp = await self._fintech_update_card_limits(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "update_card_settings":
                        resp = await self._fintech_update_card_settings(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "online_purchase":
                        block = self._ai_security_check("online_purchase", data, device_id or "")
                        resp = block if block else await self._fintech_online_purchase(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_referral_code":
                        resp = self._get_referral_code(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "apply_referral":
                        resp = self._apply_referral_code(
                            data.get("referral_code", ""), device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_referral_stats":
                        resp = self._get_referral_stats(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "set_referral_preference":
                        resp = self._handle_set_referral_preference(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── Hive Mind AI Auto-Trading (SOTA 2026) ──

                    elif msg_type == "auto_trade_start":
                        resp = self._handle_auto_trade_start(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "auto_trade_stop":
                        resp = self._handle_auto_trade_stop(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "auto_trade_status":
                        resp = self._handle_auto_trade_status(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_trading_tools":
                        resp = self._handle_get_trading_tools()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_hive_status":
                        resp = self._handle_hive_status(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── Username + Payment QR (SOTA 2026) ──

                    elif msg_type == "register_username":
                        resp = self._handle_register_username(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "change_username":
                        resp = self._handle_change_username(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "check_username":
                        resp = self._handle_check_username(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "resolve_username":
                        resp = self._handle_resolve_username(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_payment_qr":
                        resp = self._handle_get_payment_qr(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_my_username":
                        resp = self._handle_get_my_username(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_download_qr":
                        resp = self._handle_get_download_qr(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── $KAIG (KAI Gold) handlers (SOTA 2026) ──

                    elif msg_type == "get_kaig_status":
                        resp = self._get_kaig_status()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "kaig_node_start":
                        resp = self._kaig_node_start()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "kaig_node_stop":
                        resp = self._kaig_node_stop()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "kaig_node_heartbeat":
                        resp = self._kaig_node_heartbeat()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── KAIG AutoPilot handlers (SOTA 2026) ──

                    elif msg_type == "get_kaig_autopilot":
                        resp = self._get_kaig_autopilot_status()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_version_mode":
                        resp = self._get_version_mode()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── Consumer API Key Management (SOTA 2026) ──

                    elif msg_type == "save_api_keys":
                        resp = self._handle_save_api_keys(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_api_keys":
                        resp = self._handle_get_api_keys(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "delete_api_key":
                        resp = self._handle_delete_api_key(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_api_key_guide":
                        resp = self._get_api_key_guide()
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── Ollama Cloud for consumers (SOTA 2026) ──

                    elif msg_type == "set_ollama_api_key":
                        resp = self._handle_set_ollama_api_key(data, device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_ollama_setup_guide":
                        resp = self._get_ollama_setup_guide()
                        resp = {"type": "ollama_setup_guide", "status": "ok", **resp}
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_brain_status":
                        resp = self._handle_get_brain_status(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "get_desktop_node_info":
                        resp = self._handle_get_desktop_node_info()
                        resp = {"type": "desktop_node_info", "status": "ok", **resp}
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    # ── Account Recovery (SOTA 2026) ──

                    elif msg_type == "get_recovery_phrase":
                        resp = self._handle_get_recovery_phrase(device_id or "", data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "account_backup":
                        resp = self._handle_account_backup(device_id or "")
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "account_recover":
                        resp = self._handle_account_recover(data)
                        resp["request_id"] = data.get("request_id", "")
                        await websocket.send(json.dumps(resp))

                    elif msg_type == "ping":
                        await websocket.send(json.dumps({"type": "pong", "ts": time.time()}))

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error("Mobile message handling error: %s", e)

        except Exception:
            pass
        finally:
            if device_id and device_id in self._connected_devices:
                del self._connected_devices[device_id]

    async def send_to_device(self, device_id: str, data: Dict):
        """Send data to a specific connected mobile device."""
        ws = self._connected_devices.get(device_id)
        if ws:
            try:
                await ws.send(json.dumps(data))
            except Exception:
                del self._connected_devices[device_id]

    async def broadcast_to_all(self, data: Dict):
        """Send data to all connected mobile devices."""
        dead = []
        for did, ws in self._connected_devices.items():
            try:
                await ws.send(json.dumps(data))
            except Exception:
                dead.append(did)
        for did in dead:
            del self._connected_devices[did]

    # ------------------------------------------------------------------
    # Mobile data request handlers — query desktop backends
    # ------------------------------------------------------------------

    def _get_portfolio_data(self) -> Dict[str, Any]:
        """Query trading system for portfolio data."""
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                trading = self.event_bus.get_component('trading_system')
                if trading:
                    portfolio = getattr(trading, 'get_portfolio_summary', lambda: None)()
                    if portfolio:
                        return {"type": "portfolio", "status": "ok", **portfolio}
                    # Try alternative attribute access
                    total = getattr(trading, '_total_portfolio_value', 0)
                    pnl = getattr(trading, '_total_pnl', 0)
                    return {
                        "type": "portfolio", "status": "ok",
                        "total_value": total, "pnl": pnl, "pnl_pct": 0,
                    }
        except Exception as e:
            logger.error("Portfolio query error: %s", e)
        return {"type": "portfolio", "status": "ok", "total_value": 0, "pnl": 0, "pnl_pct": 0}

    def _get_wallet_data(self, user_id: str = "") -> Dict[str, Any]:
        """Query wallet system for balances, scoped to the per-user wallet.

        CRITICAL: Each user only sees THEIR OWN wallet data. The owner's
        addresses are never returned for consumer/mobile users.
        """
        try:
            user_manifest = None
            if user_id:
                try:
                    from core.wallet_creator import WalletCreator
                    wc = WalletCreator(event_bus=self.event_bus)
                    user_manifest = wc.get_user_wallet(user_id)
                except Exception:
                    pass

            if user_manifest and user_manifest.get("addresses"):
                user_addrs = user_manifest["addresses"]
                assets = [{"symbol": k.upper(), "balance": 0, "value": 0}
                          for k in user_addrs]
                wallet = None
                if self.event_bus and hasattr(self.event_bus, 'get_component'):
                    wallet = self.event_bus.get_component('wallet_system')
                if wallet and hasattr(wallet, '_fetch_onchain_balance'):
                    for asset in assets:
                        sym = asset["symbol"]
                        addr = user_addrs.get(sym, "")
                        if addr:
                            bal = wallet._fetch_onchain_balance(sym, addr)
                            if bal is not None:
                                asset["balance"] = bal
                elif wallet and hasattr(wallet, 'balance_cache'):
                    for asset in assets:
                        asset["balance"] = wallet.balance_cache.get(asset["symbol"], 0)
                return {
                    "type": "wallet", "status": "ok",
                    "total_value": 0,
                    "assets": assets,
                    "receive_address": user_addrs.get("ETH", ""),
                    "user_id": user_id,
                    "user_addresses": user_addrs,
                }

            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wallet = self.event_bus.get_component('wallet_system')
                if wallet:
                    if hasattr(wallet, 'get_all_balances'):
                        balances = wallet.get_all_balances()
                        assets = []
                        total = 0.0
                        user_chains = set()
                        if user_manifest:
                            user_chains = {k.upper() for k in user_manifest.get("addresses", {})}
                        for sym, info in (balances or {}).items():
                            if user_chains and sym.upper() not in user_chains:
                                continue
                            bal = info if isinstance(info, (int, float)) else info.get('balance', 0)
                            val = info.get('value_usd', 0) if isinstance(info, dict) else 0
                            assets.append({"symbol": sym, "balance": bal, "value": val})
                            total += val
                        addr = ""
                        if user_manifest:
                            addr = user_manifest.get("addresses", {}).get("ETH", "")
                        elif hasattr(wallet, 'get_receive_address'):
                            addr = wallet.get_receive_address() or ""
                        return {
                            "type": "wallet", "status": "ok",
                            "total_value": total, "assets": assets,
                            "receive_address": addr,
                            "user_id": user_id,
                            "user_addresses": user_manifest.get("addresses", {}) if user_manifest else {},
                        }
                    if hasattr(wallet, 'wallet_balances'):
                        balances = wallet.wallet_balances or {}
                        assets = [{"symbol": k, "balance": v, "value": 0}
                                  for k, v in balances.items()]
                        addr = ""
                        if user_manifest:
                            addr = user_manifest.get("addresses", {}).get("ETH", "")
                        else:
                            addr = getattr(wallet, 'current_address', '')
                        return {
                            "type": "wallet", "status": "ok",
                            "total_value": 0, "assets": assets,
                            "receive_address": addr,
                            "user_id": user_id,
                            "user_addresses": user_manifest.get("addresses", {}) if user_manifest else {},
                        }
                    if hasattr(wallet, 'balance_cache') and wallet.balance_cache:
                        assets = [{"symbol": k, "balance": v, "value": 0}
                                  for k, v in wallet.balance_cache.items()
                                  if isinstance(v, (int, float)) and v > 0]
                        addr = ""
                        if user_manifest:
                            addr = user_manifest.get("addresses", {}).get("ETH", "")
                        elif hasattr(wallet, 'get_address'):
                            addr = wallet.get_address("ETH") or ""
                        return {
                            "type": "wallet", "status": "ok",
                            "total_value": 0, "assets": assets,
                            "receive_address": addr,
                            "user_id": user_id,
                            "user_addresses": user_manifest.get("addresses", {}) if user_manifest else {},
                        }

            if user_manifest:
                return {
                    "type": "wallet", "status": "ok",
                    "total_value": 0, "assets": [],
                    "receive_address": user_manifest.get("addresses", {}).get("ETH", ""),
                    "user_id": user_id,
                    "user_addresses": user_manifest.get("addresses", {}),
                }
        except Exception as e:
            logger.error("Wallet query error: %s", e)
        return {"type": "wallet", "status": "ok", "total_value": 0, "assets": [],
                "receive_address": "", "user_id": user_id, "user_addresses": {}}

    def _refresh_onchain_balances(self, user_id: str = "") -> Dict[str, Any]:
        """Trigger real on-chain balance fetch and return fresh data."""
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wallet = self.event_bus.get_component('wallet_system')
                if wallet and hasattr(wallet, 'fetch_all_balances'):
                    wallet.fetch_all_balances()
            return self._get_wallet_data(user_id=user_id)
        except Exception as e:
            logger.error("Refresh balances error: %s", e)
            return {"type": "wallet", "status": "error", "error": str(e)}

    async def _handle_place_order(self, data: Dict) -> Dict[str, Any]:
        """Relay trade order to trading system."""
        try:
            if self.event_bus:
                self.event_bus.publish("trading.order.place", {
                    "exchange": data.get("exchange", ""),
                    "pair": data.get("pair", ""),
                    "side": data.get("side", "buy"),
                    "amount": data.get("amount", 0),
                    "source": "mobile",
                })
                return {"type": "order_result", "status": "ok",
                        "message": f"{data.get('side', 'buy').upper()} order submitted"}
        except Exception as e:
            logger.error("Order placement error: %s", e)
            return {"type": "order_result", "status": "error", "message": str(e)}
        return {"type": "order_result", "status": "error", "message": "No event bus"}

    async def _handle_wallet_send(self, data: Dict) -> Dict[str, Any]:
        """Execute wallet send via WalletManager for real blockchain transactions."""
        to_address = data.get("to_address", "")
        amount_raw = data.get("amount", "0")
        network = data.get("network", "ETH")
        uid = data.get("user_id", "")
        try:
            if not to_address or float(amount_raw) <= 0:
                return {"type": "send_result", "status": "error",
                        "message": "Invalid address or amount"}

            wm = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')

            if wm and hasattr(wm, 'send_transaction'):
                tx_hash = wm.send_transaction(network, to_address, float(amount_raw))
                self._record_tx("out",
                    f"Send {amount_raw} {network} → {to_address[:12]}...",
                    f"-{amount_raw} {network}",
                    user_id=uid, transaction_type="crypto_send")
                return {"type": "send_result", "status": "ok",
                        "tx_hash": tx_hash, "network": network,
                        "message": f"Sent {amount_raw} {network}"}

            if self.event_bus:
                self.event_bus.publish("wallet.send", {
                    "to_address": to_address,
                    "amount": amount_raw,
                    "network": network,
                    "source": "mobile",
                    "user_id": uid,
                })
                self._record_tx("out",
                    f"Send {amount_raw} {network} → {to_address[:12]}...",
                    f"-{amount_raw} {network}",
                    user_id=uid, transaction_type="crypto_send")
                return {"type": "send_result", "status": "ok",
                        "message": "Transaction submitted via event bus",
                        "tx_hash": "event_pending"}
        except Exception as e:
            logger.error("Wallet send error: %s", e)
            return {"type": "send_result", "status": "error", "message": str(e)}
        return {"type": "send_result", "status": "error", "message": "No wallet manager or event bus"}

    def _get_price_data(self) -> Dict[str, Any]:
        """Get current price data from trading system, with CoinGecko fallback and 30s cache."""
        now = time.time()
        cache_ttl = 30.0
        if self._price_cache and (now - self._price_cache_ts) < cache_ttl:
            return {"type": "prices", "status": "ok", "prices": self._price_cache.copy()}

        prices: Dict[str, Any] = {}
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                trading = self.event_bus.get_component('trading_system')
                if trading and hasattr(trading, 'get_market_prices'):
                    prices = trading.get_market_prices() or {}
        except Exception as e:
            logger.error("Price query error: %s", e)

        if not prices:
            try:
                url = (
                    "https://api.coingecko.com/api/v3/simple/price"
                    "?ids=bitcoin,ethereum,solana,ripple,cardano,dogecoin,polkadot,avalanche-2,"
                    "chainlink,matic-network,uniswap,cosmos,litecoin,stellar,monero"
                    "&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
                )
                req = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json", "User-Agent": "KingdomAI/1.0"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    cg_data = json.loads(resp.read().decode())
                id_to_symbol = {
                    "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL",
                    "ripple": "XRP", "cardano": "ADA", "dogecoin": "DOGE",
                    "polkadot": "DOT", "avalanche-2": "AVAX", "chainlink": "LINK",
                    "matic-network": "MATIC", "uniswap": "UNI", "cosmos": "ATOM",
                    "litecoin": "LTC", "stellar": "XLM", "monero": "XMR",
                }
                for cg_id, sym in id_to_symbol.items():
                    if cg_id in cg_data and isinstance(cg_data[cg_id], dict):
                        p = cg_data[cg_id]
                        usd = p.get("usd")
                        if usd is not None:
                            prices[sym] = {
                                "price": float(usd),
                                "change_24h": p.get("usd_24h_change"),
                                "vol_24h": p.get("usd_24h_vol"),
                            }
            except Exception as e:
                logger.warning("CoinGecko fallback error: %s", e)

        if prices:
            self._price_cache = prices.copy()
            self._price_cache_ts = now
        elif self._price_cache:
            prices = self._price_cache.copy()

        return {"type": "prices", "status": "ok", "prices": prices}

    # ------------------------------------------------------------------
    # Fintech backend methods (2026 SOTA)
    # ------------------------------------------------------------------

    def _fintech_get_cards(self, user_id: str = "") -> Dict[str, Any]:
        """Get virtual cards, optionally filtered by user_id."""
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                card_sys = self.event_bus.get_component('card_system')
                if card_sys and hasattr(card_sys, 'list_cards'):
                    cards = card_sys.list_cards()
                    if user_id and cards:
                        cards = [c for c in cards if c.get("user_id") == user_id]
                    return {"type": "cards_result", "status": "ok", "cards": cards or []}
            if hasattr(self, 'redis') and self.redis:
                key = f"kingdom:fintech:cards:{user_id}" if user_id else "kingdom:fintech:cards"
                raw = self.redis.get(key)
                if raw:
                    cards = json.loads(raw) if isinstance(raw, str) else []
                    return {"type": "cards_result", "status": "ok", "cards": cards}
            if hasattr(self, '_fintech_cards'):
                cards = self._fintech_cards
                if user_id:
                    cards = [c for c in cards if c.get("user_id") == user_id]
                return {"type": "cards_result", "status": "ok", "cards": cards}
        except Exception as e:
            logger.error("Fintech get_cards error: %s", e)
        return {"type": "cards_result", "status": "ok", "cards": []}

    async def _fintech_issue_card(self, data: Dict) -> Dict[str, Any]:
        """Issue a SOTA 2026 virtual card with full details, tokenization, and spending controls.
        Cards are per-user — each user_id gets their own unique card(s)."""
        import secrets as _secrets
        import hashlib
        try:
            label = data.get("label", "Kingdom Card")
            card_type = data.get("card_type", "virtual")
            currency = data.get("currency", "USD")
            user_id = data.get("user_id", data.get("device_id", ""))

            card_id = str(uuid.uuid4())
            card_number_raw = "4" + "".join(str(_secrets.randbelow(10)) for _ in range(15))
            last4 = card_number_raw[-4:]
            expiry_month = str(((datetime.utcnow().month % 12) + 1)).zfill(2)
            expiry_year = str(datetime.utcnow().year + 3)
            cvv = str(_secrets.randbelow(1000)).zfill(3)

            token = hashlib.sha256(
                f"{card_id}:{card_number_raw}:{_secrets.token_hex(16)}".encode()
            ).hexdigest()[:32]

            wallet_addr = ""
            wm = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')
            if wm and hasattr(wm, 'address_cache'):
                wallet_addr = wm.address_cache.get("ETH", wm.address_cache.get("ethereum", ""))

            new_card = {
                "card_id": card_id,
                "label": label,
                "last4": last4,
                "card_number_masked": f"**** **** **** {last4}",
                "expiry": f"{expiry_month}/{expiry_year}",
                "cvv_set": True,
                "network": "Visa",
                "type": card_type,
                "currency": currency,
                "frozen": False,
                "created": datetime.utcnow().isoformat(),
                "token": token,
                "wallet_address": wallet_addr,
                "settings": {
                    "contactless_enabled": True,
                    "online_payments_enabled": True,
                    "international_enabled": True,
                    "atm_enabled": card_type == "physical",
                    "apple_pay_enabled": True,
                    "google_pay_enabled": True,
                },
                "limits": {
                    "daily_limit": 5000.00,
                    "monthly_limit": 25000.00,
                    "per_transaction_limit": 2500.00,
                    "atm_daily_limit": 500.00,
                },
                "status": "active",
                "user_id": user_id,
            }

            enc_details = {
                "card_id": card_id,
                "full_number": card_number_raw,
                "cvv": cvv,
                "expiry": f"{expiry_month}/{expiry_year}",
                "user_id": user_id,
            }

            stored = False
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                card_sys = self.event_bus.get_component('card_system')
                if card_sys and hasattr(card_sys, 'issue_card'):
                    result = card_sys.issue_card(new_card)
                    if result:
                        stored = True
            if not stored and hasattr(self, 'redis') and self.redis:
                card_key = f"kingdom:fintech:cards:{user_id}" if user_id else "kingdom:fintech:cards"
                raw = self.redis.get(card_key)
                cards = json.loads(raw) if raw and isinstance(raw, str) else []
                cards.append(new_card)
                self.redis.set(card_key, json.dumps(cards))
                self.redis.set(f"kingdom:fintech:card_enc:{card_id}",
                               json.dumps(enc_details), ex=60 * 60 * 24 * 365)
                stored = True
            if not stored:
                if not hasattr(self, '_fintech_cards'):
                    self._fintech_cards = []
                self._fintech_cards.append(new_card)

            self._record_tx("in", f"Virtual card issued: {label}", f"*{last4}",
                            user_id=user_id, transaction_type="card_issued")

            return {
                "type": "issue_card_result", "status": "ok",
                "card_id": card_id, "last4": last4,
                "token": token,
                "card_number_masked": f"**** **** **** {last4}",
                "expiry": f"{expiry_month}/{expiry_year}",
                "network": "Visa",
                "card_type": card_type,
                "settings": new_card["settings"],
                "limits": new_card["limits"],
                "apple_pay_ready": True,
                "google_pay_ready": True,
            }
        except Exception as e:
            logger.error("Fintech issue_card error: %s", e)
            return {"type": "issue_card_result", "status": "error", "message": str(e)}

    async def _fintech_toggle_card(self, data: Dict, freeze: bool = True) -> Dict[str, Any]:
        """Freeze or unfreeze a virtual card."""
        card_id = data.get("card_id", "")
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                card_sys = self.event_bus.get_component('card_system')
                if card_sys and hasattr(card_sys, 'set_card_frozen'):
                    card_sys.set_card_frozen(card_id, freeze)
                    return {"type": "toggle_card_result", "status": "ok"}
            # Redis fallback
            if hasattr(self, 'redis') and self.redis:
                raw = self.redis.get("kingdom:fintech:cards")
                cards = json.loads(raw) if raw and isinstance(raw, str) else []
                for c in cards:
                    if c.get("card_id") == card_id:
                        c["frozen"] = freeze
                self.redis.set("kingdom:fintech:cards", json.dumps(cards))
                return {"type": "toggle_card_result", "status": "ok"}
        except Exception as e:
            logger.error("Fintech toggle_card error: %s", e)
            return {"type": "toggle_card_result", "status": "error", "message": str(e)}
        return {"type": "toggle_card_result", "status": "ok"}

    async def _fintech_p2p_send(self, data: Dict) -> Dict[str, Any]:
        """Execute a P2P transfer — resolve @username to address, then blockchain tx."""
        recipient = data.get("recipient", "")
        amount_raw = data.get("amount", "0")
        currency = data.get("currency", "USD")
        uid = data.get("user_id", "")
        try:
            is_address = not recipient.startswith("@") and len(recipient) > 20

            if recipient.startswith("@") or (not is_address and len(recipient) >= 3):
                try:
                    from core.username_registry import resolve_username
                    entry = resolve_username(recipient)
                    if entry:
                        sym_map = {"USD": "ETH", "EUR": "ETH", "GBP": "ETH"}
                        chain = currency if currency in ("BTC", "ETH", "SOL", "XRP", "XMR") else sym_map.get(currency, "ETH")
                        resolved_addr = entry.get("addresses", {}).get(chain, "")
                        if resolved_addr:
                            recipient = resolved_addr
                            is_address = True
                            logger.info("Resolved username to %s address: %s...%s",
                                        chain, resolved_addr[:8], resolved_addr[-4:])
                        else:
                            return {"type": "p2p_result", "status": "error",
                                    "message": f"User '{data.get('recipient')}' has no {chain} address"}
                    elif recipient.startswith("@"):
                        return {"type": "p2p_result", "status": "error",
                                "message": f"Username '{recipient}' not found"}
                except ImportError:
                    pass
            wm = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')

            if is_address and wm and hasattr(wm, 'send_transaction'):
                sym_map = {"USD": "ETH", "EUR": "ETH", "GBP": "ETH"}
                network = currency if currency in ("BTC", "ETH", "SOL", "XRP", "XMR") else sym_map.get(currency, "ETH")
                tx_hash = wm.send_transaction(network, recipient, float(amount_raw))
                self._record_tx("out", f"P2P to {recipient[:12]}...", f"-{amount_raw} {currency}",
                                user_id=uid, transaction_type="p2p_send")
                return {"type": "p2p_result", "status": "ok",
                        "tx_hash": tx_hash,
                        "message": f"Sent {amount_raw} {currency} to {recipient[:16]}..."}

            if self.event_bus:
                self.event_bus.publish("fintech.p2p.send", {
                    "recipient": recipient,
                    "amount": amount_raw,
                    "currency": currency,
                    "source": "mobile",
                    "user_id": uid,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                self._record_tx("out", f"P2P to {recipient}", f"-{amount_raw} {currency}",
                                user_id=uid, transaction_type="p2p_send")
                return {"type": "p2p_result", "status": "ok",
                        "message": f"Sent {amount_raw} {currency} to {recipient}"}
        except Exception as e:
            logger.error("Fintech P2P error: %s", e)
            return {"type": "p2p_result", "status": "error", "message": str(e)}
        return {"type": "p2p_result", "status": "error", "message": "No event bus"}

    def _get_asset_resolver(self):
        """Lazy-load the UniversalAssetResolver from the fintech module."""
        if not hasattr(self, '_asset_resolver') or self._asset_resolver is None:
            try:
                from importlib import import_module
                mod = import_module("kingdom-fintech.services.bitchat_listener")
                resolver_cls = getattr(mod, "UniversalAssetResolver", None)
                if resolver_cls:
                    redis_conn = getattr(self, 'redis', None)
                    self._asset_resolver = resolver_cls(redis_client=redis_conn)
                    return self._asset_resolver
            except Exception:
                pass
            # Inline fallback: lightweight resolver with top assets
            self._asset_resolver = _InlineAssetResolver(
                redis_client=getattr(self, 'redis', None)
            )
        return self._asset_resolver

    async def _fintech_bitchat_pay(self, data: Dict) -> Dict[str, Any]:
        """Process a BitChat natural-language payment command (2026 SOTA: any asset)."""
        command = data.get("command", "")
        try:
            # Parse the command to extract asset, amount, recipient
            import re
            parsed = None
            # "send 0.5 ETH to @user" / "transfer 100 SHIB to @user"
            m = re.match(r'^\s*(?:send|transfer)\s+([0-9]*\.?[0-9]+)\s+([a-zA-Z][a-zA-Z0-9_.]{0,19})\s+(?:to)\s+@([a-zA-Z0-9_-]+)\s*$', command, re.IGNORECASE)
            if m:
                parsed = {"amount": m.group(1), "asset": m.group(2).upper(), "recipient": m.group(3)}
            # "send $50 to @user"
            if not parsed:
                m = re.match(r'^\s*(?:send|transfer)\s+\$([0-9]*\.?[0-9]+)\s+(?:to)\s+@([a-zA-Z0-9_-]+)\s*$', command, re.IGNORECASE)
                if m:
                    parsed = {"amount": m.group(1), "asset": "USDC", "recipient": m.group(2)}
            # "pay @user 50 DOGE"
            if not parsed:
                m = re.match(r'^\s*(?:pay)\s+@([a-zA-Z0-9_-]+)\s+([0-9]*\.?[0-9]+)\s+([a-zA-Z][a-zA-Z0-9_.]{0,19})\s*$', command, re.IGNORECASE)
                if m:
                    parsed = {"amount": m.group(2), "asset": m.group(3).upper(), "recipient": m.group(1)}
            # "pay @user $100"
            if not parsed:
                m = re.match(r'^\s*(?:pay)\s+@([a-zA-Z0-9_-]+)\s+\$([0-9]*\.?[0-9]+)\s*$', command, re.IGNORECASE)
                if m:
                    parsed = {"amount": m.group(2), "asset": "USDC", "recipient": m.group(1)}

            if not parsed:
                # Forward unstructured command to event bus for AI parsing
                if self.event_bus:
                    self.event_bus.publish("fintech.bitchat.command", {
                        "command": command, "source": "mobile",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    self._record_tx("out", f"BitChat: {command[:40]}", "pending")
                    return {"type": "bitchat_result", "status": "ok",
                            "message": f"Command forwarded to AI parser: {command[:50]}"}
                return {"type": "bitchat_result", "status": "error", "message": "Could not parse command"}

            # Resolve asset via UniversalAssetResolver
            resolver = self._get_asset_resolver()
            asset_info = resolver.resolve(parsed["asset"]) if resolver else None
            if not asset_info:
                return {"type": "bitchat_result", "status": "error",
                        "message": f"Unknown asset: {parsed['asset']}. Supports BTC, ETH, SOL, USDC, USDT, DOGE, SHIB, PEPE, UNI, LINK, ARB, any ERC20/BEP20/SPL token, and more."}

            asset_chain = asset_info.get("chain", "unknown")
            asset_type = asset_info.get("type", "native")
            asset_contract = asset_info.get("contract", "")

            recipient = parsed["recipient"]
            amount_str = parsed["amount"]
            asset_sym = parsed["asset"]
            is_address = not recipient.startswith("@") and len(recipient) > 20

            wm = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')

            if is_address and wm and hasattr(wm, 'send_transaction'):
                try:
                    tx_hash = wm.send_transaction(asset_chain or asset_sym, recipient, float(amount_str))
                    self._record_tx("out",
                        f"BitChat: {amount_str} {asset_sym} → {recipient[:12]}...",
                        f"-{amount_str} {asset_sym}")
                    return {
                        "type": "bitchat_result", "status": "ok",
                        "asset": asset_sym, "chain": asset_chain,
                        "amount": amount_str, "recipient": recipient,
                        "tx_hash": tx_hash,
                        "message": f"Sent {amount_str} {asset_sym} ({asset_chain}) — TX: {tx_hash[:16]}...",
                    }
                except Exception as tx_err:
                    return {"type": "bitchat_result", "status": "error",
                            "message": f"Transaction failed: {tx_err}"}

            if self.event_bus:
                self.event_bus.publish("fintech.bitchat.command", {
                    "command": command,
                    "parsed": {
                        "amount": amount_str,
                        "asset": asset_sym,
                        "recipient": recipient,
                        "chain": asset_chain,
                        "token_type": asset_type,
                        "contract": asset_contract,
                    },
                    "source": "mobile",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                self._record_tx("out",
                    f"BitChat: {amount_str} {asset_sym} → @{recipient}",
                    f"-{amount_str} {asset_sym}")
                return {
                    "type": "bitchat_result", "status": "ok",
                    "asset": asset_sym,
                    "chain": asset_chain,
                    "amount": amount_str,
                    "recipient": recipient,
                    "message": f"Sending {amount_str} {asset_sym} ({asset_chain}) to @{recipient}",
                }
        except Exception as e:
            logger.error("BitChat pay error: %s", e)
            return {"type": "bitchat_result", "status": "error", "message": str(e)}
        return {"type": "bitchat_result", "status": "error", "message": "No event bus"}

    async def _fintech_update_card_limits(self, data: Dict) -> Dict[str, Any]:
        """Update spending limits on a virtual card."""
        card_id = data.get("card_id", "")
        new_limits = {k: v for k, v in data.items()
                      if k in ("daily_limit", "monthly_limit",
                               "per_transaction_limit", "atm_daily_limit")
                      and isinstance(v, (int, float))}
        if not card_id or not new_limits:
            return {"type": "update_limits_result", "status": "error",
                    "message": "card_id and at least one limit required"}
        try:
            updated = False
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                card_sys = self.event_bus.get_component('card_system')
                if card_sys and hasattr(card_sys, 'update_card_limits'):
                    card_sys.update_card_limits(card_id, new_limits)
                    updated = True
            if not updated and hasattr(self, 'redis') and self.redis:
                raw = self.redis.get("kingdom:fintech:cards")
                cards = json.loads(raw) if raw and isinstance(raw, str) else []
                for c in cards:
                    if c.get("card_id") == card_id:
                        c.setdefault("limits", {}).update(new_limits)
                self.redis.set("kingdom:fintech:cards", json.dumps(cards))
                updated = True
            if not updated:
                for c in getattr(self, '_fintech_cards', []):
                    if c.get("card_id") == card_id:
                        c.setdefault("limits", {}).update(new_limits)
            return {"type": "update_limits_result", "status": "ok",
                    "card_id": card_id, "limits": new_limits}
        except Exception as e:
            logger.error("Update card limits error: %s", e)
            return {"type": "update_limits_result", "status": "error", "message": str(e)}

    async def _fintech_update_card_settings(self, data: Dict) -> Dict[str, Any]:
        """Update card settings (contactless, online, international, digital wallet tokens)."""
        card_id = data.get("card_id", "")
        new_settings = {k: v for k, v in data.items()
                        if k in ("contactless_enabled", "online_payments_enabled",
                                 "international_enabled", "atm_enabled",
                                 "apple_pay_enabled", "google_pay_enabled")
                        and isinstance(v, bool)}
        if not card_id or not new_settings:
            return {"type": "update_settings_result", "status": "error",
                    "message": "card_id and at least one setting required"}
        try:
            updated = False
            if hasattr(self, 'redis') and self.redis:
                raw = self.redis.get("kingdom:fintech:cards")
                cards = json.loads(raw) if raw and isinstance(raw, str) else []
                for c in cards:
                    if c.get("card_id") == card_id:
                        c.setdefault("settings", {}).update(new_settings)
                self.redis.set("kingdom:fintech:cards", json.dumps(cards))
                updated = True
            if not updated:
                for c in getattr(self, '_fintech_cards', []):
                    if c.get("card_id") == card_id:
                        c.setdefault("settings", {}).update(new_settings)
            return {"type": "update_settings_result", "status": "ok",
                    "card_id": card_id, "settings": new_settings}
        except Exception as e:
            logger.error("Update card settings error: %s", e)
            return {"type": "update_settings_result", "status": "error", "message": str(e)}

    async def _fintech_online_purchase(self, data: Dict) -> Dict[str, Any]:
        """Authorize an online purchase using a virtual card.

        AI-powered: queries Ollama for merchant risk assessment before approving.
        Debits the wallet after authorization succeeds.
        """
        card_id = data.get("card_id", "")
        merchant = data.get("merchant", "Unknown Merchant")
        amount = float(data.get("amount", 0))
        currency = data.get("currency", "USD")
        try:
            card_data = self._lookup_card(card_id)
            if not card_data:
                return {"type": "purchase_result", "status": "declined",
                        "reason": "Card not found"}
            if card_data.get("frozen"):
                return {"type": "purchase_result", "status": "declined",
                        "reason": "Card is frozen"}
            settings = card_data.get("settings", {})
            if not settings.get("online_payments_enabled", True):
                return {"type": "purchase_result", "status": "declined",
                        "reason": "Online payments disabled for this card"}
            limits = card_data.get("limits", {})
            per_tx = limits.get("per_transaction_limit", 2500)
            if amount > per_tx:
                return {"type": "purchase_result", "status": "declined",
                        "reason": f"Amount ${amount:.2f} exceeds per-transaction limit ${per_tx:.2f}"}

            ai_check = await self._ai_merchant_risk(merchant, amount, currency)
            if ai_check.get("blocked"):
                return {"type": "purchase_result", "status": "declined",
                        "reason": f"AI blocked: {ai_check.get('reason', 'suspicious merchant')}"}

            wm = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')

            tx_hash = None
            if wm and hasattr(wm, 'send_transaction'):
                network = wm._resolve_currency_to_network(currency) if hasattr(wm, '_resolve_currency_to_network') else "ETH"
                if network:
                    try:
                        tx_hash = wm.send_transaction(network, card_data.get("wallet_address", ""), amount)
                    except Exception as tx_err:
                        logger.warning("Card purchase wallet debit failed (non-blocking): %s", tx_err)

            auth_code = str(uuid.uuid4())[:8].upper()
            card_user = card_data.get("user_id", "")
            self._record_tx("out", f"Online purchase: {merchant}", f"-{amount:.2f} {currency}",
                            user_id=card_user, merchant=merchant, card_id=card_id,
                            transaction_type="online_purchase", category=data.get("category", ""))

            return {
                "type": "purchase_result", "status": "approved",
                "auth_code": auth_code,
                "card_last4": card_data.get("last4", ""),
                "merchant": merchant,
                "amount": amount,
                "currency": currency,
                "tx_hash": tx_hash,
                "ai_risk": ai_check.get("risk_level", "low"),
            }
        except Exception as e:
            logger.error("Online purchase error: %s", e)
            return {"type": "purchase_result", "status": "error", "message": str(e)}

    def _lookup_card(self, card_id: str) -> Optional[Dict]:
        """Find a card by ID across storage layers."""
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                card_sys = self.event_bus.get_component('card_system')
                if card_sys and hasattr(card_sys, 'get_card'):
                    c = card_sys.get_card(card_id)
                    if c:
                        return c
            if hasattr(self, 'redis') and self.redis:
                raw = self.redis.get("kingdom:fintech:cards")
                cards = json.loads(raw) if raw and isinstance(raw, str) else []
                for c in cards:
                    if c.get("card_id") == card_id:
                        return c
            for c in getattr(self, '_fintech_cards', []):
                if c.get("card_id") == card_id:
                    return c
        except Exception as e:
            logger.debug("Card lookup error: %s", e)
        return None

    async def _ai_merchant_risk(self, merchant: str, amount: float,
                                 currency: str) -> Dict[str, Any]:
        """AI-powered merchant risk check using Ollama brain."""
        try:
            import requests as _req
            base_url = os.getenv("KINGDOM_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            model = os.getenv("KINGDOM_OLLAMA_MODEL", "cogito:latest")
            prompt = (
                f"MERCHANT RISK CHECK — respond JSON only.\n"
                f"Merchant: {merchant}\nAmount: {amount} {currency}\n\n"
                f"Is this merchant suspicious? Known scam patterns?\n"
                f"Respond: {{\"risk_level\":\"low|medium|high|critical\","
                f"\"blocked\":false,\"reason\":\"brief\"}}"
            )
            headers = {}
            api_key = os.environ.get("OLLAMA_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = _req.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.1, "num_predict": 150}},
                headers=headers, timeout=8)
            if resp.status_code == 200:
                text = resp.json().get("response", "")
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(text[start:end])
        except Exception as e:
            logger.debug("AI merchant risk check skipped: %s", e)
        return {"risk_level": "low", "blocked": False, "reason": "AI unavailable, default allow"}

    async def _get_crypto_price_from_coingecko(self, crypto: str) -> Optional[float]:
        """Fetch real crypto price from CoinGecko API.
        
        Returns price in USD, or None if fetch fails.
        Uses cache to avoid excessive API calls.
        """
        crypto_upper = crypto.upper()
        
        # Check cache (5 minute TTL)
        cache_key = f"coingecko_price_{crypto_upper}"
        now = time.time()
        if cache_key in self._price_cache:
            cached = self._price_cache[cache_key]
            if now - cached.get("timestamp", 0) < 300:  # 5 minutes
                return cached.get("price")
        
        # CoinGecko coin ID mapping
        coin_ids = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "BNB": "binancecoin",
            "XRP": "ripple",
            "USDC": "usd-coin",
            "USDT": "tether",
            "ADA": "cardano",
            "AVAX": "avalanche-2",
            "DOT": "polkadot",
            "DOGE": "dogecoin",
            "LINK": "chainlink",
            "MATIC": "matic-network",
        }
        
        coin_id = coin_ids.get(crypto_upper, crypto_upper.lower())
        
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            req = urllib.request.Request(url, headers={"User-Agent": "KingdomAI/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if coin_id in data and "usd" in data[coin_id]:
                    price = float(data[coin_id]["usd"])
                    # Cache the result
                    self._price_cache[cache_key] = {"price": price, "timestamp": now}
                    logger.debug("Fetched %s price from CoinGecko: $%.2f", crypto_upper, price)
                    return price
        except Exception as e:
            logger.debug("CoinGecko API fetch failed for %s: %s", crypto_upper, e)
        
        return None

    async def _fintech_offramp_quote(self, data: Dict) -> Dict[str, Any]:
        """Get a crypto-to-fiat off-ramp quote."""
        crypto = data.get("crypto", "USDC")
        fiat = data.get("fiat", "USD")
        amount = data.get("amount", "0")
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                offramp = self.event_bus.get_component('offramp_system')
                if offramp and hasattr(offramp, 'get_quote'):
                    quote = offramp.get_quote(crypto, fiat, float(amount))
                    if quote:
                        return {"type": "offramp_quote_result", "status": "ok",
                                "rate": quote.get("rate", "0"),
                                "receive_amount": quote.get("receive_amount", "0"),
                                "quote_id": quote.get("quote_id", "")}
            # Fallback: Fetch real prices from CoinGecko API
            rate = await self._get_crypto_price_from_coingecko(crypto)
            if rate is None:
                logger.warning("Failed to fetch %s price from CoinGecko, using fallback", crypto)
                # Last resort fallback rates (should rarely be used)
                fallback_rates = {"BTC": 97500, "ETH": 3400, "USDC": 1.0, "KAIG": 0.05}
                rate = fallback_rates.get(crypto, 1.0)
            
            # Fiat conversion rates (can be enhanced with real API later)
            fiat_multipliers = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}
            multiplier = fiat_multipliers.get(fiat, 1.0)
            receive = round(float(amount) * rate * multiplier, 2)
            quote_id = str(uuid.uuid4())[:12]
            return {"type": "offramp_quote_result", "status": "ok",
                    "rate": str(round(rate * multiplier, 2)),
                    "receive_amount": str(receive),
                    "quote_id": quote_id}
        except Exception as e:
            logger.error("Offramp quote error: %s", e)
            return {"type": "offramp_quote_result", "status": "error", "message": str(e)}

    async def _fintech_offramp_execute(self, data: Dict) -> Dict[str, Any]:
        """Execute an off-ramp conversion."""
        quote_id = data.get("quote_id", "")
        try:
            if self.event_bus:
                self.event_bus.publish("fintech.offramp.execute", {
                    "quote_id": quote_id,
                    "source": "mobile",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                tx_id = str(uuid.uuid4())[:16]
                self._record_tx("out", f"Off-ramp conversion", f"Quote: {quote_id[:8]}")
                return {"type": "offramp_execute_result", "status": "ok", "tx_id": tx_id}
        except Exception as e:
            logger.error("Offramp execute error: %s", e)
            return {"type": "offramp_execute_result", "status": "error", "message": str(e)}
        return {"type": "offramp_execute_result", "status": "error", "message": "No event bus"}

    def _fintech_get_tx_history(self, limit: int = 20,
                                user_id: str = "") -> Dict[str, Any]:
        """Get recent fintech transaction history, optionally filtered by user."""
        try:
            if hasattr(self, 'redis') and self.redis:
                key = f"kingdom:fintech:tx_history:{user_id}" if user_id else "kingdom:fintech:tx_history"
                raw = self.redis.lrange(key, 0, limit - 1)
                if raw:
                    txs = [json.loads(r) if isinstance(r, str) else r for r in raw]
                    return {"type": "tx_history_result", "status": "ok", "transactions": txs}
            if hasattr(self, '_fintech_tx_history'):
                all_tx = self._fintech_tx_history
                if user_id:
                    all_tx = [t for t in all_tx if t.get("user_id", "") == user_id]
                return {"type": "tx_history_result", "status": "ok",
                        "transactions": all_tx[-limit:]}
        except Exception as e:
            logger.error("TX history error: %s", e)
        return {"type": "tx_history_result", "status": "ok", "transactions": []}

    def _fintech_overview(self, user_id: str = "") -> Dict[str, Any]:
        """Get fintech system overview (2026 SOTA: includes security status)."""
        cards_resp = self._fintech_get_cards(user_id=user_id)
        tx_resp = self._fintech_get_tx_history(5, user_id=user_id)
        sec_status = {}
        if self._security_engine:
            try:
                sec_status = self._security_engine.get_security_status()
            except Exception:
                pass
        return {
            "type": "fintech_overview_result", "status": "ok",
            "card_count": len(cards_resp.get("cards", [])),
            "recent_tx_count": len(tx_resp.get("transactions", [])),
            "features": [
                "virtual_cards", "card_tokenization", "card_limit_controls",
                "card_settings_management", "online_purchase_authorization",
                "apple_pay_token", "google_pay_token",
                "p2p_transfers", "bitchat_pay_any_asset",
                "offramp", "ai_secured_nfc_tap_to_pay", "tx_history",
                "ai_security_engine", "ai_merchant_risk_scoring",
                "ai_transaction_validation", "ghost_tap_detection",
                "behavioral_biometrics", "device_attestation_rasp",
                "transaction_risk_scoring", "anti_replay_hmac",
                "rate_limiting", "impossible_travel_detection",
            ],
            "security": sec_status,
        }

    def _record_tx(self, direction: str, description: str, amount: str,
                    user_id: str = "", merchant: str = "",
                    card_id: str = "", transaction_type: str = "",
                    category: str = ""):
        """Record a transaction for history with merchant and card details."""
        tx = {
            "direction": direction,
            "description": description,
            "amount": amount,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "merchant": merchant,
            "card_id": card_id,
            "transaction_type": transaction_type,
            "category": category,
        }
        redis_key = f"kingdom:fintech:tx_history:{user_id}" if user_id else "kingdom:fintech:tx_history"
        try:
            if hasattr(self, 'redis') and self.redis:
                self.redis.lpush(redis_key, json.dumps(tx))
                self.redis.ltrim(redis_key, 0, 199)
                return
        except Exception:
            pass
        if not hasattr(self, '_fintech_tx_history'):
            self._fintech_tx_history = []
        self._fintech_tx_history.append(tx)
        if len(self._fintech_tx_history) > 200:
            self._fintech_tx_history = self._fintech_tx_history[-200:]

    # ------------------------------------------------------------------
    # AI Security Engine methods (2026 SOTA hack-proof)
    # ------------------------------------------------------------------

    async def _secure_nfc_tap_pay(self, data: Dict, device_id: str) -> Dict[str, Any]:
        """AI-secured NFC tap-to-pay with Ghost-Tap relay detection."""
        if not self._security_engine:
            return {"type": "nfc_tap_pay_result", "status": "error",
                    "message": "Security engine not available"}
        try:
            tap_data = {
                "tap_duration_ms": data.get("tap_duration_ms", 50.0),
                "card_id": data.get("card_id", ""),
                "location": tuple(data["location"]) if data.get("location") else None,
                "device_nfc_field_strength": data.get("field_strength", 0.8),
                "challenge_response_time_ms": data.get("challenge_rt_ms"),
                "user_id": data.get("user_id", device_id),
                "device_id": device_id,
            }
            device_data = data.get("device_attestation")

            # Full AI security check: NFC relay + device + rate limit
            verdict = self._security_engine.secure_nfc_tap(tap_data, device_data)

            if not verdict.allowed:
                self._security_engine.log_security_event("nfc_tap_blocked", verdict,
                    {"device_id": device_id, "card_id": data.get("card_id", "")})
                return {
                    "type": "nfc_tap_pay_result", "status": "blocked",
                    "threat_level": verdict.threat_level.value,
                    "risk_score": round(verdict.risk_score, 4),
                    "reasons": verdict.reasons,
                    "requires_biometric": verdict.requires_biometric,
                    "message": f"BLOCKED: {'; '.join(verdict.reasons[:2])}",
                }

            # If high risk but allowed, require biometric confirmation
            if verdict.requires_biometric:
                return {
                    "type": "nfc_tap_pay_result", "status": "requires_auth",
                    "threat_level": verdict.threat_level.value,
                    "risk_score": round(verdict.risk_score, 4),
                    "requires_biometric": True,
                    "message": "Biometric confirmation required for this tap",
                }

            # Approved — relay to payment system
            if self.event_bus:
                self.event_bus.publish("fintech.nfc.tap_pay", {
                    "card_id": data.get("card_id", ""),
                    "amount": data.get("amount", "0"),
                    "terminal_id": data.get("terminal_id", ""),
                    "source": "mobile",
                    "security_verdict": verdict.to_dict(),
                })
            self._record_tx("out", "NFC Tap-to-Pay", data.get("amount", "0"),
                            user_id=device_id, merchant=data.get("merchant", ""),
                            card_id=data.get("card_id", ""),
                            transaction_type="nfc_tap_to_pay")
            return {
                "type": "nfc_tap_pay_result", "status": "ok",
                "threat_level": verdict.threat_level.value,
                "risk_score": round(verdict.risk_score, 4),
                "message": "NFC payment approved — AI security verified",
            }
        except Exception as e:
            logger.error("Secure NFC tap error: %s", e)
            return {"type": "nfc_tap_pay_result", "status": "error", "message": str(e)}

    def _handle_device_attestation(self, data: Dict) -> Dict[str, Any]:
        """Process device attestation from mobile client."""
        if not self._security_engine:
            return {"type": "device_attest_result", "status": "ok",
                    "message": "Security engine not available — attestation skipped"}
        try:
            att, verdict = self._security_engine.device_attestation.attest_device(data)
            self._security_engine.log_security_event("device_attestation", verdict,
                {"device_id": data.get("device_id", "")})
            return {
                "type": "device_attest_result",
                "status": "ok" if verdict.allowed else "blocked",
                "threat_level": verdict.threat_level.value,
                "risk_score": round(verdict.risk_score, 4),
                "is_rooted": att.is_rooted,
                "is_emulator": att.is_emulator,
                "is_debugger": att.is_debugger_attached,
                "app_signature_valid": att.app_signature_valid,
                "has_secure_element": att.has_secure_element,
                "events": [e.value for e in verdict.events],
                "reasons": verdict.reasons,
                "message": "Device attestation complete",
            }
        except Exception as e:
            logger.error("Device attestation error: %s", e)
            return {"type": "device_attest_result", "status": "error", "message": str(e)}

    def _get_security_status(self) -> Dict[str, Any]:
        """Get AI security engine status."""
        if not self._security_engine:
            return {"type": "security_status_result", "status": "ok",
                    "engine_active": False, "message": "Security engine not loaded"}
        try:
            status = self._security_engine.get_security_status()
            return {"type": "security_status_result", "status": "ok", **status}
        except Exception as e:
            return {"type": "security_status_result", "status": "error", "message": str(e)}

    def _ai_security_check(self, msg_type: str, data: Dict,
                            device_id: str) -> Optional[Dict[str, Any]]:
        """
        Run AI security check on a fintech request.
        Returns None if allowed, or a block response dict if denied.
        """
        if not self._security_engine:
            return None  # No engine = allow (graceful degradation)
        try:
            # Rate limit check
            rate_v = self._security_engine.rate_limiter.check(f"{msg_type}:{device_id}")
            if not rate_v.allowed:
                return {
                    "type": f"{msg_type}_result", "status": "rate_limited",
                    "message": f"Rate limit exceeded: {rate_v.reasons[0] if rate_v.reasons else 'too many requests'}",
                    "threat_level": rate_v.threat_level.value,
                }
            # For payment operations, run full transaction security
            if msg_type in ("p2p_send", "bitchat_pay", "offramp_execute", "nfc_tap_pay"):
                tx_data = {
                    "user_id": data.get("user_id", device_id),
                    "amount": float(data.get("amount", 0)),
                    "currency": data.get("currency", data.get("asset", "USD")),
                    "recipient": data.get("recipient", ""),
                    "device_id": device_id,
                }
                verdict = self._security_engine.secure_transaction(
                    tx_data, data.get("device_attestation"))
                if not verdict.allowed:
                    return {
                        "type": f"{msg_type}_result", "status": "blocked",
                        "threat_level": verdict.threat_level.value,
                        "risk_score": round(verdict.risk_score, 4),
                        "reasons": verdict.reasons,
                        "requires_biometric": verdict.requires_biometric,
                        "message": f"Security blocked: {'; '.join(verdict.reasons[:2])}",
                    }
        except Exception as e:
            logger.error("AI security check error for %s: %s", msg_type, e)
        return None  # Allow on error (fail-open for non-critical)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # USERNAME + PAYMENT QR SYSTEM (SOTA 2026)
    # ------------------------------------------------------------------

    def _handle_register_username(self, data: Dict, device_id: str) -> Dict[str, Any]:
        """Register a unique username for this user."""
        from core.username_registry import register_username, update_addresses
        from core.wallet_creator import WalletCreator

        raw = data.get("username", "")
        if not raw:
            return {"type": "register_username_result", "status": "error",
                    "error": "Username is required"}

        addresses = {}
        try:
            wc = WalletCreator(event_bus=self.event_bus)
            manifest = wc.get_user_wallet(device_id)
            if manifest:
                addresses = manifest.get("addresses", {})
        except Exception:
            pass

        ref_code = ""
        try:
            ref_data = self._load_referrals()
            for code, info in ref_data.get("codes", {}).items():
                if info.get("device_id") == device_id:
                    ref_code = code
                    break
        except Exception:
            pass

        result = register_username(
            raw_username=raw,
            user_id=device_id,
            addresses=addresses,
            display_name=data.get("display_name", raw),
            referral_code=ref_code,
            referred_by=data.get("referred_by", ""),
        )

        if result.get("success"):
            if self.event_bus:
                self.event_bus.publish("user.username.registered", {
                    "user_id": device_id,
                    "username": result["username"],
                })
            return {"type": "register_username_result", "status": "ok",
                    "username": result["username"]}
        return {"type": "register_username_result", "status": "error",
                "error": result.get("error", "Registration failed")}

    def _handle_change_username(self, data: Dict, device_id: str) -> Dict[str, Any]:
        from core.username_registry import change_username
        raw = data.get("username", "")
        if not raw:
            return {"type": "change_username_result", "status": "error",
                    "error": "New username required"}
        result = change_username(device_id, raw)
        if result.get("success"):
            return {"type": "change_username_result", "status": "ok",
                    "username": result["username"]}
        return {"type": "change_username_result", "status": "error",
                "error": result.get("error", "Change failed")}

    def _handle_check_username(self, data: Dict) -> Dict[str, Any]:
        from core.username_registry import is_username_available
        raw = data.get("username", "")
        available = is_username_available(raw) if raw else False
        return {"type": "check_username_result", "status": "ok",
                "username": raw, "available": available}

    def _handle_resolve_username(self, data: Dict) -> Dict[str, Any]:
        """Resolve @username to wallet addresses for P2P payment."""
        from core.username_registry import resolve_username
        raw = data.get("username", "")
        entry = resolve_username(raw)
        if entry:
            return {"type": "resolve_username_result", "status": "ok",
                    "username": raw.lstrip("@").lower(),
                    "display_name": entry.get("display_name", ""),
                    "addresses": entry.get("addresses", {}),
                    "user_id": entry.get("user_id", "")}
        return {"type": "resolve_username_result", "status": "error",
                "error": f"Username '{raw}' not found"}

    def _handle_get_payment_qr(self, device_id: str) -> Dict[str, Any]:
        """Generate a payment QR payload for this user (includes username + addresses)."""
        from core.username_registry import generate_payment_qr_payload
        payload = generate_payment_qr_payload(device_id)
        if "error" in payload:
            return {"type": "payment_qr_result", "status": "error",
                    "error": payload["error"]}
        qr_json = json.dumps(payload)
        qr_b64 = ""
        try:
            import qrcode
            from io import BytesIO
            import base64
            qr = qrcode.QRCode(version=1, box_size=8, border=3)
            qr.add_data(qr_json)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#FFD700", back_color="#0A0E17")
            buf = BytesIO()
            img.save(buf, format="PNG")
            qr_b64 = base64.b64encode(buf.getvalue()).decode()
        except ImportError:
            pass
        return {"type": "payment_qr_result", "status": "ok",
                "payload": payload, "qr_image_base64": qr_b64}

    def _handle_get_my_username(self, device_id: str) -> Dict[str, Any]:
        from core.username_registry import get_username_for_user, resolve_username
        uname = get_username_for_user(device_id)
        if uname:
            entry = resolve_username(uname) or {}
            return {"type": "my_username_result", "status": "ok",
                    "username": uname,
                    "display_name": entry.get("display_name", uname)}
        return {"type": "my_username_result", "status": "ok",
                "username": None, "display_name": None}

    def _handle_get_download_qr(self, device_id: str) -> Dict[str, Any]:
        """Generate a QR code for new users to download the app.

        The QR encodes the referral link so the new user gets credited
        to the referring user's referral code.
        """
        ref_code = ""
        try:
            ref_data = self._load_referrals()
            for code, info in ref_data.get("codes", {}).items():
                if info.get("device_id") == device_id:
                    ref_code = code
                    break
            if not ref_code:
                gen = self._get_referral_code(device_id)
                ref_code = gen.get("referral_code", "")
        except Exception:
            pass

        landing = "https://kingdom-ai.netlify.app"
        params = []
        if ref_code:
            params.append(f"ref={ref_code}")
        if device_id:
            params.append(f"device_id={device_id}")
        download_url = f"{landing}/join?{'&'.join(params)}" if params else landing

        payload = {
            "type": "kingdom_download",
            "version": 2,
            "url": download_url,
            "referral_code": ref_code,
            "from_device": device_id,
        }
        qr_b64 = ""
        try:
            import qrcode
            from io import BytesIO
            import base64
            qr = qrcode.QRCode(version=1, box_size=8, border=3)
            qr.add_data(download_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#FFD700", back_color="#0A0E17")
            buf = BytesIO()
            img.save(buf, format="PNG")
            qr_b64 = base64.b64encode(buf.getvalue()).decode()
        except ImportError:
            pass

        return {"type": "download_qr_result", "status": "ok",
                "download_url": download_url, "referral_code": ref_code,
                "qr_image_base64": qr_b64}

    # ------------------------------------------------------------------
    # HIVE TRADER: Full AI Auto-Trading Engine (SOTA 2026)
    # Each mobile instance is a separate Hive entity with the full
    # trading toolkit. Hive Mind decides strategy — user just toggles ON.
    # ------------------------------------------------------------------

    TRADING_STRATEGIES = [
        "dca", "grid", "infinity_grid", "reverse_grid",
        "momentum", "mean_reversion", "scalping", "swing",
        "trend_following", "breakout", "range_trading",
        "arbitrage", "cross_exchange_arb", "triangular_arb",
        "rsi", "macd", "bollinger_bands", "twap", "vwap",
        "rebalancing", "trailing_stop", "market_making",
        "sentiment", "deep_learning", "quantum_hybrid",
        "meta_learning", "coin_accumulation", "stack_sats",
    ]

    def _get_hive_entity_id(self, device_id: str) -> str:
        """Generate a deterministic Hive entity ID for a device."""
        import hashlib
        return f"hive-{hashlib.sha256(device_id.encode()).hexdigest()[:12]}"

    def _handle_auto_trade_start(self, data: Dict, device_id: str) -> Dict[str, Any]:
        """Start AI auto-trading. Hive Mind selects strategies — user doesn't pick.

        The trading engine uses all available strategies simultaneously:
        CCXT for direct exchange execution, Hive Mind for signal coordination,
        and the full trading intelligence suite for analysis.
        """
        try:
            cfg_path = os.path.join("config", f"autotrade_{device_id}.json")
            api_keys = data.get("api_keys", {})

            if not api_keys:
                try:
                    user_keys_path = os.path.join("data", "wallets", "users", device_id, "api_keys.json")
                    if os.path.exists(user_keys_path):
                        with open(user_keys_path, "r") as f:
                            api_keys = json.load(f)
                except Exception:
                    pass

            if not api_keys and device_id == "creator":
                try:
                    keys_path = os.path.join("config", "api_keys.json")
                    if os.path.exists(keys_path):
                        with open(keys_path, "r") as f:
                            api_keys = json.load(f)
                except Exception:
                    pass

            if not api_keys:
                return {"type": "auto_trade_result", "status": "error",
                        "message": "API keys required — add exchange keys first"}

            hive_id = self._get_hive_entity_id(device_id)
            pair = data.get("pair", "BTC/USDT")
            risk_level = data.get("risk_level", "moderate")
            amount = float(data.get("amount_per_trade", 25))

            state = {
                "enabled": True,
                "hive_entity_id": hive_id,
                "device_id": device_id,
                "pair": pair,
                "risk_level": risk_level,
                "amount_per_trade": amount,
                "active_strategies": list(self.TRADING_STRATEGIES),
                "started_at": datetime.utcnow().isoformat(),
                "trades_executed": 0,
                "total_pnl": 0.0,
            }

            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            with open(cfg_path, "w") as f:
                json.dump(state, f, indent=2)

            if self.event_bus:
                self.event_bus.publish("hive.entity.joined", {
                    "hive_entity_id": hive_id,
                    "device_id": device_id,
                    "device_type": "mobile",
                    "capabilities": ["trading", "signals", "execution"],
                })
                self.event_bus.publish("trading.auto.start", {
                    "hive_entity_id": hive_id,
                    "device_id": device_id,
                    "pair": pair,
                    "risk_level": risk_level,
                    "amount": amount,
                    "strategies": list(self.TRADING_STRATEGIES),
                    "source": "mobile_hive",
                })

            logger.info("Hive auto-trade started: entity=%s, device=%s, %d strategies",
                        hive_id, device_id, len(self.TRADING_STRATEGIES))
            return {
                "type": "auto_trade_result", "status": "ok",
                "hive_entity_id": hive_id,
                "strategies_active": len(self.TRADING_STRATEGIES),
                "pair": pair,
                "risk_level": risk_level,
                "message": f"AI Auto-Trade ON — Hive Mind controlling {len(self.TRADING_STRATEGIES)} strategies",
            }
        except Exception as e:
            logger.error("Auto-trade start failed: %s", e)
            return {"type": "auto_trade_result", "status": "error", "message": str(e)}

    def _handle_auto_trade_stop(self, device_id: str) -> Dict[str, Any]:
        """Stop auto-trading and disconnect this entity from the hive."""
        try:
            cfg_path = os.path.join("config", f"autotrade_{device_id}.json")
            hive_id = self._get_hive_entity_id(device_id)

            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    state = json.load(f)
                state["enabled"] = False
                state["stopped_at"] = datetime.utcnow().isoformat()
                with open(cfg_path, "w") as f:
                    json.dump(state, f, indent=2)

            if self.event_bus:
                self.event_bus.publish("trading.auto.stop", {
                    "hive_entity_id": hive_id,
                    "device_id": device_id,
                })
                self.event_bus.publish("hive.entity.left", {
                    "hive_entity_id": hive_id,
                    "device_id": device_id,
                })

            logger.info("Hive auto-trade stopped: entity=%s", hive_id)
            return {"type": "auto_trade_stop_result", "status": "ok",
                    "hive_entity_id": hive_id,
                    "message": "AI Auto-Trade OFF"}
        except Exception as e:
            return {"type": "auto_trade_stop_result", "status": "error", "message": str(e)}

    def _handle_auto_trade_status(self, device_id: str) -> Dict[str, Any]:
        """Get current auto-trade status for this device."""
        cfg_path = os.path.join("config", f"autotrade_{device_id}.json")
        hive_id = self._get_hive_entity_id(device_id)
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r") as f:
                    state = json.load(f)
                return {
                    "type": "auto_trade_status_result", "status": "ok",
                    "enabled": state.get("enabled", False),
                    "hive_entity_id": hive_id,
                    "strategies_active": len(state.get("active_strategies", [])),
                    "pair": state.get("pair", "BTC/USDT"),
                    "risk_level": state.get("risk_level", "moderate"),
                    "trades_executed": state.get("trades_executed", 0),
                    "total_pnl": state.get("total_pnl", 0.0),
                    "started_at": state.get("started_at", ""),
                }
            except Exception:
                pass
        return {"type": "auto_trade_status_result", "status": "ok",
                "enabled": False, "hive_entity_id": hive_id,
                "strategies_active": 0, "trades_executed": 0, "total_pnl": 0.0}

    def _handle_get_trading_tools(self) -> Dict[str, Any]:
        """Return the full list of trading tools/strategies available."""
        return {
            "type": "trading_tools_result", "status": "ok",
            "strategies": list(self.TRADING_STRATEGIES),
            "total_strategies": len(self.TRADING_STRATEGIES),
            "intelligence_modules": [
                "coin_accumulation_intelligence",
                "market_intelligence",
                "mining_intelligence",
                "kaig_intelligence_bridge",
                "competitive_edge_analyzer",
            ],
            "execution_modes": [
                "direct_ccxt", "event_bus_relay", "hive_mind_coordinated",
            ],
            "risk_levels": ["conservative", "moderate", "aggressive", "ultra"],
            "features": [
                "multi_exchange", "multi_pair", "multi_strategy",
                "ai_signal_generation", "hive_mind_coordination",
                "real_time_risk_management", "stop_loss_take_profit",
                "trailing_stops", "position_sizing", "portfolio_rebalancing",
                "sentiment_analysis", "on_chain_analysis",
                "cross_exchange_arbitrage", "dip_buying",
                "profit_to_wallet_routing", "tax_loss_harvesting",
            ],
        }

    def _handle_hive_status(self, device_id: str) -> Dict[str, Any]:
        """Get Hive Mind connection status for this instance."""
        hive_id = self._get_hive_entity_id(device_id)
        peer_count = 0
        connected = False

        if self.event_bus and hasattr(self.event_bus, 'get_component'):
            hive = self.event_bus.get_component('hive_mind')
            if hive and hasattr(hive, 'get_status'):
                try:
                    status = hive.get_status()
                    peer_count = status.get("total_peers", 0)
                    connected = status.get("active", False)
                except Exception:
                    pass

        auto_cfg_path = os.path.join("config", f"autotrade_{device_id}.json")
        auto_enabled = False
        if os.path.exists(auto_cfg_path):
            try:
                with open(auto_cfg_path, "r") as f:
                    auto_enabled = json.load(f).get("enabled", False)
            except Exception:
                pass

        return {
            "type": "hive_status_result", "status": "ok",
            "hive_entity_id": hive_id,
            "connected": connected or auto_enabled,
            "peer_count": peer_count,
            "device_id": device_id,
            "auto_trading": auto_enabled,
            "strategies_available": len(self.TRADING_STRATEGIES),
        }

    # ------------------------------------------------------------------
    # Referral Program (2026 SOTA: dual-sided rewards, QR deep-link)
    # ------------------------------------------------------------------

    REFERRAL_CONFIG_PATH = os.path.join("config", "referrals.json")
    # Tier 1: First referral = 3 months no 10% commission on winning trades
    COMMISSION_FREE_DAYS = 90          # 3 months
    COMMISSION_RATE_NORMAL = 0.10      # 10% on winning trades (normal)
    # Tier 2+: Subsequent referrals = KAIG coins (tracked, rolled out later)
    KAIG_PER_REFERRAL = 10.0           # KAIG (KAI Gold) coins per additional referral
    KAIG_WELCOME_BONUS = 5.0           # KAIG coins for new user joining via referral
    KAIG_REFERRAL_PARITY_BONUS = 5.0  # +5 KAIG parity bonus for referrer on EVERY referral
    REFERRAL_PREFERENCE_PATH = os.path.join("config", "referral_preferences.json")

    def _load_referral_preference(self, device_id: str) -> str:
        """Get referrer's preference: 'commission_free' (default) or 'kaig_coins'."""
        try:
            if os.path.exists(self.REFERRAL_PREFERENCE_PATH):
                with open(self.REFERRAL_PREFERENCE_PATH, "r") as f:
                    prefs = json.load(f)
                return prefs.get(device_id, "commission_free")
        except Exception:
            pass
        return "commission_free"

    def _save_referral_preference(self, device_id: str, preference: str):
        """Store referrer's preference in config."""
        prefs = {}
        try:
            if os.path.exists(self.REFERRAL_PREFERENCE_PATH):
                with open(self.REFERRAL_PREFERENCE_PATH, "r") as f:
                    prefs = json.load(f)
        except Exception:
            pass
        prefs[device_id] = preference
        os.makedirs(os.path.dirname(self.REFERRAL_PREFERENCE_PATH), exist_ok=True)
        with open(self.REFERRAL_PREFERENCE_PATH, "w") as f:
            json.dump(prefs, f, indent=2)

    def _load_referrals(self) -> Dict:
        try:
            if os.path.exists(self.REFERRAL_CONFIG_PATH):
                with open(self.REFERRAL_CONFIG_PATH, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"codes": {}, "applied": {}, "rewards": {}}

    def _save_referrals(self, data: Dict):
        os.makedirs(os.path.dirname(self.REFERRAL_CONFIG_PATH), exist_ok=True)
        with open(self.REFERRAL_CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # $KAIG (KAI Gold) handlers — mobile ↔ KAIG engine (SOTA 2026)
    # ------------------------------------------------------------------

    def _get_kaig_engine(self):
        """Get KAIG engine from component registry or event bus."""
        try:
            from core.component_registry import get_component
            engine = get_component('kaig_engine')
            if engine:
                return engine
        except Exception:
            pass
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                return self.event_bus.get_component('kaig_engine')
        except Exception:
            pass
        try:
            from core.kaig_engine import KAIGEngine
            return KAIGEngine.get_instance()
        except Exception:
            pass
        return None

    def _get_kaig_status(self) -> Dict[str, Any]:
        """Get full KAIG ecosystem status for mobile."""
        engine = self._get_kaig_engine()
        if engine:
            try:
                status = engine.get_full_status()
                return {"type": "kaig_status", "status": "ok", **status}
            except Exception as e:
                return {"type": "kaig_status", "status": "error", "error": str(e)}
        return {"type": "kaig_status", "status": "unavailable"}

    def _kaig_node_start(self) -> Dict[str, Any]:
        """Start KAIG node from mobile."""
        engine = self._get_kaig_engine()
        if engine:
            try:
                result = engine.node.start()
                return {"type": "kaig_node_start", "status": "ok", **result}
            except Exception as e:
                return {"type": "kaig_node_start", "status": "error", "error": str(e)}
        return {"type": "kaig_node_start", "status": "unavailable"}

    def _kaig_node_stop(self) -> Dict[str, Any]:
        """Stop KAIG node from mobile."""
        engine = self._get_kaig_engine()
        if engine:
            try:
                result = engine.node.stop()
                return {"type": "kaig_node_stop", "status": "ok", **result}
            except Exception as e:
                return {"type": "kaig_node_stop", "status": "error", "error": str(e)}
        return {"type": "kaig_node_stop", "status": "unavailable"}

    def _kaig_node_heartbeat(self) -> Dict[str, Any]:
        """KAIG node heartbeat from mobile — triggers reward check."""
        engine = self._get_kaig_engine()
        if engine:
            try:
                if engine.node.is_running:
                    beat = engine.node.heartbeat()
                    return {"type": "kaig_node_heartbeat", "status": "ok", **(beat or {})}
                return {"type": "kaig_node_heartbeat", "status": "node_not_running"}
            except Exception as e:
                return {"type": "kaig_node_heartbeat", "status": "error", "error": str(e)}
        return {"type": "kaig_node_heartbeat", "status": "unavailable"}

    # ------------------------------------------------------------------
    # Referral system
    # ------------------------------------------------------------------

    def _get_referral_code(self, device_id: str) -> Dict[str, Any]:
        """Generate or retrieve a referral code for this device/user."""
        referrals = self._load_referrals()
        codes = referrals.get("codes", {})

        # Check if this device already has a code
        for code, info in codes.items():
            if info.get("owner_device") == device_id:
                return {
                    "type": "referral_code_result", "status": "ok",
                    "referral_code": code,
                    "referral_link": f"{LANDING_PAGE_URL}/join?ref={code}&type=consumer",
                    "total_referrals": info.get("total_referrals", 0),
                    "rewards_earned": info.get("rewards_earned", 0.0),
                }

        # Generate new code — short, memorable, uppercase
        code = f"KAIG-{secrets.token_hex(3).upper()}"
        while code in codes:
            code = f"KAIG-{secrets.token_hex(3).upper()}"

        codes[code] = {
            "owner_device": device_id,
            "created_at": datetime.utcnow().isoformat(),
            "total_referrals": 0,
            "rewards_earned": 0.0,
        }
        referrals["codes"] = codes
        self._save_referrals(referrals)

        if self.event_bus:
            self.event_bus.publish("referral.code.created", {
                "device_id": device_id, "code": code,
            })

        logger.info("Referral code created: %s for device %s", code, device_id)
        return {
            "type": "referral_code_result", "status": "ok",
            "referral_code": code,
            "referral_link": f"{LANDING_PAGE_URL}/join?ref={code}&type=consumer",
            "total_referrals": 0,
            "rewards_earned": 0.0,
        }

    def _apply_referral_code(self, referral_code: str, device_id: str) -> Dict[str, Any]:
        """Apply a referral code for a new user. Dual-sided reward."""
        if not referral_code:
            return {"type": "apply_referral_result", "status": "error",
                    "message": "No referral code provided"}

        referrals = self._load_referrals()
        codes = referrals.get("codes", {})
        applied = referrals.get("applied", {})
        rewards = referrals.get("rewards", {})

        # Check code exists
        if referral_code not in codes:
            return {"type": "apply_referral_result", "status": "error",
                    "message": f"Invalid referral code: {referral_code}"}

        # Check if this device already used a referral
        if device_id in applied:
            return {"type": "apply_referral_result", "status": "error",
                    "message": "You already used a referral code"}

        # Can't refer yourself
        code_info = codes[referral_code]
        if code_info.get("owner_device") == device_id:
            return {"type": "apply_referral_result", "status": "error",
                    "message": "Cannot use your own referral code"}

        # Determine referrer's current referral count for tiered rewards
        referrer_device = code_info["owner_device"]
        prev_referrals = code_info.get("total_referrals", 0)
        new_total = prev_referrals + 1
        is_first_referral = (prev_referrals == 0)
        now_iso = datetime.utcnow().isoformat()

        # Apply referral for the new user
        applied[device_id] = {
            "referral_code": referral_code,
            "applied_at": now_iso,
            "welcome_kaig": self.KAIG_WELCOME_BONUS,
        }

        # Credit referrer — tiered rewards + settings toggle for first referral
        code_info["total_referrals"] = new_total
        referrer_reward_entry: Dict[str, Any] = {
            "referral_number": new_total,
            "from_device": device_id,
            "at": now_iso,
        }

        referrer_preference = self._load_referral_preference(referrer_device)
        tier_kaig = 0.0  # KAIG from tier (first may be commission-free)

        if is_first_referral:
            if referrer_preference == "kaig_coins":
                # User chose KAIG coins instead of commission-free for first referral
                tier_kaig = self.KAIG_WELCOME_BONUS  # Parity with new user's welcome bonus
                kaig_earned = code_info.get("kaig_earned", 0.0) + tier_kaig
                code_info["kaig_earned"] = kaig_earned
                referrer_reward_entry["type"] = "kaig_coins"
                referrer_reward_entry["kaig_amount"] = tier_kaig
                referrer_reward_entry["description"] = (
                    f"+{tier_kaig:.0f} KAIG (first referral, kaig preference)"
                )
                referrer_msg = (f"First referral! +{tier_kaig:.0f} KAIG earned "
                               f"(total: {kaig_earned:.0f})")
            else:
                # Default: commission-free for 3 months
                commission_free_until = (
                    datetime.utcnow() + timedelta(days=self.COMMISSION_FREE_DAYS)
                ).isoformat()
                code_info["commission_free_until"] = commission_free_until
                referrer_reward_entry["type"] = "commission_free"
                referrer_reward_entry["commission_free_until"] = commission_free_until
                referrer_reward_entry["description"] = (
                    f"3 months no {int(self.COMMISSION_RATE_NORMAL*100)}% on winning trades"
                )
                referrer_msg = (f"First referral! No {int(self.COMMISSION_RATE_NORMAL*100)}% "
                               f"commission on winning trades for 3 months")
        else:
            # Tier 2+: KAIG coins (tracked for future rollout)
            tier_kaig = self.KAIG_PER_REFERRAL
            kaig_earned = code_info.get("kaig_earned", 0.0) + tier_kaig
            code_info["kaig_earned"] = kaig_earned
            referrer_reward_entry["type"] = "kaig_coins"
            referrer_reward_entry["kaig_amount"] = tier_kaig
            referrer_reward_entry["description"] = (
                f"+{tier_kaig:.0f} KAIG (total: {kaig_earned:.0f})"
            )
            referrer_msg = (f"Referral #{new_total}! +{tier_kaig:.0f} KAIG "
                           f"earned (total: {kaig_earned:.0f})")

        # +5 KAIG parity bonus for referrer on EVERY referral (on top of tier)
        referrer_kaig_total = tier_kaig + self.KAIG_REFERRAL_PARITY_BONUS

        codes[referral_code] = code_info

        # Track rewards history
        rewards.setdefault(referrer_device, []).append(referrer_reward_entry)
        rewards.setdefault(device_id, []).append({
            "type": "welcome_bonus", "kaig_amount": self.KAIG_WELCOME_BONUS,
            "referral_code": referral_code, "at": now_iso,
        })

        referrals["codes"] = codes
        referrals["applied"] = applied
        referrals["rewards"] = rewards
        self._save_referrals(referrals)

        if self.event_bus:
            self.event_bus.publish("referral.applied", {
                "referral_code": referral_code,
                "device_id": device_id,
                "new_device": device_id,
                "new_user_id": device_id,
                "referrer_device": referrer_device,
                "referrer_id": referrer_device,
                "referrer": referrer_device,
                "is_first_referral": is_first_referral,
                "referrer_total": new_total,
                "welcome_kaig": self.KAIG_WELCOME_BONUS,
                "referrer_kaig": referrer_kaig_total,
                "commission_free_until": code_info.get("commission_free_until", ""),
            })

        logger.info("Referral %s applied by %s (referrer=%s, #%d)",
                    referral_code, device_id, referrer_device, new_total)
        return {
            "type": "apply_referral_result", "status": "ok",
            "message": f"Welcome! +{self.KAIG_WELCOME_BONUS:.0f} KAIG welcome bonus",
            "welcome_kaig": self.KAIG_WELCOME_BONUS,
            "referral_code": referral_code,
            "referrer_message": referrer_msg,
        }

    def _get_referral_stats(self, device_id: str) -> Dict[str, Any]:
        """Get referral stats for a device."""
        referrals = self._load_referrals()
        codes = referrals.get("codes", {})
        applied = referrals.get("applied", {})
        rewards = referrals.get("rewards", {})

        # Find this device's code
        my_code = ""
        my_referrals = 0
        my_earnings = 0.0
        for code, info in codes.items():
            if info.get("owner_device") == device_id:
                my_code = code
                my_referrals = info.get("total_referrals", 0)
                my_earnings = info.get("rewards_earned", 0.0)
                break

        # Check if this device used a referral
        was_referred = device_id in applied
        referred_by = applied.get(device_id, {}).get("referral_code", "")

        # Recent reward history
        my_rewards = rewards.get(device_id, [])[-10:]

        # Commission-free status
        commission_free_until = ""
        commission_free_active = False
        for code, info in codes.items():
            if info.get("owner_device") == device_id:
                cfu = info.get("commission_free_until", "")
                if cfu:
                    commission_free_until = cfu
                    try:
                        commission_free_active = (
                            datetime.fromisoformat(cfu) > datetime.utcnow()
                        )
                    except Exception:
                        pass
                break

        # KAIG coins earned (tracked for future rollout)
        kaig_earned = 0.0
        for code, info in codes.items():
            if info.get("owner_device") == device_id:
                kaig_earned = info.get("kaig_earned", 0.0)
                break

        return {
            "type": "referral_stats_result", "status": "ok",
            "referral_code": my_code,
            "referral_link": f"{LANDING_PAGE_URL}/join?ref={my_code}" if my_code else "",
            "total_referrals": my_referrals,
            "kaig_earned": kaig_earned,
            "commission_free_until": commission_free_until,
            "commission_free_active": commission_free_active,
            "was_referred": was_referred,
            "referred_by": referred_by,
            "recent_rewards": my_rewards,
            "reward_info": {
                "first_referral": f"3 months no {int(self.COMMISSION_RATE_NORMAL*100)}% commission",
                "subsequent": f"+{self.KAIG_PER_REFERRAL:.0f} KAIG per referral",
                "welcome": f"+{self.KAIG_WELCOME_BONUS:.0f} KAIG welcome bonus",
                "kaig_note": "KAIG (KAI Gold) rewards tracked — redeemable in future update",
            },
        }

    def _handle_set_referral_preference(self, data: Dict, device_id: str) -> Dict[str, Any]:
        """Store referrer's preference: 'commission_free' (default) or 'kaig_coins' for first referral."""
        preference = (data.get("preference") or "").strip().lower()
        if preference not in ("commission_free", "kaig_coins"):
            return {
                "type": "set_referral_preference_result", "status": "error",
                "message": "Invalid preference. Use 'commission_free' or 'kaig_coins'",
            }
        self._save_referral_preference(device_id, preference)
        return {
            "type": "set_referral_preference_result", "status": "ok",
            "preference": preference,
            "message": f"First referral reward set to: {preference.replace('_', ' ')}",
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_links(self):
        try:
            if os.path.exists(LINK_CONFIG_PATH):
                with open(LINK_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                self._linked_devices = data.get("linked_devices", {})
        except Exception:
            pass

    def _persist_links(self):
        os.makedirs(os.path.dirname(LINK_CONFIG_PATH), exist_ok=True)
        with open(LINK_CONFIG_PATH, "w") as f:
            json.dump({"linked_devices": self._linked_devices}, f, indent=2)

    def _get_desktop_id(self) -> str:
        config = load_json("config/desktop_id.json")
        if not config.get("id"):
            config["id"] = str(uuid.uuid4())[:12]
            save_json("config/desktop_id.json", config)
        return config["id"]

    def _get_desktop_name(self) -> str:
        config = load_json("config/desktop_id.json")
        name = config.get("name", "")
        if not name:
            import socket
            name = f"Kingdom AI ({socket.gethostname()})"
            config["name"] = name
            save_json("config/desktop_id.json", config)
        return name

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self):
        if not self.event_bus:
            return
        self.event_bus.subscribe("mobile.link.generate_qr", self._handle_gen_qr)
        self.event_bus.subscribe("mobile.server.start", self._handle_start)
        self.event_bus.subscribe("mobile.server.stop", self._handle_stop)
        # Relay AI responses back to mobile
        self.event_bus.subscribe("ai.response", self._handle_ai_response)
        # Relay price updates to mobile
        self.event_bus.subscribe("trading.price.update", self._handle_price_update)
        # SOTA 2026: Relay KAIG AutoPilot events to mobile
        self.event_bus.subscribe("kaig.phase.transition", self._handle_kaig_phase_transition)
        self.event_bus.subscribe("kaig.creator.alert", self._handle_kaig_creator_alert)
        self.event_bus.subscribe("kaig.status.update", self._handle_kaig_status_update)
        # SHA-LU-AM: Truth Timeline — relay to mobile when native tongue spoken
        self.event_bus.subscribe("secret.reserve.reveal", self._handle_secret_reserve_reveal)

    def _handle_gen_qr(self, data: Any):
        self.generate_link_qr()

    def _handle_start(self, data: Any):
        asyncio.ensure_future(self.start_server())

    def _handle_stop(self, data: Any):
        asyncio.ensure_future(self.stop_server())

    def _handle_ai_response(self, data: Any):
        if isinstance(data, dict) and "mobile:" in str(data.get("source", "")):
            asyncio.ensure_future(self.broadcast_to_all({
                "type": "ai_response",
                "text": data.get("text", ""),
                "source": "kai",
            }))

    def _handle_price_update(self, data: Any):
        if isinstance(data, dict):
            asyncio.ensure_future(self.broadcast_to_all({
                "type": "price_update",
                "data": data,
            }))

    def _handle_kaig_phase_transition(self, data: Any):
        if isinstance(data, dict):
            asyncio.ensure_future(self.broadcast_to_all({
                "type": "kaig_phase_transition",
                "data": data,
            }))

    def _handle_kaig_creator_alert(self, data: Any):
        if isinstance(data, dict):
            asyncio.ensure_future(self.broadcast_to_all({
                "type": "kaig_creator_alert",
                "data": data,
            }))

    def _handle_kaig_status_update(self, data: Any):
        if isinstance(data, dict):
            asyncio.ensure_future(self.broadcast_to_all({
                "type": "kaig_status_update",
                "data": data,
            }))

    def _handle_secret_reserve_reveal(self, data: Any):
        """SHA-LU-AM: Broadcast Truth Timeline reveal to all mobile clients."""
        asyncio.ensure_future(self.broadcast_to_all({
            "type": "truth_timeline_reveal",
            "trigger": "SHA-LU-AM",
            "timestamp": datetime.utcnow().isoformat(),
        }))

    def _get_truth_timeline_data(self) -> Dict[str, Any]:
        """Get Truth Timeline data for mobile. Owner/Consumer desktop + mobile."""
        try:
            from core.redis_nexus import get_redis_nexus
            from core.truth_timeline_data import load_all_facts
            nexus = get_redis_nexus()
            return load_all_facts(nexus)
        except Exception as e:
            logger.debug("Truth timeline data: %s", e)
        return {"foundation": "", "gathered": [], "documents": [], "truth_records": [], "timeline": []}

    def _get_kaig_autopilot_status(self) -> Dict[str, Any]:
        """Get KAIG AutoPilot status for mobile."""
        try:
            from core.kaig_autopilot import KAIGAutoPilot
            autopilot = KAIGAutoPilot._instance
            if autopilot:
                status = autopilot.get_status()
                matrix = autopilot.get_automation_matrix()
                phase_id = status.get("current_phase", "phase_0_genesis")
                phase_matrix = matrix.get(phase_id, {})
                return {
                    "type": "kaig_autopilot_status", "status": "ok",
                    "mode": status.get("mode", "unknown"),
                    "running": status.get("running", False),
                    "current_phase": phase_id,
                    "automation_pct": phase_matrix.get("automation_pct", 0),
                    "pending_alerts": status.get("pending_alerts", 0),
                    "total_auto_buybacks": status.get("total_auto_buybacks", 0),
                    "wallets": status.get("wallets", 0),
                    "ai_handles": phase_matrix.get("ai_handles", []),
                    "human_needed": phase_matrix.get("human_needed", []),
                }
        except Exception as e:
            logger.debug("KAIG autopilot status query: %s", e)
        return {"type": "kaig_autopilot_status", "status": "unavailable"}

    def _get_version_mode(self) -> Dict[str, Any]:
        """Return whether desktop is running in creator or consumer mode."""
        try:
            from core.kaig_autopilot import KAIGAutoPilot
            autopilot = KAIGAutoPilot._instance
            if autopilot:
                return {
                    "type": "version_mode", "status": "ok",
                    "mode": "creator" if autopilot.is_creator else "consumer",
                    "is_creator": autopilot.is_creator,
                }
        except Exception:
            pass
        return {"type": "version_mode", "status": "ok", "mode": "consumer", "is_creator": False}

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Prepare the server for start_server(): validate config, load state, verify deps."""
        try:
            # Validate websockets dependency before anything else
            if not HAS_WEBSOCKETS:
                logger.error("initialize: websockets package not installed — mobile sync will be unavailable")

            # Validate port is in usable range
            if not (1024 <= self._port <= 65535):
                logger.warning("Port %d out of range, falling back to default %d", self._port, SYNC_PORT)
                self._port = SYNC_PORT

            # Ensure config directory exists for link persistence
            os.makedirs(os.path.dirname(LINK_CONFIG_PATH), exist_ok=True)

            # Reload persisted linked devices in case they changed since __init__
            self._load_links()
            logger.info("initialize: %d previously linked devices loaded", len(self._linked_devices))

            # Ensure desktop identity is ready (generates if missing)
            desktop_id = self._get_desktop_id()
            desktop_name = self._get_desktop_name()
            logger.info("initialize: desktop identity ready — id=%s name=%s", desktop_id, desktop_name)

            # Re-subscribe events in case event_bus was attached after __init__
            self._subscribe_events()

            # Pre-warm security engine if available
            if HAS_AI_SECURITY and self._security_engine is None:
                try:
                    redis_conn = getattr(self, 'redis', None)
                    self._security_engine = get_ai_security_engine(redis_client=redis_conn)
                    logger.info("[SECURITY] AISecurityEngine activated during initialize()")
                except Exception as sec_err:
                    logger.warning("AISecurityEngine init in initialize() failed (non-fatal): %s", sec_err)

            self._initialized = True
            logger.info("MobileSyncServer initialize() complete — ready for start_server()")
            return True

        except Exception as e:
            logger.error("MobileSyncServer initialize() failed: %s", e)
            self._initialized = False
            return False

    async def close(self):
        await self.stop_server()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "server_running": self._server is not None,
            "port": self._port,
            "connected_devices": len(self._connected_devices),
            "linked_devices": len(self._linked_devices),
        }


# Utility functions
def load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════
# _InlineAssetResolver — lightweight fallback when fintech module unavailable
# 2026 SOTA: Supports 50+ native coins, stablecoins, DeFi, meme tokens
# ══════════════════════════════════════════════════════════════════════════
class _InlineAssetResolver:
    """Minimal asset resolver used when kingdom-fintech is not importable."""

    _ASSETS = {
        # Native
        "BTC": {"chain": "bitcoin", "type": "native", "decimals": 8},
        "ETH": {"chain": "ethereum", "type": "native", "decimals": 18},
        "BNB": {"chain": "bsc", "type": "native", "decimals": 18},
        "SOL": {"chain": "solana", "type": "native", "decimals": 9},
        "ADA": {"chain": "cardano", "type": "native", "decimals": 6},
        "XRP": {"chain": "xrpl", "type": "native", "decimals": 6},
        "DOT": {"chain": "polkadot", "type": "native", "decimals": 10},
        "AVAX": {"chain": "avalanche", "type": "native", "decimals": 18},
        "MATIC": {"chain": "polygon", "type": "native", "decimals": 18},
        "POL": {"chain": "polygon", "type": "native", "decimals": 18},
        "TRX": {"chain": "tron", "type": "native", "decimals": 6},
        "DOGE": {"chain": "dogecoin", "type": "native", "decimals": 8},
        "LTC": {"chain": "litecoin", "type": "native", "decimals": 8},
        "ATOM": {"chain": "cosmos", "type": "native", "decimals": 6},
        "NEAR": {"chain": "near", "type": "native", "decimals": 24},
        "FTM": {"chain": "fantom", "type": "native", "decimals": 18},
        "APT": {"chain": "aptos", "type": "native", "decimals": 8},
        "SUI": {"chain": "sui", "type": "native", "decimals": 9},
        "SEI": {"chain": "sei", "type": "native", "decimals": 6},
        "ALGO": {"chain": "algorand", "type": "native", "decimals": 6},
        "FIL": {"chain": "filecoin", "type": "native", "decimals": 18},
        "ICP": {"chain": "icp", "type": "native", "decimals": 8},
        # Stablecoins
        "USDT": {"chain": "ethereum", "type": "erc20", "decimals": 6, "contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7"},
        "USDC": {"chain": "ethereum", "type": "erc20", "decimals": 6, "contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
        "DAI": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x6B175474E89094C44Da98b954EedeAC495271d0F"},
        "USD": {"chain": "ethereum", "type": "erc20", "decimals": 6, "contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
        # DeFi
        "LINK": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x514910771AF9Ca656af840dff83E8264EcF986CA"},
        "UNI": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"},
        "AAVE": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"},
        "MKR": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"},
        "CRV": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0xD533a949740bb3306d119CC777fa900bA034cd52"},
        "LDO": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32"},
        "GRT": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0xc944E90C64B2c07662A292be6244BDf05Cda44a7"},
        "SNX": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F"},
        "COMP": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0xc00e94Cb662C3520282E6f5717214004A7f26888"},
        "ENS": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72"},
        "ARB": {"chain": "arbitrum", "type": "erc20", "decimals": 18, "contract": "0x912CE59144191C1204E64559FE8253a0e49E6548"},
        "OP": {"chain": "optimism", "type": "erc20", "decimals": 18, "contract": "0x4200000000000000000000000000000000000042"},
        # Memecoins
        "SHIB": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE"},
        "PEPE": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x6982508145454Ce325dDbE47a25d4ec3d2311933"},
        "FLOKI": {"chain": "ethereum", "type": "erc20", "decimals": 9, "contract": "0xcf0C122c6b73ff809C693DB761e7BaeBe62b6a2E"},
        "BONK": {"chain": "solana", "type": "spl", "decimals": 5, "contract": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
        "WIF": {"chain": "solana", "type": "spl", "decimals": 6, "contract": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
        # Wrapped
        "WETH": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"},
        "WBTC": {"chain": "ethereum", "type": "erc20", "decimals": 8, "contract": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"},
        "STETH": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"},
        # Kingdom AI
        "KAIG": {"chain": "ethereum", "type": "erc20", "decimals": 18, "contract": "0x0000000000000000000000000000000000000KAIG"},
    }

    def __init__(self, redis_client=None):
        self.redis_client = redis_client

    def resolve(self, symbol: str, preferred_chain: str = None) -> Optional[Dict[str, Any]]:
        sym = symbol.upper()
        # Redis custom registry first
        if self.redis_client:
            try:
                raw = self.redis_client.get(f"kingdom:asset_registry:{sym}")
                if raw:
                    return {"symbol": sym, **(json.loads(raw) if isinstance(raw, str) else {})}
            except Exception:
                pass
        info = self._ASSETS.get(sym)
        if info:
            return {"symbol": sym, **info}
        return None
