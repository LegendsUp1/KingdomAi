#!/usr/bin/env python3
# Market Definitions for Kingdom AI Trading System

from enum import Enum
from typing import Dict, List, Set, Optional, Any

class AssetClass(Enum):
    """Comprehensive enumeration of all major asset classes for trading."""
    CRYPTOCURRENCY = "cryptocurrency"
    STOCK = "stock"
    BOND = "bond"
    FOREX = "forex"
    COMMODITY = "commodity"
    OPTION = "option"
    FUTURE = "future"
    ETF = "etf"
    INDEX = "index"
    MUTUAL_FUND = "mutual_fund"
    REIT = "reit"
    PRECIOUS_METAL = "precious_metal"
    FIXED_INCOME = "fixed_income"
    DERIVATIVE = "derivative"
    SYNTHETIC = "synthetic"
    NFT = "nft"
    DEFI = "defi"
    OTHER = "other"

class MarketType(Enum):
    """Types of markets where trading occurs."""
    SPOT = "spot"
    MARGIN = "margin"
    FUTURES = "futures"
    OPTIONS = "options"
    PERPETUAL = "perpetual"
    DEFI_AMM = "defi_amm"
    DEFI_ORDERBOOK = "defi_orderbook"
    DARK_POOL = "dark_pool"
    OTC = "otc"
    IPO = "ipo"
    SECONDARY = "secondary"
    PRIMARY_BOND = "primary_bond"
    SECONDARY_BOND = "secondary_bond"
    REPO = "repo"
    MONEY_MARKET = "money_market"

# Exchange Capabilities
EXCHANGE_CAPABILITIES = {
    "binance": {"spot": True, "futures": True, "margin": True, "lending": True},
    "coinbase": {"spot": True, "futures": False, "margin": False, "lending": False},
    "kraken": {"spot": True, "futures": True, "margin": True, "lending": True},
    "bybit": {"spot": True, "futures": True, "margin": True, "lending": False},
}

class OrderType(Enum):
    """Comprehensive list of order types across all markets."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    FILL_OR_KILL = "fill_or_kill"
    ICEBERG = "iceberg"
    MARKET_ON_CLOSE = "market_on_close"
    LIMIT_ON_CLOSE = "limit_on_close"
    GOOD_TILL_CANCELLED = "good_till_cancelled"
    IMMEDIATE_OR_CANCEL = "immediate_or_cancel"
    POST_ONLY = "post_only"
    AUCTION = "auction"
    PEGGED = "pegged"
    RESERVE = "reserve"
    BRACKET = "bracket"
    OCO = "one_cancels_other"
    TWAP = "time_weighted_average_price"
    VWAP = "volume_weighted_average_price"

class OrderSide(Enum):
    """Sides of a trade."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"

class TimeInForce(Enum):
    """Time in force options for orders."""
    GTC = "good_till_cancelled"
    IOC = "immediate_or_cancel"
    FOK = "fill_or_kill"
    DAY = "day"
    GTD = "good_till_date"
    AT_THE_OPEN = "at_the_open"
    AT_THE_CLOSE = "at_the_close"

class ExchangeType(Enum):
    """Types of exchanges where trading occurs."""
    CENTRALIZED_CRYPTO = "centralized_crypto"
    DECENTRALIZED_CRYPTO = "decentralized_crypto"
    STOCK_EXCHANGE = "stock_exchange"
    OPTIONS_EXCHANGE = "options_exchange"
    FUTURES_EXCHANGE = "futures_exchange"
    FOREX_ECN = "forex_ecn"
    FOREX_MARKET_MAKER = "forex_market_maker"
    COMMODITY_EXCHANGE = "commodity_exchange"
    BOND_MARKET = "bond_market"
    DARK_POOL = "dark_pool"
    OTC_MARKET = "otc_market"
    ATS = "alternative_trading_system"
    MTF = "multilateral_trading_facility"
    SWF = "systematic_internaliser"

