"""Autonomous trading: seven modules + orchestration (additive, config-gated)."""

from .autonomous_orchestrator import AutonomousOrchestrator
from .data_feeds import DataFeedManager
from .execution_engine import ExecutionEngine
from .risk_manager import AutonomousRiskManager
from .module_1_portfolio_hedging import PortfolioHedgingModule
from .module_2_institutional_positioning import InstitutionalPositioningModule
from .module_3_dividend_radar import DividendRadarModule
from .module_4_correlation_map import CorrelationMapModule
from .module_5_sentiment_arbitrage import SentimentArbitrageModule
from .module_6_macro_analysis import MacroAnalysisModule
from .module_7_short_squeeze import ShortSqueezeModule

__all__ = [
    "AutonomousOrchestrator",
    "DataFeedManager",
    "ExecutionEngine",
    "AutonomousRiskManager",
    "PortfolioHedgingModule",
    "InstitutionalPositioningModule",
    "DividendRadarModule",
    "CorrelationMapModule",
    "SentimentArbitrageModule",
    "MacroAnalysisModule",
    "ShortSqueezeModule",
]
