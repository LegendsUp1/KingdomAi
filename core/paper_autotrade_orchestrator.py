import asyncio
import logging
import time
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from core.base_component_v2 import BaseComponentV2


class PaperAutotradeOrchestrator(BaseComponentV2):
    """Simulate Thoth/Ollama auto-trading and emit readiness/metrics.

    This component sits alongside the real TradingComponent and
    AdvancedRiskManager. It does **not** execute live orders. Instead it:

    - Listens to Thoth's auto-trading signals:
        * ``trading.signal`` (crypto/FX)
        * ``stock.order_submit`` (stocks)
    - Tracks a synthetic paper portfolio and equity curve in Redis.
    - Consumes live pricing and risk snapshots:
        * ``trading.live_prices``
        * ``trading.portfolio.snapshot``
        * ``trading.risk.snapshot``
    - Periodically publishes:
        * ``autotrade.paper.metrics`` – performance metrics for the
          paper account (win-rate, drawdown, PnL, etc.).
        * ``autotrade.readiness`` – a coarse readiness state:
          ``WARMUP``, ``LEARNING``, ``READY``, or ``FAILED``.

    The readiness state is intended to gate **live** auto-trading in the
    GUI. TradingTab should only enable live AI auto-trade controls when
    ``state == "READY"`` for safety.
    """

    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="PaperAutotradeOrchestrator", event_bus=event_bus, config=config or {})
        self.logger = logging.getLogger("kingdom_ai.PaperAutotradeOrchestrator")

        # Study / learning window configuration (seconds)
        # Default is no fixed time gate: readiness now follows full-analysis readiness.
        self.study_duration_seconds: float = float(self.config.get("study_duration_seconds", 0.0))
        self.min_warmup_seconds: float = float(self.config.get("min_warmup_seconds", 0.0))
        self.min_trades_for_readiness: int = int(self.config.get("min_trades_for_readiness", 0))
        # Aim for extremely high win rate on paper before reporting READY.
        self.target_win_rate: float = float(self.config.get("target_win_rate", 0.95))
        self.max_allowed_drawdown: float = float(self.config.get("max_allowed_drawdown", 10.0))  # 10%

        # Paper portfolio state
        self._last_live_prices: Dict[str, float] = {}
        self._paper_positions: Dict[str, Dict[str, Any]] = {}
        self._closed_trades: List[Dict[str, Any]] = []

        # Aggregate metrics
        self._equity: float = 0.0
        self._equity_peak: float = 0.0
        self._equity_min: float = 0.0
        self._wins: int = 0
        self._losses: int = 0
        self._gross_profit: float = 0.0
        self._gross_loss: float = 0.0

        # Global trade-level PnL series so downstream learning components can
        # compute CVaR, Kelly-style sizing, Wilson intervals, and other
        # profit-focused statistics over the paper account.
        self._global_pnl_series: List[float] = []
        self._pnl_series_max_length: int = int(self.config.get("pnl_series_max_length", 5000))

        # Per-strategy performance buckets so Thoth/Ollama and the UI can see
        # which styles (trend, mean-reversion, arbitrage, etc.) are working.
        # Keys are strategy_style strings, values are small stats dicts.
        self._strategy_stats: Dict[str, Dict[str, Any]] = {}

        # Study window
        self._study_start_ts: float = time.time()
        self._last_metrics_emit_ts: float = 0.0
        self._metrics_emit_interval: float = 30.0  # seconds

        # Readiness state
        self._readiness_state: str = "WARMUP"
        self._readiness_reason: str = "Study window just started"
        self._analysis_ready: bool = bool(self.config.get("analysis_ready", False))
        self._analysis_ready_reason: str = "Waiting for full analysis readiness signal"

    async def _initialize(self) -> None:
        """Initialize Redis state if needed."""
        try:
            if not await self._init_redis():
                self.logger.error("PaperAutotradeOrchestrator failed to initialize Redis")
                await self._shutdown_on_redis_failure()
                return

            # Try to restore prior study state from Redis (best-effort).
            await self._load_state_from_redis()

            self.logger.info(
                "PaperAutotradeOrchestrator initialized – study_duration=%.0fs, min_trades=%d, target_win_rate=%.1f%%",
                self.study_duration_seconds,
                self.min_trades_for_readiness,
                self.target_win_rate * 100.0,
            )
        except Exception as e:
            self._handle_error("Error during PaperAutotradeOrchestrator initialization", e)

    async def _register_event_handlers(self) -> None:
        """Subscribe to trading and risk topics on the EventBus."""
        await self.subscribe("trading.live_prices", self._on_live_prices)
        await self.subscribe("trading.signal", self._on_trading_signal)
        await self.subscribe("stock.order_submit", self._on_stock_order_submit)
        await self.subscribe("trading.portfolio.snapshot", self._on_portfolio_snapshot)
        await self.subscribe("trading.risk.snapshot", self._on_risk_snapshot)
        await self.subscribe("autotrade.paper.reset", self._on_reset_request)
        await self.subscribe("autotrade.paper.configure", self._on_configure_request)
        await self.subscribe("ai.autotrade.analysis.ready", self._on_analysis_ready_signal)
        await self.subscribe("trading.analysis.ready", self._on_analysis_ready_signal)

    async def _start(self) -> None:
        """Optional hook for future background tasks."""
        # No dedicated background loop yet; metrics are updated on events.
        return

    async def _on_live_prices(self, payload: Dict[str, Any]) -> None:
        """Handle streaming live prices from TradingComponent.

        Payload shape (from TradingComponent._process_market_data):
            {
                "timestamp": float,
                "prices": {
                    "BTC": {"symbol": "BTC/USD", "price": 42000.0, ...},
                    ...
                }
            }
        """
        try:
            prices = payload.get("prices", {})
            if not isinstance(prices, dict):
                return

            for base, info in prices.items():
                if not isinstance(info, dict):
                    continue
                sym = info.get("symbol")
                p = info.get("price")
                if not sym or not isinstance(p, (int, float)):
                    continue
                try:
                    price_f = float(p)
                except (TypeError, ValueError):
                    continue
                if price_f <= 0.0:
                    continue
                self._last_live_prices[str(sym)] = price_f

            # Mark-to-market any open paper positions
            self._mark_to_market()
            await self._maybe_emit_metrics()
        except Exception as e:
            self._handle_error("Error in _on_live_prices", e)

    async def _on_trading_signal(self, signal: Dict[str, Any]) -> None:
        """Handle crypto/FX auto-trade signals (paper only).

        Expected payload from ThothLiveIntegration._crypto_autotrade_loop:
            {
                "symbol": "BTC/USDT",
                "signal_type": "buy" | "sell",
                "quantity": float,
                "price": Optional[float],
                "source": "thoth_ai",
                ...
            }
        """
        try:
            symbol = str(signal.get("symbol") or "").upper()
            side = str(signal.get("signal_type") or "").lower()
            if not symbol or side not in ("buy", "sell", "long", "short"):
                return

            qty_raw = signal.get("quantity", 0.0)
            try:
                quantity = float(qty_raw or 0.0)
            except (TypeError, ValueError):
                quantity = 0.0
            if quantity <= 0.0:
                return

            price_val = signal.get("price")
            entry_price = self._resolve_price(symbol, price_val)
            if entry_price is None or entry_price <= 0.0:
                return

            strategy_style = self._infer_strategy_style(signal, asset_class="crypto")
            direction = "long" if side in ("buy", "long") else "short"
            self._apply_paper_trade(symbol, direction, quantity, entry_price, strategy_style=strategy_style)
            await self._maybe_emit_metrics()
        except Exception as e:
            self._handle_error("Error in _on_trading_signal", e)

    async def _on_stock_order_submit(self, order: Dict[str, Any]) -> None:
        """Handle stock auto-trade proposals (paper only).

        Expected payload from ThothLiveIntegration._stocks_autotrade_loop:
            {
                "symbol": "AAPL",
                "side": "buy" | "sell",
                "type": "market" | "limit",
                "quantity": float,
                "price": Optional[float],
                ...
            }
        """
        try:
            symbol = str(order.get("symbol") or "").upper()
            side = str(order.get("side") or "").lower()
            if not symbol or side not in ("buy", "sell"):
                return

            try:
                quantity = float(order.get("quantity", 0.0) or 0.0)
            except (TypeError, ValueError):
                quantity = 0.0
            if quantity <= 0.0:
                return

            price_val = order.get("price")
            entry_price = self._resolve_price(symbol, price_val)
            if entry_price is None or entry_price <= 0.0:
                return

            strategy_style = self._infer_strategy_style(order, asset_class="stocks")
            direction = "long" if side == "buy" else "short"
            self._apply_paper_trade(symbol, direction, quantity, entry_price, strategy_style=strategy_style)
            await self._maybe_emit_metrics()
        except Exception as e:
            self._handle_error("Error in _on_stock_order_submit", e)

    async def _on_portfolio_snapshot(self, payload: Dict[str, Any]) -> None:
        """Consume real portfolio snapshot for context only.

        We do **not** alter paper equity based on real balances; this data is
        used purely for Thoth/Ollama context and potential future extensions
        (e.g. scaling paper account size to real portfolio value).
        """
        try:
            # Optionally sync initial equity to real portfolio value
            total_value = payload.get("total_value") or None
            if isinstance(total_value, (int, float)) and self._equity == 0.0:
                try:
                    eq = float(total_value)
                    if eq > 0.0:
                        self._equity = eq
                        self._equity_peak = eq
                        self._equity_min = eq
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            self._handle_error("Error in _on_portfolio_snapshot", e)

    async def _on_risk_snapshot(self, payload: Dict[str, Any]) -> None:
        """Consume real risk snapshot for context only.

        Future work: incorporate drawdown / leverage limits from real
        portfolio directly into readiness logic.
        """
        try:
            # Currently no-op except for potential logging
            _ = payload
        except Exception as e:
            self._handle_error("Error in _on_risk_snapshot", e)

    async def _on_reset_request(self, payload: Dict[str, Any]) -> None:
        """Handle external request to reset the paper study window."""
        try:
            self.logger.info("Resetting PaperAutotradeOrchestrator study window: %s", payload)
            # Archive before reset so no learning/trade history is lost.
            archive = {
                "timestamp": time.time(),
                "reason": payload,
                "paper_positions": self._paper_positions,
                "closed_trades": self._closed_trades,
                "equity": self._equity,
                "equity_peak": self._equity_peak,
                "equity_min": self._equity_min,
                "wins": self._wins,
                "losses": self._losses,
            }
            archive_path = Path("data/autotrade/paper_reset_archive.jsonl")
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            with archive_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(archive, ensure_ascii=True) + "\n")
            self._study_start_ts = time.time()
            self._paper_positions.clear()
            self._closed_trades.clear()
            self._equity = 0.0
            self._equity_peak = 0.0
            self._equity_min = 0.0
            self._wins = 0
            self._losses = 0
            self._gross_profit = 0.0
            self._gross_loss = 0.0
            self._readiness_state = "WARMUP"
            self._readiness_reason = "Study window reset"

            await self._persist_state_to_redis()
            await self._emit_metrics()
            await self._emit_readiness()
        except Exception as e:
            self._handle_error("Error in _on_reset_request", e)

    async def _on_configure_request(self, payload: Dict[str, Any]) -> None:
        """Handle runtime configuration updates.

        Example payload:
            {
                "study_duration_seconds": 3600,
                "min_trades_for_readiness": 50,
                "target_win_rate": 0.9,
                "max_allowed_drawdown": 5.0,
            }
        """
        try:
            if not isinstance(payload, Dict):
                return

            if "study_duration_seconds" in payload:
                try:
                    self.study_duration_seconds = float(payload["study_duration_seconds"])
                except (TypeError, ValueError):
                    pass
            if "analysis_ready" in payload:
                self._analysis_ready = bool(payload.get("analysis_ready"))
                self._analysis_ready_reason = str(
                    payload.get("analysis_ready_reason")
                    or ("Analysis marked ready by configuration" if self._analysis_ready else "Analysis readiness cleared by configuration")
                )
            if "min_trades_for_readiness" in payload:
                try:
                    self.min_trades_for_readiness = int(payload["min_trades_for_readiness"])
                except (TypeError, ValueError):
                    pass
            if "target_win_rate" in payload:
                try:
                    self.target_win_rate = float(payload["target_win_rate"])
                except (TypeError, ValueError):
                    pass
            if "max_allowed_drawdown" in payload:
                try:
                    self.max_allowed_drawdown = float(payload["max_allowed_drawdown"])
                except (TypeError, ValueError):
                    pass

            self.logger.info(
                "Updated paper autotrade config: duration=%.0fs, min_trades=%d, target_win_rate=%.1f%%, max_dd=%.1f%%",
                self.study_duration_seconds,
                self.min_trades_for_readiness,
                self.target_win_rate * 100.0,
                self.max_allowed_drawdown,
            )

            await self._persist_state_to_redis()
            await self._emit_readiness()
        except Exception as e:
            self._handle_error("Error in _on_configure_request", e)

    async def _on_analysis_ready_signal(self, payload: Dict[str, Any]) -> None:
        """Mark full-analysis readiness from upstream AI orchestration."""
        try:
            ready = True
            reason = "Full analysis completed"
            if isinstance(payload, dict):
                if "ready" in payload:
                    ready = bool(payload.get("ready"))
                reason = str(payload.get("reason") or reason)
            self._analysis_ready = ready
            self._analysis_ready_reason = reason
            await self._emit_readiness()
        except Exception as e:
            self._handle_error("Error in _on_analysis_ready_signal", e)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_price(self, symbol: str, explicit_price: Any) -> Optional[float]:
        """Resolve a reasonable entry/exit price for a given symbol."""
        # Prefer explicit price from signal/order
        if isinstance(explicit_price, (int, float)):
            try:
                p = float(explicit_price)
                if p > 0.0:
                    return p
            except (TypeError, ValueError):
                pass

        # Fallback to last live price for the full symbol or base asset
        sym_key = symbol.upper()
        if sym_key in self._last_live_prices:
            return self._last_live_prices[sym_key]

        # Try base asset key: e.g., BTC from BTC/USD
        if "/" in sym_key:
            base = sym_key.split("/")[0]
            if base and base in self._last_live_prices:
                return self._last_live_prices[base]

        return None

    def _canonicalize_strategy_style(self, raw_style: Any, asset_class: str) -> str:
        """Map raw strategy style hints into a small, canonical label set.

        This keeps per-strategy paper metrics and any downstream UI tables
        aligned with a consistent mental model (trend, mean_reversion,
        arbitrage, options_hedge, etc.), regardless of how upstream components
        spell or decorate the style name.
        """
        try:
            s = str(raw_style or "").strip()
        except Exception:
            s = ""

        asset = (asset_class or "").lower().strip()

        if not s:
            # Asset-class defaults when no explicit strategy metadata is
            # provided. We deliberately map these into coarse style buckets
            # (mostly trend-following) so metrics and tables aggregate cleanly.
            if asset in ("crypto", "fx", "forex", "derivatives"):
                base = "trend"
            elif asset in ("stocks", "equities", "equity", "etf"):
                base = "trend"
            else:
                base = "trend"
        else:
            s_norm = s.lower().replace("-", "_").replace(" ", "_")
            mapping = {
                # Core styles
                "trend": "trend",
                "trend_following": "trend",
                "trendfollowing": "trend",
                "momentum": "momentum",
                "momentum_trading": "momentum",
                "mean_reversion": "mean_reversion",
                "meanreversion": "mean_reversion",
                "mean_reverting": "mean_reversion",
                # Statistical arbitrage-style mean reversion
                "stat_arb": "mean_reversion",
                "stat_arbitrage": "mean_reversion",
                # Arbitrage families
                "arbitrage": "arbitrage",
                "cross_exchange_arbitrage": "arbitrage",
                "triangular_arbitrage": "arbitrage",
                # Pairs / relative-value trading
                "pairs": "pairs_trading",
                "pairs_trading": "pairs_trading",
                "pair_trading": "pairs_trading",
                "stat_pairs": "pairs_trading",
                # Grid & range trading
                "grid": "grid",
                "grid_trading": "grid",
                # Options / hedge styles
                "options_hedge": "options_hedge",
                "options_hedging": "options_hedge",
                "gamma_scalping": "options_hedge",
                "delta_hedge": "options_hedge",
                # Liquidity / market-making
                "liquidity_provision": "liquidity_provision",
                "liquidity_providing": "liquidity_provision",
                "market_making": "liquidity_provision",
                "market_maker": "liquidity_provision",
                # Other common labels
                "scalping": "scalping",
                "scalp": "scalping",
                "event_driven": "event_driven",
                "news_trading": "event_driven",
                "news": "event_driven",
                "carry": "carry",
                "carry_trade": "carry",
                "volatility": "volatility",
                "vol_targeting": "volatility",
                "volatility_arbitrage": "volatility",
                # Historical fallbacks used elsewhere in the stack
                "crypto_trend": "trend",
                "stocks_trend": "trend",
                "global_trend": "trend",
            }
            base = mapping.get(s_norm, s_norm)

        if not base:
            base = "other"
        return base

    def _infer_strategy_style(self, payload: Dict[str, Any], asset_class: str) -> str:
        """Infer a coarse, canonical strategy_style label for a signal/order.

        Logic:
        - Prefer explicit fields like strategy_style / strategy / style when
          provided by upstream Thoth/Ollama logic.
        - Otherwise fall back to asset-class defaults.
        - In all cases, pass the result through _canonicalize_strategy_style
          so that per-strategy telemetry is keyed by a small, stable set of
          labels (trend, mean_reversion, arbitrage, options_hedge, etc.).
        """
        try:
            style: Any = payload.get("strategy_style")  # type: ignore[assignment]
            if not style:
                style = payload.get("strategy") or payload.get("style")
        except Exception:
            style = None

        asset = (asset_class or "").lower()
        return self._canonicalize_strategy_style(style, asset)

    def _apply_paper_trade(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        strategy_style: Optional[str] = None,
    ) -> None:
        """Update paper positions and closed trades for a new signal.

        Simple model:
        - One net position per symbol (long or short).
        - When direction flips, we close the existing position at current
          price and open a new one.
        - PnL is realized immediately on close.
        """
        symbol = symbol.upper()
        pos = self._paper_positions.get(symbol)

        if pos is not None:
            prev_dir = pos.get("direction")
            prev_qty = float(pos.get("quantity", 0.0) or 0.0)
            entry_price = float(pos.get("entry_price", 0.0) or 0.0)
            prev_style = str(pos.get("strategy_style") or strategy_style or "unknown")

            if prev_dir in ("long", "short") and prev_qty > 0.0 and entry_price > 0.0:
                # Close existing position before potentially opening a new one
                pnl = self._compute_pnl(prev_dir, prev_qty, entry_price, price)
                trade = {
                    "symbol": symbol,
                    "direction": prev_dir,
                    "quantity": prev_qty,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "pnl": pnl,
                    "closed_ts": time.time(),
                    "strategy_style": prev_style,
                }
                self._closed_trades.append(trade)
                self._equity += pnl
                if pnl >= 0.0:
                    self._wins += 1
                    self._gross_profit += pnl
                else:
                    self._losses += 1
                    self._gross_loss += abs(pnl)

                # Record trade-level PnL for global statistics. We keep this
                # bounded so metrics payloads do not explode in size.
                try:
                    self._global_pnl_series.append(float(pnl))
                    if len(self._global_pnl_series) > self._pnl_series_max_length:
                        self._global_pnl_series = self._global_pnl_series[-self._pnl_series_max_length:]
                except Exception:
                    # PnL history is best-effort; never block core logic.
                    pass

                # Update per-strategy aggregates
                self._update_strategy_metrics(prev_style, pnl)

                # Emit a trade-level telemetry event so online RL and
                # higher-level analytics can learn directly from individual
                # outcomes while staying fully decoupled from live order
                # execution.
                try:
                    import asyncio

                    metrics_snapshot = {
                        "equity": self._equity,
                        "equity_peak": self._equity_peak,
                        "equity_min": self._equity_min,
                        "wins": self._wins,
                        "losses": self._losses,
                        "trade_count": len(self._closed_trades),
                        "gross_profit": self._gross_profit,
                        "gross_loss": self._gross_loss,
                    }

                    evt = dict(trade)
                    evt["metrics_snapshot"] = metrics_snapshot

                    # Fire-and-forget publish so we do not block core logic.
                    if asyncio.get_event_loop().is_running():
                        asyncio.create_task(
                            self.publish_event("autotrade.paper.trade_closed", evt)
                        )
                except Exception:
                    # Telemetry is best-effort; never block paper trading.
                    pass

        # Open/replace with new position
        self._paper_positions[symbol] = {
            "symbol": symbol,
            "direction": direction,
            "quantity": float(quantity),
            "entry_price": float(price),
            "open_ts": time.time(),
            "strategy_style": strategy_style or "unknown",
        }

        # Update equity extrema
        if self._equity_peak == 0.0 and self._equity == 0.0:
            self._equity_peak = 0.0
            self._equity_min = 0.0
        self._equity_peak = max(self._equity_peak, self._equity)
        self._equity_min = min(self._equity_min, self._equity)

    def _compute_pnl(self, direction: str, qty: float, entry: float, exit: float) -> float:
        if entry <= 0.0 or exit <= 0.0 or qty <= 0.0:
            return 0.0
        if direction == "long":
            return (exit - entry) * qty
        return (entry - exit) * qty

    def _mark_to_market(self) -> None:
        """Mark open positions to latest prices to keep equity curve sane."""
        eq = self._equity
        for symbol, pos in self._paper_positions.items():
            symbol_u = symbol.upper()
            price = self._resolve_price(symbol_u, None)
            if price is None or price <= 0.0:
                continue
            direction = str(pos.get("direction") or "").lower()
            qty = float(pos.get("quantity", 0.0) or 0.0)
            entry = float(pos.get("entry_price", 0.0) or 0.0)
            if qty <= 0.0 or entry <= 0.0:
                continue
            pnl = self._compute_pnl(direction, qty, entry, price)
            eq = self._equity + pnl

        self._equity_peak = max(self._equity_peak, eq)
        self._equity_min = min(self._equity_min, eq)

    def _update_strategy_metrics(self, style: str, pnl: float) -> None:
        """Update per-strategy aggregates for a closed trade.

        Stats tracked per strategy_style:
            - trade_count, wins, losses
            - gross_profit, gross_loss, net_profit
            - equity, equity_peak, equity_min (for drawdown)
        """
        try:
            # Normalize style into canonical label space so historical names
            # like "crypto_trend" and "stocks_trend" roll up under
            # consistent keys (e.g. "trend"). Asset class is unknown here,
            # but _canonicalize_strategy_style still folds most variants.
            key = self._canonicalize_strategy_style(style, "")
            stats = self._strategy_stats.get(key) or {
                "trade_count": 0,
                "wins": 0,
                "losses": 0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "equity": 0.0,
                "equity_peak": 0.0,
                "equity_min": 0.0,
                "pnl_series": [],
            }

            stats["trade_count"] = int(stats.get("trade_count", 0) or 0) + 1
            if pnl >= 0.0:
                stats["wins"] = int(stats.get("wins", 0) or 0) + 1
                stats["gross_profit"] = float(stats.get("gross_profit", 0.0) or 0.0) + pnl
            else:
                stats["losses"] = int(stats.get("losses", 0) or 0) + 1
                stats["gross_loss"] = float(stats.get("gross_loss", 0.0) or 0.0) + abs(pnl)

            eq = float(stats.get("equity", 0.0) or 0.0) + pnl
            peak = float(stats.get("equity_peak", eq) or eq)
            min_eq = float(stats.get("equity_min", eq) or eq)
            peak = max(peak, eq)
            min_eq = min(min_eq, eq)

            stats["equity"] = eq
            stats["equity_peak"] = peak
            stats["equity_min"] = min_eq

            # Maintain a bounded PnL series per strategy so advanced learning
            # logic can compute per-style CVaR and other distributional stats.
            try:
                pnl_series = list(stats.get("pnl_series") or [])
                pnl_series.append(float(pnl))
                if len(pnl_series) > self._pnl_series_max_length:
                    pnl_series = pnl_series[-self._pnl_series_max_length:]
                stats["pnl_series"] = pnl_series
            except Exception:
                # As above, metrics are best-effort.
                pass

            self._strategy_stats[key] = stats
        except Exception:
            # Per-strategy metrics are best-effort; never block core logic.
            return

    def _compute_metrics_snapshot(self) -> Dict[str, Any]:
        now = time.time()
        elapsed = max(0.0, now - self._study_start_ts)
        trades = len(self._closed_trades)
        wins = self._wins
        losses = self._losses
        total = float(max(1, wins + losses))
        win_rate = wins / total

        eq = self._equity
        peak = self._equity_peak if self._equity_peak != 0.0 else eq
        min_eq = self._equity_min if self._equity_min != 0.0 else eq
        dd = 0.0
        if peak > 0.0:
            dd = (peak - min_eq) / peak * 100.0

        avg_trade_return = 0.0
        if trades > 0:
            avg_trade_return = (self._gross_profit - self._gross_loss) / float(trades)

        # Build per-strategy summary snapshot for telemetry/Thoth
        strategy_metrics: Dict[str, Any] = {}
        for style, stats in self._strategy_stats.items():
            try:
                sc = int(stats.get("trade_count", 0) or 0)
                sw = int(stats.get("wins", 0) or 0)
                sl = int(stats.get("losses", 0) or 0)
                sgp = float(stats.get("gross_profit", 0.0) or 0.0)
                sgl = float(stats.get("gross_loss", 0.0) or 0.0)
                seq = float(stats.get("equity", 0.0) or 0.0)
                speak = float(stats.get("equity_peak", seq) or seq)
                smin = float(stats.get("equity_min", seq) or seq)
                stotal = max(1, sw + sl)
                swin_rate = sw / float(stotal)
                sdd = 0.0
                if speak > 0.0:
                    sdd = (speak - smin) / speak * 100.0

                strategy_metrics[style] = {
                    "trade_count": sc,
                    "wins": sw,
                    "losses": sl,
                    "win_rate": swin_rate,
                    "gross_profit": sgp,
                    "gross_loss": sgl,
                    "net_profit": sgp - sgl,
                    "equity": seq,
                    "equity_peak": speak,
                    "equity_min": smin,
                    "max_drawdown": sdd,
                    # Bounded trade-level PnL history for this style. This is
                    # intentionally shallow-copied so callers cannot mutate
                    # internal state.
                    "pnl_series": list(stats.get("pnl_series") or []),
                }
            except Exception:
                continue

        return {
            "timestamp": now,
            "study_start_ts": self._study_start_ts,
            "elapsed_seconds": elapsed,
            "study_duration_target": self.study_duration_seconds,
            "trade_count": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "gross_profit": self._gross_profit,
            "gross_loss": self._gross_loss,
            "net_profit": self._gross_profit - self._gross_loss,
            "equity": eq,
            "equity_peak": peak,
            "equity_min": min_eq,
            "max_drawdown": dd,
            "avg_trade_return": avg_trade_return,
            "strategy_metrics": strategy_metrics,
        }

    def _update_readiness_state(self, metrics: Dict[str, Any]) -> None:
        now = time.time()
        elapsed = float(metrics.get("elapsed_seconds", 0.0) or 0.0)
        trades = int(metrics.get("trade_count", 0) or 0)
        win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
        max_dd = float(metrics.get("max_drawdown", 0.0) or 0.0)

        # Phase 1: Warmup – always at least min_warmup_seconds
        if elapsed < self.min_warmup_seconds:
            self._readiness_state = "WARMUP"
            self._readiness_reason = "Warming up – collecting initial trades and prices"
            return

        # Phase 2: Learning – until full analysis reports ready
        if not self._analysis_ready:
            self._readiness_state = "LEARNING"
            self._readiness_reason = (
                f"Learning – waiting for full analysis readiness; "
                f"trades={trades}, win_rate={win_rate:.2f}, max_dd={max_dd:.2f}%"
            )
            return

        # Phase 3: Analysis-ready gate passed; trading can start.
        self._readiness_state = "READY"
        self._readiness_reason = (
            f"READY – full analysis complete ({self._analysis_ready_reason}); "
            f"trades={trades}, win_rate={win_rate:.2f}, max_dd={max_dd:.2f}%"
        )

    async def _maybe_emit_metrics(self) -> None:
        now = time.time()
        if now - self._last_metrics_emit_ts < self._metrics_emit_interval:
            return
        await self._emit_metrics()
        await self._emit_readiness()
        await self._persist_state_to_redis()
        self._last_metrics_emit_ts = now

    async def _emit_metrics(self) -> None:
        metrics = self._compute_metrics_snapshot()
        try:
            await self.publish_event("autotrade.paper.metrics", metrics)
        except Exception as e:
            self._handle_error("Failed to publish autotrade.paper.metrics", e)

    async def _emit_readiness(self) -> None:
        metrics = self._compute_metrics_snapshot()
        self._update_readiness_state(metrics)

        payload = {
            "timestamp": time.time(),
            "state": self._readiness_state,
            "reason": self._readiness_reason,
            "study_start_ts": self._study_start_ts,
            "study_duration_target": self.study_duration_seconds,
            "elapsed_seconds": metrics.get("elapsed_seconds"),
            "time_remaining_seconds": max(
                0.0,
                float(self.study_duration_seconds) - float(metrics.get("elapsed_seconds", 0.0) or 0.0),
            ),
            "metrics": {
                "trade_count": metrics.get("trade_count"),
                "wins": metrics.get("wins"),
                "losses": metrics.get("losses"),
                "win_rate": metrics.get("win_rate"),
                "max_drawdown": metrics.get("max_drawdown"),
                "net_profit": metrics.get("net_profit"),
            },
        }

        try:
            await self.publish_event("autotrade.readiness", payload)
        except Exception as e:
            self._handle_error("Failed to publish autotrade.readiness", e)

    async def _persist_state_to_redis(self) -> None:
        if not self.redis_connected:
            return
        try:
            state = self._compute_metrics_snapshot()
            state.update(
                {
                    "study_start_ts": self._study_start_ts,
                    "readiness_state": self._readiness_state,
                    "readiness_reason": self._readiness_reason,
                    "paper_positions": self._paper_positions,
                    "closed_trades": self._closed_trades,
                    "global_pnl_series": self._global_pnl_series,
                    "strategy_stats": self._strategy_stats,
                }
            )
            payload = json.dumps(state)
            await asyncio.to_thread(self.redis.set, "autotrade:paper:state", payload)
            if hasattr(self.redis, "xadd"):
                await asyncio.to_thread(
                    self.redis.xadd,
                    "autotrade:paper:state:stream",
                    {"timestamp": str(time.time()), "payload": payload},
                    maxlen=20000,
                    approximate=True,
                )
        except Exception as e:
            self._handle_error("Failed to persist paper autotrade state to Redis", e)

    async def _load_state_from_redis(self) -> None:
        if not self.redis_connected:
            return
        try:
            raw = await asyncio.to_thread(self.redis.get, "autotrade:paper:state")
            if not raw:
                return
            data = json.loads(raw)
            if not isinstance(data, dict):
                return

            self._study_start_ts = float(data.get("study_start_ts", self._study_start_ts) or self._study_start_ts)
            self._equity = float(data.get("equity", self._equity) or self._equity)
            self._equity_peak = float(data.get("equity_peak", self._equity_peak) or self._equity_peak)
            self._equity_min = float(data.get("equity_min", self._equity_min) or self._equity_min)
            self._wins = int(data.get("wins", self._wins) or self._wins)
            self._losses = int(data.get("losses", self._losses) or self._losses)
            self._gross_profit = float(data.get("gross_profit", self._gross_profit) or self._gross_profit)
            self._gross_loss = float(data.get("gross_loss", self._gross_loss) or self._gross_loss)
            self._readiness_state = str(data.get("readiness_state", self._readiness_state) or self._readiness_state)
            self._readiness_reason = str(data.get("readiness_reason", self._readiness_reason) or self._readiness_reason)
            self._paper_positions = data.get("paper_positions", self._paper_positions) or self._paper_positions
            self._closed_trades = data.get("closed_trades", self._closed_trades) or self._closed_trades
            self._global_pnl_series = data.get("global_pnl_series", self._global_pnl_series) or self._global_pnl_series
            self._strategy_stats = data.get("strategy_stats", self._strategy_stats) or self._strategy_stats

            self.logger.info(
                "Restored paper autotrade state from Redis – state=%s, equity=%.2f, wins=%d, losses=%d",
                self._readiness_state,
                self._equity,
                self._wins,
                self._losses,
            )
        except Exception as e:
            self._handle_error("Failed to load paper autotrade state from Redis", e)