class ExchangeInfo:
    """Information about a specific exchange."""
    
    def __init__(self, 
                 name: str,
                 exchange_type: ExchangeType,
                 supported_asset_classes: List[AssetClass],
                 supported_market_types: List[MarketType],
                 supported_order_types: List[OrderType],
                 base_url: Optional[str] = None,
                 api_version: Optional[str] = None,
                 requires_api_key: bool = True,
                 websocket_supported: bool = False,
                 websocket_url: Optional[str] = None,
                 has_sandbox: bool = False,
                 sandbox_url: Optional[str] = None,
                 countries_supported: Optional[List[str]] = None,
                 rate_limits: Optional[Dict[str, Any]] = None):
        self.name = name
        self.exchange_type = exchange_type
        self.supported_asset_classes = supported_asset_classes
        self.supported_market_types = supported_market_types
        self.supported_order_types = supported_order_types
        self.base_url = base_url
        self.api_version = api_version
        self.requires_api_key = requires_api_key
        self.websocket_supported = websocket_supported
        self.websocket_url = websocket_url
        self.has_sandbox = has_sandbox
        self.sandbox_url = sandbox_url
        self.countries_supported = countries_supported or []
        self.rate_limits = rate_limits or {}
        self.symbols: Dict[str, Dict[str, Any]] = {}

class MarketRegistry:
    """Registry of all supported markets and exchanges."""
    
    def __init__(self):
        self.exchanges: Dict[str, ExchangeInfo] = {}
        self.asset_classes: Set[AssetClass] = set()
        self.market_types: Set[MarketType] = set()
        
    def register_exchange(self, exchange_info: ExchangeInfo) -> None:
        """Register a new exchange."""
        self.exchanges[exchange_info.name] = exchange_info
        for asset_class in exchange_info.supported_asset_classes:
            self.asset_classes.add(asset_class)
        for market_type in exchange_info.supported_market_types:
            self.market_types.add(market_type)
            
    def get_exchange(self, name: str) -> Optional[ExchangeInfo]:
        """Get exchange by name."""
        return self.exchanges.get(name)
    
    def get_exchanges_for_asset_class(self, asset_class: AssetClass) -> List[ExchangeInfo]:
        """Get all exchanges supporting a specific asset class."""
        return [exchange for exchange in self.exchanges.values() 
                if asset_class in exchange.supported_asset_classes]
    
    def get_exchanges_for_market_type(self, market_type: MarketType) -> List[ExchangeInfo]:
        """Get all exchanges supporting a specific market type."""
        return [exchange for exchange in self.exchanges.values() 
                if market_type in exchange.supported_market_types]
                
    def is_symbol_supported(self, exchange: str, symbol: str) -> bool:
        """Check if a symbol is supported on an exchange."""
        exchange_info = self.get_exchange(exchange)
        if not exchange_info:
            return False
        return symbol in exchange_info.symbols
        
    def get_market_info(self, exchange: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get market info for a symbol on an exchange."""
        exchange_info = self.get_exchange(exchange)
        if not exchange_info:
            return None
        return exchange_info.symbols.get(symbol)
        
    def detect_asset_class(self, symbol: str) -> AssetClass:
        """Detect asset class from symbol format."""
        if '/' in symbol:
            if symbol.endswith('/USD') or symbol.endswith('/USDT') or symbol.endswith('/BTC'):
                return AssetClass.CRYPTOCURRENCY
            else:
                return AssetClass.FOREX
        elif symbol.startswith('BTC') or symbol.startswith('ETH'):
            return AssetClass.CRYPTOCURRENCY
        elif '.' in symbol:
            # Stock with exchange prefix like 'NYSE:AAPL' or 'AAPL.US'
            return AssetClass.STOCK
        elif symbol.endswith('Z') or symbol.endswith('F'):
            # Futures contract
            return AssetClass.FUTURE
        elif len(symbol) <= 5:
            # Most stock tickers are 5 or fewer characters
            return AssetClass.STOCK
        else:
            # Default assumption
            return AssetClass.OTHER

    def get_available_markets(self) -> Dict[str, List[str]]:
        """Get all available markets grouped by exchange."""
        result = {}
        for exchange_name, exchange_info in self.exchanges.items():
            result[exchange_name] = list(exchange_info.symbols.keys())
        return result

# Initialize global market registry
market_registry = MarketRegistry()
