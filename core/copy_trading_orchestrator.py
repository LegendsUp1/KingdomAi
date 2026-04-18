import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.base_component_v2 import BaseComponentV2
from core.event_bus import EventBus
from core.real_exchange_executor import OrderType as RealOrderType, OrderSide as RealOrderSide


class CopyTradingOrchestrator(BaseComponentV2):
    """Orchestrates copy-trading status and metrics for the TradingTab Intelligence Hub.

    This component listens to copy-trading configuration events and live
    `trading.top_traders` data, aggregates it into `trading.copy.*` topics,
    and optionally integrates with the shared real exchange executors
    registered on the EventBus.
    """

    def __init__(self, event_bus: EventBus, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="CopyTradingOrchestrator", event_bus=event_bus, config=config or {})
        self.logger = logging.getLogger("kingdom_ai.CopyTradingOrchestrator")

        self.enabled: bool = bool(self.config.get("enabled", False))
        self.live_trading_enabled: bool = bool(self.config.get("enable_live_copy_trades", False))

        self.real_executor: Optional[Any] = None
        self._default_exchange: Optional[str] = None

        self._last_top_traders: List[Dict[str, Any]] = []
        self._status_message: str = "📋 Copy trading idle"
        self._copy_metrics: Dict[str, Any] = {
            "total_traders": 0,
            "avg_roi": 0.0,
            "avg_win_rate": 0.0,
        }

    async def _initialize(self) -> None:
        """Resolve shared executors from the EventBus registry if available."""
        try:
            if self.event_bus and hasattr(self.event_bus, "get_component"):
                executor = self.event_bus.get_component("real_exchange_executor")
                if executor is not None:
                    self.real_executor = executor

                    try:
                        exchanges = list(getattr(self.real_executor, "exchanges", {}).keys())
                        if exchanges:
                            self._default_exchange = "binance" if "binance" in exchanges else exchanges[0]
                    except Exception:
                        self._default_exchange = None

                    self.logger.info("CopyTradingOrchestrator connected to shared RealExchangeExecutor")
                else:
                    self.logger.warning("RealExchangeExecutor component not available; running in analysis-only mode")
        except Exception as e:
            self.logger.error(f"Error during CopyTradingOrchestrator initialization: {e}")

    async def _register_event_handlers(self) -> None:
        """Subscribe to copy-trading config and data topics."""
        await self.subscribe("copy_trading.enable", self._on_enable)
        await self.subscribe("copy_trading.disable", self._on_disable)
        await self.subscribe("copy_trading.config.update", self._on_config_update)
        await self.subscribe("copy.trading.fetch_top_traders", self._on_fetch_request)
        await self.subscribe("trading.top_traders", self._on_top_traders)
        await self.subscribe("trading.copy.trade_signal", self._on_copy_trade_signal)
        await self.subscribe("trade.execute", self._on_legacy_trade_execute)

    async def _on_enable(self, data: Dict[str, Any]) -> None:
        """Handle requests to enable copy trading from the UI."""
        try:
            self.enabled = True
            if isinstance(data, dict):
                if data.get("mode") == "live" and self.config.get("allow_live_trading", False):
                    self.live_trading_enabled = True
            await self._publish_status("📋 Copy trading enabled")
        except Exception as e:
            self.logger.error(f"Error handling copy_trading.enable: {e}")

    async def _on_disable(self, data: Dict[str, Any]) -> None:
        """Handle requests to disable copy trading."""
        try:
            self.enabled = False
            self.live_trading_enabled = False
            await self._publish_status("⏸️ Copy trading disabled")
        except Exception as e:
            self.logger.error(f"Error handling copy_trading.disable: {e}")

    async def _on_config_update(self, data: Dict[str, Any]) -> None:
        """Handle runtime configuration updates for copy trading."""
        try:
            if isinstance(data, dict):
                self.config.update(data)
                if "enable_live_copy_trades" in data:
                    self.live_trading_enabled = bool(data.get("enable_live_copy_trades", self.live_trading_enabled))
            await self._publish_status(self._status_message)
        except Exception as e:
            self.logger.error(f"Error handling copy_trading.config.update: {e}")

    async def _on_fetch_request(self, data: Dict[str, Any]) -> None:
        """Refresh copy-trading status when UI explicitly requests top traders."""
        try:
            await self._publish_status(self._status_message)
        except Exception as e:
            self.logger.error(f"Error handling copy.trading.fetch_top_traders: {e}")

    async def _on_top_traders(self, data: Dict[str, Any]) -> None:
        """Consume live `trading.top_traders` feed and publish copy status."""
        try:
            traders = data.get("traders", []) if isinstance(data, dict) else []
            if not isinstance(traders, list):
                return

            self._last_top_traders = traders

            ui_traders: List[Dict[str, Any]] = []
            total_roi = 0.0
            total_win_rate = 0.0

            for t in traders[:3]:
                try:
                    name = str(t.get("name", "Unknown"))
                    win_rate_raw = t.get("win_rate", 0.0)
                    roi_raw = t.get("roi", t.get("pnl", t.get("volume", 0.0)))

                    win_rate = float(win_rate_raw or 0.0)
                    profit = float(roi_raw or 0.0)

                    ui_traders.append({
                        "name": name,
                        "win_rate": win_rate,
                        "profit": profit,
                    })

                    total_roi += profit
                    total_win_rate += win_rate
                except Exception:
                    continue

            count = len(ui_traders)
            if count > 0:
                self._copy_metrics["total_traders"] = count
                self._copy_metrics["avg_roi"] = total_roi / float(count)
                self._copy_metrics["avg_win_rate"] = total_win_rate / float(count)

            if ui_traders:
                message = "📋 Copy trading ready - live top traders loaded from exchanges"
            else:
                message = "📋 Copy trading enabled but no top traders available yet"

            await self._publish_status(message, ui_traders)
            await self._publish_performance()
        except Exception as e:
            self.logger.error(f"Error handling trading.top_traders: {e}")

    async def _on_copy_trade_signal(self, data: Dict[str, Any]) -> None:
        """Handle canonical copy-trading trade signals.

        Expected payload (producer-agnostic):
            {
                "symbol": "BTC/USDT",
                "side": "buy" | "sell",
                "quantity": float,
                "price": Optional[float],
                "order_type": "market" | "limit",  # optional, defaults to market
                "exchange": Optional[str],            # optional preferred venue
                ... additional metadata ...
            }
        """
        try:
            if not isinstance(data, dict):
                return
            await self._handle_trade_signal(data, is_legacy=False)
        except Exception as e:
            self.logger.error(f"Error handling trading.copy.trade_signal: {e}")

    async def _on_legacy_trade_execute(self, data: Dict[str, Any]) -> None:
        """Bridge legacy trade.execute events for copy-trading into real execution.

        Several older components (e.g. trading.copy_trading.CopyTradingManager)
        publish "trade.execute" events with a "copied_from" field when they
        want to execute a copied trade. To avoid interfering with non-copy
        flows, we only treat events that include this field as copy signals.
        """
        try:
            if not isinstance(data, dict):
                return

            # Only handle copy-trading executions
            if "copied_from" not in data:
                return

            symbol = data.get("symbol")
            side = data.get("side")
            amount = data.get("amount")
            price = data.get("price")

            if symbol is None or side is None or amount is None:
                return

            # Normalize into canonical signal payload
            try:
                quantity = float(amount)
            except (TypeError, ValueError):
                return

            canonical: Dict[str, Any] = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": float(price) if price is not None else None,
                "order_type": data.get("type", "market"),
                "exchange": data.get("exchange"),
                "source": "legacy.trade.execute",
                "copied_from": data.get("copied_from"),
                "subscriber_id": data.get("subscriber_id"),
            }

            await self._handle_trade_signal(canonical, is_legacy=True)
        except Exception as e:
            self.logger.error(f"Error handling legacy trade.execute for copy trading: {e}")

    async def _handle_trade_signal(self, signal: Dict[str, Any], is_legacy: bool) -> None:
        """Core handler to execute or simulate a copy-trade signal.

        This enforces safety gates and, when explicitly enabled, routes
        the trade either through TradingComponent (preferred) or directly
        to RealExchangeExecutor.
        """
        try:
            if not self.enabled:
                self.logger.info("CopyTradingOrchestrator received trade signal while disabled; ignoring")
                return

            # Live execution must be explicitly enabled via config or mode
            if not self.live_trading_enabled or not self.config.get("allow_live_trading", False):
                self.logger.info(
                    "CopyTradingOrchestrator received trade signal but live trading is not enabled; "
                    "running in analysis-only mode",
                )
                return

            symbol_raw = signal.get("symbol")
            side_raw = signal.get("side")
            if not symbol_raw or not side_raw:
                return

            symbol = str(symbol_raw)
            side_str = str(side_raw).lower()

            try:
                quantity = float(signal.get("quantity", 0.0) or 0.0)
            except (TypeError, ValueError):
                quantity = 0.0

            price_val = signal.get("price")
            price: Optional[float]
            try:
                price = float(price_val) if price_val is not None else None
            except (TypeError, ValueError):
                price = None

            if quantity <= 0.0:
                self.logger.warning(f"Invalid copy-trade quantity for {symbol}: {quantity}")
                return

            # Safety gates from config
            max_qty = self.config.get("max_copy_trade_amount")
            if max_qty is not None:
                try:
                    max_qty_f = float(max_qty)
                    if quantity > max_qty_f:
                        self.logger.warning(
                            f"Copy-trade quantity {quantity} exceeds max_copy_trade_amount {max_qty_f}; skipping",
                        )
                        return
                except (TypeError, ValueError):
                    pass

            allowed_symbols = self.config.get("allowed_symbols")
            if isinstance(allowed_symbols, (list, tuple)) and allowed_symbols:
                if symbol not in allowed_symbols:
                    self.logger.warning(f"Symbol {symbol} is not in allowed_symbols; skipping copy trade")
                    return

            # Exchange selection
            ex_name_raw = signal.get("exchange") or self._default_exchange
            if not isinstance(ex_name_raw, str) or not ex_name_raw:
                self.logger.warning("No valid exchange specified for copy trade and no default available; skipping")
                return

            exchange_name = ex_name_raw.lower()

            allowed_exchanges = self.config.get("allowed_exchanges")
            if isinstance(allowed_exchanges, (list, tuple)) and allowed_exchanges:
                norm_allowed = {str(e).lower() for e in allowed_exchanges}
                if exchange_name not in norm_allowed:
                    self.logger.warning(
                        f"Exchange {exchange_name} is not in allowed_exchanges; skipping copy trade",
                    )
                    return

            if self.real_executor is None:
                self.logger.warning(
                    "CopyTradingOrchestrator cannot execute trade signal because RealExchangeExecutor is not available",
                )
                return

            # Preferred path: route through TradingComponent so that its
            # portfolio, risk, and routing logic remain authoritative.
            trading_component = None
            try:
                if self.event_bus and hasattr(self.event_bus, "get_component"):
                    trading_component = self.event_bus.get_component("trading_component")
            except Exception:
                trading_component = None

            if trading_component is not None and hasattr(trading_component, "_on_trading_signal"):
                try:
                    signal_payload: Dict[str, Any] = {
                        "symbol": symbol,
                        "signal_type": "buy" if side_str in ("buy", "long") else "sell",
                        "quantity": quantity,
                        "price": price,
                    }
                    self.logger.info(
                        f"Routing copy-trade signal for {symbol} via TradingComponent (qty={quantity}, price={price})",
                    )
                    await trading_component._on_trading_signal(signal_payload)
                    return
                except Exception as tc_err:
                    self.logger.error(f"Error routing copy-trade via TradingComponent: {tc_err}")

            # Fallback: direct RealExchangeExecutor call
            try:
                real_side = RealOrderSide.BUY if side_str in ("buy", "long") else RealOrderSide.SELL
            except Exception:
                self.logger.warning(f"Unsupported copy-trade side: {side_str}")
                return

            order_type_raw = str(signal.get("order_type", signal.get("type", "market")) or "market").lower()
            if order_type_raw not in ("market", "limit"):
                self.logger.warning(f"Unsupported copy-trade order_type {order_type_raw}; defaulting to market")
                order_type_raw = "market"

            real_type = RealOrderType.MARKET if order_type_raw == "market" else RealOrderType.LIMIT

            self.logger.info(
                f"Executing LIVE copy trade on {exchange_name.upper()}: {real_side.value.upper()} "
                f"{quantity} {symbol} type={real_type.value} price={price}",
            )

            try:
                _ = await self.real_executor.place_real_order(
                    exchange_name=exchange_name,
                    symbol=symbol,
                    order_type=real_type,
                    side=real_side,
                    amount=quantity,
                    price=price if real_type == RealOrderType.LIMIT else None,
                )
            except Exception as live_err:
                self.logger.error(f"Error executing live copy trade via RealExchangeExecutor: {live_err}")

        except Exception as e:
            self.logger.error(f"Error in _handle_trade_signal: {e}")

    async def _publish_status(self, message: str, traders: Optional[List[Dict[str, Any]]] = None) -> None:
        """Publish `trading.copy.status` in the exact shape expected by TradingTab."""
        try:
            self._status_message = message

            if traders is None:
                traders = []
                for t in self._last_top_traders[:3]:
                    try:
                        name = str(t.get("name", "Unknown"))
                        win_rate_raw = t.get("win_rate", 0.0)
                        roi_raw = t.get("roi", t.get("pnl", t.get("volume", 0.0)))
                        win_rate = float(win_rate_raw or 0.0)
                        profit = float(roi_raw or 0.0)
                        traders.append({
                            "name": name,
                            "win_rate": win_rate,
                            "profit": profit,
                        })
                    except Exception:
                        continue

            payload: Dict[str, Any] = {
                "message": message,
                "active": bool(self.enabled),
                "traders": traders,
            }

            await self.publish_event("trading.copy.status", payload)
        except Exception as e:
            self.logger.error(f"Error publishing trading.copy.status: {e}")

    async def _publish_performance(self) -> None:
        """Publish a lightweight performance snapshot for copy trading."""
        try:
            payload = {
                "enabled": bool(self.enabled),
                "live_trading": bool(self.live_trading_enabled),
                "metrics": dict(self._copy_metrics),
            }
            await self.publish_event("trading.copy.performance", payload)
        except Exception as e:
            self.logger.error(f"Error publishing trading.copy.performance: {e}")

    async def _start(self) -> None:
        """Optional start hook; reserved for future background tasks."""
        try:
            if self.real_executor is not None and self._default_exchange is None:
                try:
                    exchanges = list(getattr(self.real_executor, "exchanges", {}).keys())
                    if exchanges:
                        self._default_exchange = "binance" if "binance" in exchanges else exchanges[0]
                except Exception:
                    self._default_exchange = None
        except Exception as e:
            self.logger.error(f"Error in CopyTradingOrchestrator _start: {e}")

    async def _stop(self) -> None:
        """Optional stop hook for future extensions."""
        return
