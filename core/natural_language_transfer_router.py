"""Kingdom AI - Natural-Language Transfer Router
=================================================

Single entry point that turns a free-text user command into an executable,
cross-venue money-movement plan.

Examples that work out of the box::

    move $500 from kraken to polymarket
    send 100 USDC from coinbase to my eth wallet
    withdraw $1000 from alpaca to my bank
    fund polymarket with 200 USDC from kraken
    move all my AVAX from kraken to binanceus
    transfer 0.1 BTC from my kingdom wallet to kraken
    sell $300 of AAPL on alpaca and move the cash to coinbase
    shift 25% of my USDC out of coinbase into polymarket

Architecture
------------
``NaturalLanguageTransferRouter`` has three layers:

1. **Intent parser** - deterministic regex + venue fuzzy match, with
   optional Ollama fallback when the regex fails. No LLM is *required*.
2. **Plan builder** - consults
   :mod:`core.trading_funding_matrix` and the cross-venue route truth
   table to produce a :class:`TransferPlan` (possibly multi-leg).
3. **Executor** - delegates each leg to the real engines:
     * crypto legs -> :class:`core.cross_venue_transfer_manager.CrossVenueTransferManager`
     * equity sell legs -> :class:`core.real_stock_executor.RealStockExecutor`
     * equity buy legs  -> same
     * on-chain legs    -> :class:`core.multichain_trade_executor.MultiChainTradeExecutor`
       (via the cross-venue manager's ``_onchain_*`` helpers)

Every plan returns rich structured data suitable for voice readback
("three legs: sell 300 AAPL on alpaca, withdraw $297 to your bank, then
swap into USDC on kraken - shall I proceed?").
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

logger = logging.getLogger("KingdomAI.NLTransferRouter")


# ---------------------------------------------------------------------------
# Venue alias table - auto-generated from the sources of truth
# ---------------------------------------------------------------------------
# Rather than hardcode names, we pull every declared venue from:
#   * ``core.api_key_manager.APIKeyManager.CATEGORIES``
#   * ``core.trading_funding_matrix.VENUE_FUNDING``
# and synthesize aliases: canonical, lowercased, dash/space/dot variants,
# plus curated nicknames for the common ones the user actually speaks.

# Curated nicknames only - covers abbreviations and branding differences.
# Everything else is auto-generated. Keys must be lowercased.
_NICKNAMES: Dict[str, str] = {
    # Crypto CEX nicknames
    "cb": "coinbase", "coinbase pro": "coinbase", "coinbase advanced": "coinbase",
    "binance global": "binance", "binance international": "binance",
    "binance.us": "binanceus", "binance us": "binanceus", "bus": "binanceus",
    "huobi": "htx", "hx": "htx",
    "okex": "okx",
    "gate": "gate_io", "gate.io": "gate_io", "gateio": "gate_io",
    "crypto.com": "crypto_com", "cryptocom": "crypto_com", "cdc": "crypto_com",
    "cryptodotcom": "crypto_com",
    "woo": "woo_x", "woonetwork": "woo_x", "woo network": "woo_x",
    "poly": "polymarket",
    # Broker nicknames
    "tasty": "tastytrade", "tasty trade": "tastytrade",
    "charles schwab": "schwab",
    "rh": "robinhood",
    "e-trade": "etrade", "e*trade": "etrade", "e trade": "etrade",
    "ibkr": "interactive_brokers", "interactive brokers": "interactive_brokers",
    "ib": "interactive_brokers",
    "td": "td_ameritrade", "td ameritrade": "td_ameritrade",
    "ninja": "ninjatrader", "nt": "ninjatrader", "ninjatrader 8": "ninjatrader",
    "lightspeed trader": "lightspeed",
    "public": "public_api", "public.com": "public_api", "public com": "public_api",
    # Forex nicknames
    "forex.com": "forex_com", "forexcom": "forex_com", "forex com": "forex_com",
    "ig": "ig_markets", "ig markets": "ig_markets",
    "mt4": "mt4_bridge", "mt5": "mt5_bridge",
    "meta trader 4": "mt4_bridge", "meta trader 5": "mt5_bridge",
    "metatrader4": "mt4_bridge", "metatrader5": "mt5_bridge",
    "ic markets": "icmarkets",
    # On-chain / kingdom wallets - virtual venues outside APIKeyManager
    "my wallet": "kingdom_wallet", "kingdom wallet": "kingdom_wallet",
    "kingdom ai wallet": "kingdom_wallet", "kingdom": "kingdom_wallet",
    "on chain": "kingdom_wallet", "on-chain": "kingdom_wallet",
    "onchain": "kingdom_wallet", "self custody": "kingdom_wallet",
    "cold wallet": "kingdom_wallet", "hot wallet": "kingdom_wallet",
    "kingdom hot": "kingdom_wallet", "kingdom cold": "kingdom_wallet",
    "eth wallet": "kingdom_wallet:ethereum",
    "ethereum wallet": "kingdom_wallet:ethereum",
    "my eth": "kingdom_wallet:ethereum", "my ethereum": "kingdom_wallet:ethereum",
    "sol wallet": "kingdom_wallet:solana",
    "solana wallet": "kingdom_wallet:solana",
    "my sol": "kingdom_wallet:solana", "my solana": "kingdom_wallet:solana",
    "btc wallet": "kingdom_wallet:bitcoin",
    "bitcoin wallet": "kingdom_wallet:bitcoin",
    "my btc": "kingdom_wallet:bitcoin", "my bitcoin": "kingdom_wallet:bitcoin",
    "polygon wallet": "kingdom_wallet:polygon",
    "matic wallet": "kingdom_wallet:polygon",
    "my matic": "kingdom_wallet:polygon", "my polygon": "kingdom_wallet:polygon",
    "bsc wallet": "kingdom_wallet:bsc", "bnb wallet": "kingdom_wallet:bsc",
    "avax wallet": "kingdom_wallet:avalanche",
    "avalanche wallet": "kingdom_wallet:avalanche",
    "arbitrum wallet": "kingdom_wallet:arbitrum",
    "arb wallet": "kingdom_wallet:arbitrum",
    "optimism wallet": "kingdom_wallet:optimism",
    "op wallet": "kingdom_wallet:optimism",
    "base wallet": "kingdom_wallet:base",
    # Bank / fiat
    "my bank": "bank", "bank": "bank", "checking": "bank",
    "savings": "bank", "linked bank": "bank", "my checking": "bank",
    "my savings": "bank", "ach": "bank", "wire": "bank",
}


def _canonical_variants(name: str) -> List[str]:
    """Return all plausible user-facing variants of a canonical venue key."""
    name = name.strip()
    if not name:
        return []
    lowered = name.lower()
    variants = {lowered, lowered.replace("_", " "), lowered.replace("_", "-"),
                lowered.replace("_", "."), lowered.replace("_", "")}
    # For compound names, also include first token ("binance_futures" -> "binance")
    if "_" in lowered:
        head = lowered.split("_", 1)[0]
        if len(head) >= 3:
            variants.add(head + " " + lowered.split("_", 1)[1])
    return list(variants)


def _build_venue_aliases() -> Dict[str, str]:
    """Auto-build the alias table from CATEGORIES + VENUE_FUNDING + nicknames."""
    aliases: Dict[str, str] = {}

    # 1) Every venue declared in APIKeyManager.CATEGORIES
    try:
        from core.api_key_manager import APIKeyManager
        for cat_venues in (APIKeyManager.CATEGORIES or {}).values():
            for canonical in cat_venues:
                for v in _canonical_variants(str(canonical)):
                    aliases.setdefault(v, canonical)
    except Exception as exc:
        logger.debug("Could not load APIKeyManager categories: %s", exc)

    # 2) Every venue declared in VENUE_FUNDING (may overlap but we pick up
    #    on-chain/prediction virtual venues that aren't in CATEGORIES)
    try:
        from core.trading_funding_matrix import VENUE_FUNDING
        for canonical in VENUE_FUNDING.keys():
            for v in _canonical_variants(str(canonical)):
                aliases.setdefault(v, canonical)
    except Exception as exc:
        logger.debug("Could not load VENUE_FUNDING: %s", exc)

    # 3) Curated nicknames ALWAYS win (they're aliases, not new canonicals)
    for alias, canonical in _NICKNAMES.items():
        aliases[alias.lower()] = canonical

    return aliases


# Computed once at import time; exported for visibility.
VENUE_ALIASES: Dict[str, str] = _build_venue_aliases()


# ---------------------------------------------------------------------------
# Asset-name -> canonical ticker lookup
# ---------------------------------------------------------------------------
# Users say "bitcoin" more often than "BTC". This maps spoken/typed names
# to canonical trading symbols.
ASSET_NAME_TO_TICKER: Dict[str, str] = {
    # Majors
    "bitcoin": "BTC", "btc": "BTC",
    "ether": "ETH", "ethereum": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
    "ripple": "XRP", "xrp": "XRP",
    "cardano": "ADA", "ada": "ADA",
    "polkadot": "DOT", "dot": "DOT",
    "avalanche": "AVAX", "avax": "AVAX",
    "polygon": "MATIC", "matic": "MATIC", "pol": "POL",
    "bnb": "BNB", "binance coin": "BNB",
    "dogecoin": "DOGE", "doge": "DOGE",
    "shiba inu": "SHIB", "shib": "SHIB",
    "litecoin": "LTC", "ltc": "LTC",
    "chainlink": "LINK", "link": "LINK",
    "uniswap": "UNI", "uni": "UNI",
    "near protocol": "NEAR", "near": "NEAR",
    "aptos": "APT", "apt": "APT",
    "sui": "SUI",
    "arbitrum": "ARB", "arb": "ARB",
    "optimism": "OP", "op": "OP",
    "pepe": "PEPE",
    "toncoin": "TON", "ton": "TON",
    "tron": "TRX", "trx": "TRX",
    "monero": "XMR", "xmr": "XMR",
    "atom": "ATOM", "cosmos": "ATOM",
    "algorand": "ALGO", "algo": "ALGO",
    # Stablecoins
    "usdc": "USDC", "usd coin": "USDC",
    "usdt": "USDT", "tether": "USDT",
    "dai": "DAI",
    "busd": "BUSD", "binance usd": "BUSD",
    "tusd": "TUSD", "true usd": "TUSD",
    "frax": "FRAX",
    "usdg": "USDG",
    # Fiat proxies
    "dollars": "USD", "usd": "USD", "dollar": "USD",
    "euros": "EUR", "eur": "EUR", "euro": "EUR",
    "pounds": "GBP", "gbp": "GBP", "pound": "GBP",
    "yen": "JPY", "jpy": "JPY",
}

# Phrases that mean "use the full balance". Word-boundary regex to avoid
# false positives like "wallet" matching "all".
ALL_PHRASES_RE = re.compile(
    r"\b(?:all(?:\s+(?:my|the|of|of\s+my|of\s+the))?|everything|"
    r"the\s+rest|the\s+balance|the\s+whole\s+thing|"
    r"whatever(?:\s+is|'s)?|my\s+entire|my\s+whole|my\s+full|"
    r"max(?:imum)?|every\s+last|every\s+single|full\s+balance|"
    r"100\s*%)\b",
    re.IGNORECASE,
)

# Fractional quantity words
FRACTION_WORDS: Dict[str, float] = {
    "half": 50.0, "a half": 50.0, "one half": 50.0, "1/2": 50.0,
    "quarter": 25.0, "a quarter": 25.0, "one quarter": 25.0, "1/4": 25.0,
    "third": 33.333, "a third": 33.333, "one third": 33.333, "1/3": 33.333,
    "two thirds": 66.666, "2/3": 66.666,
    "three quarters": 75.0, "3/4": 75.0, "three fourths": 75.0,
    "eighth": 12.5, "an eighth": 12.5, "one eighth": 12.5, "1/8": 12.5,
    "tenth": 10.0, "a tenth": 10.0, "one tenth": 10.0, "1/10": 10.0,
    "fifth": 20.0, "a fifth": 20.0, "one fifth": 20.0, "1/5": 20.0,
}
FRACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(FRACTION_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Asset symbol heuristics - anything uppercase 2-6 letters that isn't a known
# venue alias is treated as an asset ticker.
ASSET_TICKER_RE = re.compile(r"\b([A-Z]{2,6})\b")

# Dollar-amount regex: "$500", "$ 500.25", "500 dollars", "500 bucks"
DOLLAR_RE = re.compile(
    r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:k|K|m|M)?\b"
    r"|\b([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:dollars|usd|bucks)\b",
    re.IGNORECASE,
)

# Unit-amount regex: "100 USDC", "0.1 BTC"
UNIT_RE = re.compile(
    r"\b([0-9][0-9,]*(?:\.[0-9]+)?)\s*([A-Z]{2,6})\b"
)

# Percentage: "25%", "50 percent"
PCT_RE = re.compile(r"\b([0-9]{1,3}(?:\.[0-9]+)?)\s*(?:%|percent\b)",
                    re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class LegType(str, Enum):
    SELL = "sell"          # sell a position to produce cash (equity/stock)
    BUY = "buy"            # buy an asset at destination after cash arrives
    CRYPTO_TRANSFER = "crypto_transfer"
    ACH_OUT = "ach_out"    # broker -> bank
    ACH_IN = "ach_in"      # bank -> broker
    MANUAL = "manual"      # user portal required
    INFO = "info"          # informational; never executes


class PlanStatus(str, Enum):
    READY = "ready"
    NEEDS_CONFIRMATION = "needs_confirmation"
    REJECTED = "rejected"
    PARTIAL = "partial"


@dataclass
class IntentParseResult:
    raw_text: str
    action: str                       # "move", "withdraw", "fund", "sell_and_move"
    amount: Optional[float] = None
    amount_kind: Optional[str] = None  # "usd" | "unit" | "all" | "percent"
    asset: Optional[str] = None
    from_venue: Optional[str] = None
    to_venue: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "action": self.action,
            "amount": self.amount,
            "amount_kind": self.amount_kind,
            "asset": self.asset,
            "from_venue": self.from_venue,
            "to_venue": self.to_venue,
            "confidence": self.confidence,
            "extras": self.extras,
            "errors": list(self.errors),
        }


@dataclass
class PlanLeg:
    leg_type: LegType
    venue: str
    asset: str
    amount: float
    note: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leg_type": self.leg_type.value,
            "venue": self.venue,
            "asset": self.asset,
            "amount": self.amount,
            "note": self.note,
            "details": self.details,
        }


@dataclass
class TransferPlan:
    plan_id: str
    intent: IntentParseResult
    legs: List[PlanLeg] = field(default_factory=list)
    status: PlanStatus = PlanStatus.NEEDS_CONFIRMATION
    narrative: str = ""
    warnings: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "intent": self.intent.to_dict(),
            "legs": [leg.to_dict() for leg in self.legs],
            "status": self.status.value,
            "narrative": self.narrative,
            "warnings": list(self.warnings),
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Intent parser (deterministic, no LLM required)
# ---------------------------------------------------------------------------

# Action verbs - SOTA 2026 comprehensive vocabulary
_ACTION_MAP = [
    (re.compile(
        r"\b(sell|liquidate|unload|dump|close\s+(?:out|position))\b.+"
        r"\b(move|send|transfer|buy|into|to|over\s+to|wire|ach|route)\b",
        re.IGNORECASE,
    ), "sell_and_move"),
    (re.compile(
        r"\b(withdraw|cash\s*out|cashout|exit|pull|yank|retrieve|"
        r"take\s+out|take\s+off|pull\s+out|redeem)\b",
        re.IGNORECASE,
    ), "withdraw"),
    (re.compile(
        r"\b(fund|deposit|top\s*up|top-up|load|put\s+(?:into|in)|add)\b",
        re.IGNORECASE,
    ), "fund"),
    (re.compile(
        r"\b(move|send|transfer|shift|push|route|wire|beam|flip|"
        r"rotate|swap\s+(?:out|over)|migrate|relocate|bridge|ship|"
        r"sweep|yeet|zap)\b",
        re.IGNORECASE,
    ), "move"),
    (re.compile(
        r"\b(convert|exchange|swap|trade)\b.+\b(to|into|for)\b",
        re.IGNORECASE,
    ), "convert"),
]


_VENUE_FILLERS = re.compile(
    r"\b(?:my|the|a|an|our|some|please|account|exchange|wallet|"
    r"brokerage|broker|app)\b",
    re.IGNORECASE,
)


def _fuzzy_venue(token: str) -> Optional[str]:
    """Map a free-text venue phrase to a canonical key using VENUE_ALIASES.

    Strategy:
      1) Exact match on the full phrase.
      2) Exact match on the phrase with filler words stripped.
      3) Token-level longest-alias match (prefers multi-token aliases).
      4) Substring fallback (bias toward longer matches, but require
         word-boundary to avoid "pol" matching "polkadot wallet").
    """
    if not token:
        return None
    raw = token.strip().lower()
    if raw in VENUE_ALIASES:
        return VENUE_ALIASES[raw]

    stripped = _VENUE_FILLERS.sub(" ", raw)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if stripped and stripped in VENUE_ALIASES:
        return VENUE_ALIASES[stripped]

    # Token-level match: try every contiguous ngram against the alias table,
    # longest ngram first. This lets "binance us account" -> "binance us".
    tokens = stripped.split() if stripped else raw.split()
    for n in range(min(len(tokens), 4), 0, -1):
        for i in range(0, len(tokens) - n + 1):
            ngram = " ".join(tokens[i:i + n])
            if ngram in VENUE_ALIASES:
                return VENUE_ALIASES[ngram]

    # Substring fallback - find the longest alias that appears as a word
    # boundary in the phrase.
    best: Optional[str] = None
    best_len = 0
    for alias, canon in VENUE_ALIASES.items():
        if len(alias) <= best_len:
            continue
        # Require word boundaries on both ends for single-token aliases.
        if " " in alias:
            if alias in raw:
                best, best_len = canon, len(alias)
        else:
            if re.search(r"\b" + re.escape(alias) + r"\b", raw):
                best, best_len = canon, len(alias)
    return best


def _resolve_asset(token: Optional[str]) -> Optional[str]:
    """Map a free-text asset phrase to a canonical ticker."""
    if not token:
        return None
    t = token.strip().lower()
    if t in ASSET_NAME_TO_TICKER:
        return ASSET_NAME_TO_TICKER[t]
    # If it's already a ticker-looking symbol
    if re.fullmatch(r"[A-Za-z]{2,6}", token.strip()):
        return token.strip().upper()
    return None


def parse_intent(text: str) -> IntentParseResult:
    """Parse a natural-language command into a structured intent.

    Works on its own for the common cases. If confidence < 0.6 the caller
    should fall back to an Ollama intent extractor or re-prompt the user.
    """
    out = IntentParseResult(raw_text=text, action="unknown")
    cleaned = text.strip()
    lower = cleaned.lower()
    confidence = 0.0

    # ---- Action ---------------------------------------------------------
    for regex, action in _ACTION_MAP:
        if regex.search(cleaned):
            out.action = action
            confidence += 0.15
            break

    # ---- Venues: "sell/liquidate ... on X ... (move|send|transfer|to) Y"
    m_sell_move = re.search(
        r"\b(?:sell|liquidate)\b.+?\bon\s+(?P<src>[a-z0-9_\.\- ]+?)\s+"
        r"(?:and|then|,)\s+(?:move|send|transfer|push|route|shift)\s+"
        r"(?:the\s+\w+\s+)?(?:to|into)\s+(?P<dst>[a-z0-9_\.\- ]+?)"
        r"(?:$|[\.,]|\bwith\b|\busing\b|\bat\b|\bfor\b)",
        lower,
    )
    if m_sell_move:
        out.from_venue = _fuzzy_venue(m_sell_move.group("src"))
        out.to_venue = _fuzzy_venue(m_sell_move.group("dst"))
        if out.from_venue:
            confidence += 0.2
        if out.to_venue:
            confidence += 0.2

    # ---- Venues: "from|out of X to|into Y" -----------------------------
    # Terminator: end-of-string, comma, period followed by space/EOL (so
    # brand names like "crypto.com" / "forex.com" survive), or a filler kw.
    m_from_to = None if out.from_venue and out.to_venue else re.search(
        r"\b(?:from|out\s+of)\s+(?P<src>[a-z0-9_\.\- ]+?)\s+"
        r"(?:to|into|over\s+to)\s+"
        r"(?P<dst>[a-z0-9_\.\- ]+?)"
        r"(?:$|,|\.(?:\s|$)|\bwith\b|\busing\b|\bat\b|\bfor\b)",
        lower,
    )
    if m_from_to:
        out.from_venue = _fuzzy_venue(m_from_to.group("src"))
        out.to_venue = _fuzzy_venue(m_from_to.group("dst"))
        if out.from_venue:
            confidence += 0.2
        if out.to_venue:
            confidence += 0.2
    elif not (out.from_venue and out.to_venue):
        # Handle "fund X with Y from Z"
        m_fund = re.search(
            r"\bfund\s+(?P<dst>[a-z0-9_\.\- ]+?)\s+with\s+.+?\bfrom\s+"
            r"(?P<src>[a-z0-9_\.\- ]+?)(?:$|,|\.(?:\s|$))",
            lower,
        )
        if m_fund:
            out.to_venue = _fuzzy_venue(m_fund.group("dst"))
            out.from_venue = _fuzzy_venue(m_fund.group("src"))
            if out.from_venue:
                confidence += 0.2
            if out.to_venue:
                confidence += 0.2
        else:
            # "withdraw from X to bank"
            m_w = re.search(
                r"\bwithdraw\s+.*?\bfrom\s+(?P<src>[a-z0-9_\.\- ]+?)"
                r"(?:\s+(?:to|into)\s+(?P<dst>[a-z0-9_\.\- ]+?))?"
                r"(?:$|,|\.(?:\s|$))",
                lower,
            )
            if m_w:
                out.from_venue = _fuzzy_venue(m_w.group("src"))
                if out.from_venue:
                    confidence += 0.2
                if m_w.group("dst"):
                    out.to_venue = _fuzzy_venue(m_w.group("dst"))
                    if out.to_venue:
                        confidence += 0.15
                else:
                    out.to_venue = "bank"
                    confidence += 0.1

            # "convert X on <venue1> to Y and send to <venue2>"
            if not (out.from_venue and out.to_venue):
                m_convert = re.search(
                    r"\bconvert\s+.+?\bon\s+(?P<src>[a-z0-9_\.\- ]+?)\b"
                    r".+?\b(?:to|into)\s+(?P<asset2>[a-z]{2,10})\b"
                    r".+?\b(?:send|move|transfer|push)\s+to\s+"
                    r"(?P<dst>[a-z0-9_\.\- ]+?)(?:$|,|\.(?:\s|$))",
                    lower,
                )
                if m_convert:
                    out.from_venue = _fuzzy_venue(m_convert.group("src"))
                    out.to_venue = _fuzzy_venue(m_convert.group("dst"))
                    out.action = "convert_and_move"
                    if out.from_venue:
                        confidence += 0.2
                    if out.to_venue:
                        confidence += 0.2

    # ---- Amount ---------------------------------------------------------
    # Priority: explicit "all/everything" > fraction word > percent >
    #           unit (100 USDC) > $ amount
    if ALL_PHRASES_RE.search(cleaned):
        out.amount = None
        out.amount_kind = "all"
        confidence += 0.15
    else:
        m_frac = FRACTION_RE.search(cleaned)
        m_pct = PCT_RE.search(cleaned)
        m_unit = UNIT_RE.search(cleaned)
        m_dollar = DOLLAR_RE.search(cleaned)
        if m_pct:
            out.amount = float(m_pct.group(1))
            out.amount_kind = "percent"
            confidence += 0.15
        elif m_frac:
            out.amount = FRACTION_WORDS[m_frac.group(1).lower()]
            out.amount_kind = "percent"
            confidence += 0.15
        elif m_unit and m_unit.group(2).upper() not in {"USD"}:
            # "100 USDC" / "0.1 BTC"
            raw_amount = float(m_unit.group(1).replace(",", ""))
            raw_ticker = m_unit.group(2).upper()
            out.amount = raw_amount
            out.asset = raw_ticker
            out.amount_kind = "unit"
            confidence += 0.2
        elif m_dollar:
            grp = m_dollar.group(1) or m_dollar.group(2)
            val = float(grp.replace(",", ""))
            # Handle K/M suffix
            raw = m_dollar.group(0).lower()
            if "k" in raw:
                val *= 1000
            elif "m" in raw:
                val *= 1_000_000
            out.amount = val
            out.amount_kind = "usd"
            confidence += 0.2

    # ---- Asset ----------------------------------------------------------
    if out.asset is None:
        # 1) Explicit "of ASSET" (works for tickers and for named assets)
        m_of = re.search(r"\bof\s+([A-Za-z][A-Za-z\s]{1,20})",
                         cleaned.lower())
        if m_of:
            candidate = m_of.group(1).strip()
            # Trim trailing filler like "on alpaca"
            candidate = re.split(r"\b(?:on|from|to|into)\b", candidate)[0].strip()
            resolved = _resolve_asset(candidate)
            if resolved:
                out.asset = resolved
                confidence += 0.1

    if out.asset is None:
        # 2) Named assets ("bitcoin", "solana", "dogecoin") anywhere in text
        lowered_cmp = lower
        for name, ticker in ASSET_NAME_TO_TICKER.items():
            if " " in name:
                if name in lowered_cmp:
                    out.asset = ticker
                    confidence += 0.1
                    break
            else:
                if re.search(r"\b" + re.escape(name) + r"\b", lowered_cmp):
                    out.asset = ticker
                    confidence += 0.1
                    break

    if out.asset is None:
        # 3) Fallback: standalone uppercase tickers
        for tok in ASSET_TICKER_RE.findall(cleaned):
            if tok.upper() in {"USD", "ACH", "KYC", "API", "ETF", "IRA",
                                "ETH", "BTC"}:
                # Keep common crypto tickers, skip obvious acronyms
                if tok.upper() in {"USD", "ACH", "KYC", "API", "ETF", "IRA"}:
                    continue
            if tok.lower() in VENUE_ALIASES:
                continue
            out.asset = tok.upper()
            confidence += 0.1
            break

    # Default asset is USDC for crypto routes, USD for broker routes.
    if out.asset is None:
        out.asset = "USDC"

    out.confidence = round(min(confidence, 1.0), 3)

    # ---- Error report ---------------------------------------------------
    if not out.from_venue:
        out.errors.append("could not identify source venue")
    if not out.to_venue:
        out.errors.append("could not identify destination venue")
    if out.amount is None and out.amount_kind is None:
        out.errors.append("could not identify an amount")

    return out


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------


def _venue_category(venue: str, funding_info: Mapping[str, Any]) -> str:
    """Return the category from the funding matrix (or 'on_chain' for
    kingdom_wallet / 'bank' for bank).
    """
    if not venue:
        return "unknown"
    if venue.startswith("kingdom_wallet"):
        return "on_chain"
    if venue == "bank":
        return "bank"
    v = funding_info.get(venue, {})
    return str(v.get("category", "unknown"))


def _normalize_asset_for_route(asset: str, from_cat: str, to_cat: str) -> str:
    """Pick a sensible default asset if the user said "$500" without a symbol."""
    if asset and asset not in ("USD", "USDC", "USDT"):
        return asset
    # Broker cash rails use USD; crypto rails use USDC.
    if from_cat in ("equity_broker", "forex", "bank") or \
       to_cat in ("equity_broker", "forex", "bank"):
        return "USD"
    return "USDC" if asset in (None, "", "USDC", "USD") else asset


class NaturalLanguageTransferRouter:
    """High-level orchestrator. Parses text, builds a plan, and executes it."""

    def __init__(
        self,
        cross_venue_manager=None,
        real_stock_executor=None,
        event_bus=None,
        funding_info: Optional[Mapping[str, Any]] = None,
    ):
        self.cross_venue_manager = cross_venue_manager
        self.real_stock_executor = real_stock_executor
        self.event_bus = event_bus
        # Curated venue knowledge
        if funding_info is None:
            try:
                from core.trading_funding_matrix import VENUE_FUNDING
                funding_info = VENUE_FUNDING
            except Exception:
                funding_info = {}
        self.funding_info: Mapping[str, Any] = funding_info

    # ------------------------------------------------------------------
    def parse(self, text: str) -> IntentParseResult:
        return parse_intent(text)

    # ------------------------------------------------------------------
    def build_plan(self, text_or_intent) -> TransferPlan:
        """Parse (if needed) and build an executable plan."""
        if isinstance(text_or_intent, IntentParseResult):
            intent = text_or_intent
        else:
            intent = self.parse(str(text_or_intent))

        plan = TransferPlan(plan_id=str(uuid.uuid4())[:8], intent=intent)

        # Short-circuit: missing critical fields
        if intent.errors:
            plan.status = PlanStatus.REJECTED
            plan.narrative = (
                "I couldn't parse the request: "
                + "; ".join(intent.errors)
                + ". Please restate with a clear source, destination, and amount."
            )
            return plan

        from_info = self.funding_info.get(intent.from_venue, {}) \
            if intent.from_venue not in (None, "bank") and \
               not (intent.from_venue or "").startswith("kingdom_wallet") else {}
        to_info = self.funding_info.get(intent.to_venue, {}) \
            if intent.to_venue not in (None, "bank") and \
               not (intent.to_venue or "").startswith("kingdom_wallet") else {}

        from_cat = _venue_category(intent.from_venue, self.funding_info)
        to_cat = _venue_category(intent.to_venue, self.funding_info)
        asset = _normalize_asset_for_route(intent.asset or "", from_cat, to_cat)
        amount = intent.amount or 0.0

        # Legal/regulatory gate - reject up front if either side is dead or blocked.
        for label, info in (("source", from_info), ("destination", to_info)):
            legal = info.get("legal", "")
            if legal in ("defunct",):
                plan.status = PlanStatus.REJECTED
                plan.legs.append(PlanLeg(
                    LegType.INFO,
                    intent.from_venue if label == "source" else intent.to_venue,
                    asset, amount,
                    note=f"{label.title()} venue is defunct - no funds can be moved.",
                ))
                plan.narrative = self._narrate(plan)
                return plan

        plan = self._build_category_driven_plan(
            plan, intent, from_cat, to_cat, asset, amount,
            from_info, to_info,
        )

        plan.narrative = self._narrate(plan)
        return plan

    # ------------------------------------------------------------------
    def _build_category_driven_plan(
        self,
        plan: TransferPlan,
        intent: IntentParseResult,
        from_cat: str,
        to_cat: str,
        asset: str,
        amount: float,
        from_info: Mapping[str, Any],
        to_info: Mapping[str, Any],
    ) -> TransferPlan:
        """Universal routing logic - works for every one of the 70+ venues.

        The decision tree is driven entirely by:

          * ``from_cat`` / ``to_cat`` (crypto, crypto_deriv, prediction,
            equity_broker, forex, on_chain, bank, charting, data)
          * ``from_info["ai_fund_in/out"]`` and ``to_info[...]`` from the
            canonical :data:`VENUE_FUNDING` map.

        Everything past that is narration. No venue is hardcoded beyond
        the fixed-position roles (bank, kingdom_wallet).
        """
        warnings: List[str] = []
        f_venue, t_venue = intent.from_venue or "", intent.to_venue or ""

        # Normalize category groupings used by the decision tree.
        CRYPTO_CATS = {"crypto", "crypto_deriv", "prediction", "on_chain"}
        BROKER_CATS = {"equity_broker", "forex"}

        # -----------------------------------------------------------------
        # 0) Same-venue move (buy/sell/swap happens at the venue, not here)
        if f_venue and f_venue == t_venue:
            plan.legs.append(PlanLeg(
                LegType.INFO, f_venue, asset, amount,
                note=(
                    f"Source and destination are both {f_venue}. "
                    "No cross-venue transfer needed - use the venue's own "
                    "trade/convert function."
                ),
            ))
            plan.status = PlanStatus.READY
            plan.warnings = warnings
            return plan

        # -----------------------------------------------------------------
        # 1) EQUITY/FX BROKER -> anywhere (sell-then-ACH chain)
        if from_cat in BROKER_CATS:
            # Oanda-class forex brokers don't expose withdrawal APIs.
            if not from_info.get("ai_fund_out", False):
                plan.legs.append(PlanLeg(
                    LegType.MANUAL, f_venue, "USD", amount,
                    note=(
                        f"{f_venue} does not expose a withdrawal API. "
                        "Use the venue portal to move funds to your linked bank."
                    ),
                    details={"primary_rail": from_info.get("primary_rail")},
                ))
                plan.status = PlanStatus.PARTIAL
                warnings.append(f"{f_venue} requires manual portal action.")
                plan.warnings = warnings
                return plan

            # Sell leg - only if the user named a non-cash ticker.
            if asset not in ("USD", "USDC", "USDT", "DAI"):
                plan.legs.append(PlanLeg(
                    LegType.SELL, f_venue, asset, amount,
                    note=f"Sell {asset} position on {f_venue}",
                ))
            plan.legs.append(PlanLeg(
                LegType.ACH_OUT, f_venue, "USD", amount,
                note=f"ACH withdraw USD from {f_venue} to linked bank",
            ))

            if to_cat == "bank":
                plan.status = PlanStatus.READY
            elif to_cat in BROKER_CATS:
                if to_info.get("ai_fund_in", False):
                    plan.legs.append(PlanLeg(
                        LegType.ACH_IN, t_venue, "USD", amount,
                        note=f"ACH deposit USD into {t_venue}",
                    ))
                    plan.status = PlanStatus.READY
                else:
                    plan.legs.append(PlanLeg(
                        LegType.MANUAL, t_venue, "USD", amount,
                        note=(
                            f"Fund {t_venue} via the venue portal "
                            f"({to_info.get('primary_rail','manual_portal')})."
                        ),
                    ))
                    plan.status = PlanStatus.PARTIAL
            elif to_cat in CRYPTO_CATS:
                # Bank -> (CEX that accepts USD ACH) -> swap USD to USDC ->
                # send on-chain to the final destination.
                if to_cat == "crypto" and to_info.get("ai_fund_in", False):
                    # Destination IS a crypto CEX that the user can link a
                    # bank to; ACH lands there directly.
                    plan.legs.append(PlanLeg(
                        LegType.MANUAL, "bank", "USD", amount,
                        note=f"User action: ACH from bank to {t_venue}",
                    ))
                    plan.legs.append(PlanLeg(
                        LegType.BUY, t_venue, "USDC", amount,
                        note=f"Swap USD -> USDC on {t_venue}",
                    ))
                    plan.status = PlanStatus.PARTIAL
                else:
                    # on_chain or prediction with no ACH rail: use any
                    # US-friendly CEX as an intermediate staging venue.
                    plan.legs.append(PlanLeg(
                        LegType.MANUAL, "bank", "USD", amount,
                        note=(
                            "User action: ACH from bank to a US-friendly crypto "
                            "CEX (coinbase / kraken / gemini / bitstamp)."
                        ),
                    ))
                    plan.legs.append(PlanLeg(
                        LegType.BUY, "coinbase", "USDC", amount,
                        note="Swap USD -> USDC on the staging CEX",
                    ))
                    plan.legs.append(PlanLeg(
                        LegType.CRYPTO_TRANSFER, "coinbase", "USDC", amount,
                        note=f"Withdraw USDC from staging CEX to {t_venue}",
                        details={"to_venue": t_venue},
                    ))
                    plan.status = PlanStatus.PARTIAL
                warnings.append(
                    f"{from_cat} -> {to_cat} requires a manual bank hop (ACH)."
                )
            else:
                plan.legs.append(PlanLeg(
                    LegType.INFO, t_venue, asset, amount,
                    note=f"No supported rail for {from_cat} -> {to_cat}.",
                ))
                plan.status = PlanStatus.REJECTED

            plan.warnings = warnings
            return plan

        # -----------------------------------------------------------------
        # 2) BANK -> {broker, crypto, on_chain, prediction}
        if from_cat == "bank":
            if to_cat in BROKER_CATS:
                if to_info.get("ai_fund_in", False):
                    plan.legs.append(PlanLeg(
                        LegType.ACH_IN, t_venue, "USD", amount,
                        note=f"Plaid-assisted ACH pull into {t_venue}",
                    ))
                    plan.status = PlanStatus.READY
                else:
                    plan.legs.append(PlanLeg(
                        LegType.MANUAL, t_venue, "USD", amount,
                        note=(
                            f"Fund {t_venue} via the venue portal "
                            f"({to_info.get('primary_rail','manual_portal')})."
                        ),
                    ))
                    plan.status = PlanStatus.PARTIAL
            elif to_cat in CRYPTO_CATS:
                plan.legs.append(PlanLeg(
                    LegType.MANUAL, t_venue, "USD", amount,
                    note=(
                        f"Fund {t_venue} via ACH / wire / card on the "
                        f"venue portal ({to_info.get('primary_rail','manual_portal')})."
                    ),
                ))
                plan.status = PlanStatus.PARTIAL
            else:
                plan.legs.append(PlanLeg(
                    LegType.INFO, t_venue, asset, amount,
                    note=f"No supported rail for bank -> {to_cat}.",
                ))
                plan.status = PlanStatus.REJECTED
            plan.warnings = warnings
            return plan

        # -----------------------------------------------------------------
        # 3) CRYPTO / ON-CHAIN / PREDICTION -> anywhere
        if from_cat in CRYPTO_CATS:
            # 3a) crypto -> bank: only via a broker ACH (not supported directly)
            if to_cat == "bank":
                plan.legs.append(PlanLeg(
                    LegType.INFO, f_venue, asset, amount,
                    note=(
                        f"Direct {f_venue} -> bank is not a native rail. "
                        "Sell to USD on a CEX with fiat rails "
                        "(coinbase/kraken/gemini/bitstamp) then ACH out."
                    ),
                ))
                plan.legs.append(PlanLeg(
                    LegType.CRYPTO_TRANSFER, f_venue, asset, amount,
                    note=f"Transfer {asset} from {f_venue} to a fiat-capable CEX",
                    details={"to_venue": "coinbase"},
                ))
                plan.legs.append(PlanLeg(
                    LegType.SELL, "coinbase", asset, amount,
                    note=f"Sell {asset} -> USD on staging CEX",
                ))
                plan.legs.append(PlanLeg(
                    LegType.ACH_OUT, "coinbase", "USD", amount,
                    note="ACH USD from staging CEX to linked bank",
                ))
                plan.status = PlanStatus.PARTIAL
                warnings.append(
                    "Crypto -> bank requires a sell-then-ACH staging CEX."
                )

            # 3b) crypto -> broker: only specific brokers accept inbound crypto
            elif to_cat in BROKER_CATS:
                if to_info.get("ai_fund_in", False):
                    # e.g. Alpaca crypto wallet, or any broker with
                    # ai_fund_in==True in VENUE_FUNDING
                    plan.legs.append(PlanLeg(
                        LegType.CRYPTO_TRANSFER, f_venue, asset, amount,
                        note=(
                            f"Send {asset} from {f_venue} to "
                            f"{t_venue} crypto-deposit address"
                        ),
                        details={"to_venue": t_venue},
                    ))
                    plan.status = PlanStatus.READY
                else:
                    plan.legs.append(PlanLeg(
                        LegType.INFO, t_venue, asset, amount,
                        note=(
                            f"{t_venue} does not accept direct crypto funding "
                            f"(primary rail: {to_info.get('primary_rail','manual_portal')}). "
                            "Route via: CEX -> sell to USD -> ACH -> broker."
                        ),
                    ))
                    plan.status = PlanStatus.REJECTED
                    warnings.append(
                        f"Direct crypto -> {t_venue} is not legally possible."
                    )

            # 3c) crypto -> crypto (includes CEX<->CEX, CEX<->on_chain,
            #     CEX<->prediction, on_chain<->prediction)
            elif to_cat in CRYPTO_CATS:
                src_ok = f_venue.startswith("kingdom_wallet") or \
                    from_info.get("ai_fund_out", False)
                dst_ok = t_venue.startswith("kingdom_wallet") or \
                    to_info.get("ai_fund_in", False)

                if src_ok and dst_ok:
                    plan.legs.append(PlanLeg(
                        LegType.CRYPTO_TRANSFER, f_venue, asset, amount,
                        note=f"Move {asset} from {f_venue} to {t_venue}",
                        details={"to_venue": t_venue},
                    ))
                    plan.status = PlanStatus.READY
                elif not src_ok:
                    plan.legs.append(PlanLeg(
                        LegType.INFO, f_venue, asset, amount,
                        note=(
                            f"{f_venue} does not expose an outbound transfer "
                            f"API (primary rail: {from_info.get('primary_rail','unknown')}). "
                            "Use the venue portal to withdraw, then run the "
                            "incoming half of the transfer."
                        ),
                    ))
                    plan.status = PlanStatus.PARTIAL
                    warnings.append(f"{f_venue} lacks outbound API - manual required.")
                else:
                    plan.legs.append(PlanLeg(
                        LegType.INFO, t_venue, asset, amount,
                        note=(
                            f"{t_venue} does not expose an inbound transfer "
                            f"API (primary rail: {to_info.get('primary_rail','unknown')}). "
                            "User must fund it via portal."
                        ),
                    ))
                    plan.status = PlanStatus.PARTIAL
                    warnings.append(f"{t_venue} lacks inbound API - manual required.")

            # 3d) crypto -> charting/data/other - rejected
            else:
                plan.legs.append(PlanLeg(
                    LegType.INFO, t_venue, asset, amount,
                    note=f"{t_venue} is category={to_cat}; not a fundable venue.",
                ))
                plan.status = PlanStatus.REJECTED

            plan.warnings = warnings
            return plan

        # -----------------------------------------------------------------
        # 4) Unknown category fall-through - reject with context.
        plan.legs.append(PlanLeg(
            LegType.INFO, f_venue or "?", asset, amount,
            note=(
                f"No rail found for {from_cat} -> {to_cat}. "
                "Both venues must exist in VENUE_FUNDING with a known category."
            ),
        ))
        plan.status = PlanStatus.REJECTED
        plan.warnings = warnings
        return plan

    # ------------------------------------------------------------------
    def _narrate(self, plan: TransferPlan) -> str:
        if plan.status == PlanStatus.REJECTED:
            return (
                f"[rejected] {plan.intent.raw_text} - "
                + (plan.legs[0].note if plan.legs else "no legal route")
            )
        parts: List[str] = []
        for i, leg in enumerate(plan.legs, start=1):
            amt = f"{leg.amount:g}" if leg.amount else "(resolved at exec)"
            parts.append(f"  [{i}] {leg.leg_type.value}: {leg.note} (amount={amt})")
        tail = ""
        if plan.warnings:
            tail = "\n  warnings: " + "; ".join(plan.warnings)
        return (
            f"Plan {plan.plan_id} for: {plan.intent.raw_text}\n"
            + "\n".join(parts)
            + tail
        )

    # ------------------------------------------------------------------
    async def execute(
        self,
        plan_or_text,
        *,
        dry_run: bool = True,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Execute a plan (or build+execute from raw text).

        The first call will always build the plan and return
        ``status=needs_confirmation`` unless ``confirmed=True``. The
        second call (with the same plan or ``confirmed=True``) actually
        runs each leg.
        """
        if isinstance(plan_or_text, TransferPlan):
            plan = plan_or_text
        else:
            plan = self.build_plan(plan_or_text)

        if plan.status == PlanStatus.REJECTED:
            return {
                "ok": False,
                "plan": plan.to_dict(),
                "message": plan.narrative,
            }

        if not confirmed:
            return {
                "ok": True,
                "needs_confirmation": True,
                "plan": plan.to_dict(),
                "message": (
                    plan.narrative
                    + "\n\nReply 'confirm' to execute."
                ),
            }

        results: List[Dict[str, Any]] = []
        for leg in plan.legs:
            results.append(await self._execute_leg(leg, plan.intent, dry_run))

        outcome = {
            "ok": all(r.get("ok", False) or r.get("status") == "dry_run"
                      for r in results),
            "plan": plan.to_dict(),
            "leg_results": results,
            "dry_run": dry_run,
        }

        # Broadcast
        if self.event_bus is not None:
            try:
                self.event_bus.publish("transfer.nl.executed", outcome)
            except Exception as exc:  # noqa: BLE001
                logger.debug("event publish failed: %s", exc)

        return outcome

    # ------------------------------------------------------------------
    async def _execute_leg(
        self,
        leg: PlanLeg,
        intent: IntentParseResult,
        dry_run: bool,
    ) -> Dict[str, Any]:
        try:
            if leg.leg_type == LegType.CRYPTO_TRANSFER:
                if self.cross_venue_manager is None:
                    return {"ok": False, "leg": leg.to_dict(),
                            "error": "CrossVenueTransferManager not wired"}
                dst = leg.details.get("to_venue") or intent.to_venue
                # Amount "all"/"percent" resolution happens here - if caller
                # wants we can query balances, but for now dry-run surfaces
                # the symbolic amount.
                result = await self.cross_venue_manager.transfer(
                    from_venue=leg.venue,
                    to_venue=dst,
                    asset=leg.asset,
                    amount=float(leg.amount or 0.0),
                    dry_run=dry_run,
                )
                return {"ok": True, "leg": leg.to_dict(),
                        "result": result.to_dict() if hasattr(result, "to_dict") else result}

            if leg.leg_type == LegType.SELL:
                if self.real_stock_executor is None:
                    return {"ok": False, "leg": leg.to_dict(),
                            "error": "RealStockExecutor not wired"}
                if dry_run:
                    return {"ok": True, "leg": leg.to_dict(),
                            "status": "dry_run",
                            "note": f"Would sell {leg.amount} of {leg.asset}"}
                # Real sell path
                place = getattr(self.real_stock_executor, "place_alpaca_order", None)
                if place is None:
                    return {"ok": False, "leg": leg.to_dict(),
                            "error": "place_alpaca_order not available"}
                res = await place(symbol=leg.asset, qty=float(leg.amount), side="sell")
                return {"ok": True, "leg": leg.to_dict(), "result": res}

            if leg.leg_type == LegType.BUY:
                if self.real_stock_executor is None:
                    return {"ok": False, "leg": leg.to_dict(),
                            "error": "RealStockExecutor not wired"}
                if dry_run:
                    return {"ok": True, "leg": leg.to_dict(),
                            "status": "dry_run",
                            "note": f"Would buy {leg.amount} of {leg.asset}"}
                place = getattr(self.real_stock_executor, "place_alpaca_order", None)
                if place is None:
                    return {"ok": False, "leg": leg.to_dict(),
                            "error": "place_alpaca_order not available"}
                res = await place(symbol=leg.asset, qty=float(leg.amount), side="buy")
                return {"ok": True, "leg": leg.to_dict(), "result": res}

            if leg.leg_type == LegType.ACH_OUT:
                if self.cross_venue_manager is None:
                    return {"ok": False, "leg": leg.to_dict(),
                            "error": "CrossVenueTransferManager not wired"}
                result = await self.cross_venue_manager.transfer(
                    from_venue=leg.venue,
                    to_venue="bank",
                    asset="USD",
                    amount=float(leg.amount or 0.0),
                    dry_run=dry_run,
                )
                return {"ok": True, "leg": leg.to_dict(),
                        "result": result.to_dict() if hasattr(result, "to_dict") else result}

            if leg.leg_type == LegType.ACH_IN:
                if self.cross_venue_manager is None:
                    return {"ok": False, "leg": leg.to_dict(),
                            "error": "CrossVenueTransferManager not wired"}
                result = await self.cross_venue_manager.transfer(
                    from_venue="bank",
                    to_venue=leg.venue,
                    asset="USD",
                    amount=float(leg.amount or 0.0),
                    dry_run=dry_run,
                )
                return {"ok": True, "leg": leg.to_dict(),
                        "result": result.to_dict() if hasattr(result, "to_dict") else result}

            if leg.leg_type == LegType.MANUAL:
                return {
                    "ok": True, "leg": leg.to_dict(),
                    "status": "manual_action_required",
                    "note": leg.note,
                    "portal_url": leg.details.get("portal_url"),
                }

            if leg.leg_type == LegType.INFO:
                return {"ok": False, "leg": leg.to_dict(),
                        "status": "rejected", "note": leg.note}

            return {"ok": False, "leg": leg.to_dict(),
                    "error": f"unhandled leg type {leg.leg_type}"}
        except Exception as exc:  # noqa: BLE001
            logger.exception("leg execution failed")
            return {"ok": False, "leg": leg.to_dict(), "error": str(exc)}


__all__ = [
    "IntentParseResult",
    "PlanLeg",
    "PlanStatus",
    "TransferPlan",
    "LegType",
    "NaturalLanguageTransferRouter",
    "parse_intent",
    "VENUE_ALIASES",
]
