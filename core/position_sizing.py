from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class PositionSizingInputs:
    equity_usd: float
    entry_price: float
    stop_price: Optional[float]
    risk_fraction: float
    side: str
    confidence: Optional[float] = None
    max_notional_usd: Optional[float] = None
    drawdown_pct: Optional[float] = None
    volatility: Optional[float] = None
    avg_volatility: Optional[float] = None
    kelly_fraction: Optional[float] = None
    rl_fraction: Optional[float] = None
    qty_step: Optional[float] = None
    min_qty: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionSizingResult:
    quantity: float
    notional_usd: float
    risk_amount_usd: float
    risk_fraction_used: float
    notional_fraction: float
    stop_distance: Optional[float]
    multipliers: Dict[str, float] = field(default_factory=dict)
    caps: Dict[str, float] = field(default_factory=dict)


class BayesianConfidence:
    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self.alpha = float(prior_alpha)
        self.beta = float(prior_beta)

    def update(self, success: bool) -> None:
        if success:
            self.alpha += 1.0
        else:
            self.beta += 1.0

    def mean(self) -> float:
        denom = self.alpha + self.beta
        if denom <= 0:
            return 0.5
        return self.alpha / denom

    def conservative_score(self, z: float = 1.0) -> float:
        denom = self.alpha + self.beta
        if denom <= 1:
            return self.mean()
        mean = self.mean()
        var = (self.alpha * self.beta) / ((denom ** 2) * (denom + 1.0))
        std = var ** 0.5
        return max(0.0, min(1.0, mean - z * std))


class PositionSizer:
    def __init__(
        self,
        *,
        min_confidence_floor: float = 0.25,
        max_volatility_scale: float = 1.5,
        min_volatility_scale: float = 0.25,
    ) -> None:
        self.min_confidence_floor = float(min_confidence_floor)
        self.max_volatility_scale = float(max_volatility_scale)
        self.min_volatility_scale = float(min_volatility_scale)

    def size(self, inputs: PositionSizingInputs) -> PositionSizingResult:
        equity = float(inputs.equity_usd or 0.0)
        entry = float(inputs.entry_price or 0.0)

        if equity <= 0.0 or entry <= 0.0:
            return PositionSizingResult(
                quantity=0.0,
                notional_usd=0.0,
                risk_amount_usd=0.0,
                risk_fraction_used=0.0,
                notional_fraction=0.0,
                stop_distance=None,
            )

        risk_fraction = _clamp(float(inputs.risk_fraction or 0.0), 0.0, 1.0)
        if inputs.kelly_fraction is not None:
            kf = float(inputs.kelly_fraction or 0.0)
            if kf > 0.0:
                risk_fraction = min(risk_fraction, _clamp(kf, 0.0, 1.0))
        if inputs.rl_fraction is not None:
            rf = float(inputs.rl_fraction or 0.0)
            if rf > 0.0:
                risk_fraction = min(risk_fraction, _clamp(rf, 0.0, 1.0))

        risk_amount = equity * risk_fraction

        conf = _normalize_confidence(inputs.confidence)
        conf_mult = self.min_confidence_floor + (1.0 - self.min_confidence_floor) * conf

        dd_mult = _drawdown_multiplier(inputs.drawdown_pct)
        vol_mult = _volatility_multiplier(
            current=inputs.volatility,
            avg=inputs.avg_volatility,
            min_scale=self.min_volatility_scale,
            max_scale=self.max_volatility_scale,
        )

        risk_amount_adj = max(0.0, risk_amount * conf_mult * dd_mult * vol_mult)

        stop_distance: Optional[float] = None
        if inputs.stop_price is not None:
            try:
                stop = float(inputs.stop_price)
                if stop > 0.0:
                    stop_distance = abs(entry - stop)
            except (TypeError, ValueError):
                stop_distance = None

        qty: float
        if stop_distance is None or stop_distance <= 0.0:
            max_notional = float(inputs.max_notional_usd or 0.0)
            if max_notional > 0.0:
                qty = max_notional / entry
            else:
                qty = 0.0
        else:
            qty = risk_amount_adj / stop_distance

        caps: Dict[str, float] = {}
        max_notional = float(inputs.max_notional_usd or 0.0)
        if max_notional > 0.0 and qty * entry > max_notional:
            caps["max_notional_usd"] = max_notional
            qty = max_notional / entry

        qty_step = inputs.qty_step
        if qty_step is not None and qty_step > 0:
            qty = _floor_to_step(qty, float(qty_step))

        if qty <= float(inputs.min_qty or 0.0):
            qty = 0.0

        notional = qty * entry
        notional_fraction = (notional / equity) if equity > 0.0 else 0.0

        return PositionSizingResult(
            quantity=float(qty),
            notional_usd=float(notional),
            risk_amount_usd=float(risk_amount_adj),
            risk_fraction_used=float(risk_fraction),
            notional_fraction=float(notional_fraction),
            stop_distance=float(stop_distance) if stop_distance is not None else None,
            multipliers={
                "confidence": float(conf_mult),
                "drawdown": float(dd_mult),
                "volatility": float(vol_mult),
            },
            caps=caps,
        )


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _normalize_confidence(confidence: Optional[float]) -> float:
    if confidence is None:
        return 0.5
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return 0.5
    if c > 1.0:
        c = c / 100.0
    return _clamp(c, 0.0, 1.0)


def _drawdown_multiplier(drawdown_pct: Optional[float]) -> float:
    if drawdown_pct is None:
        return 1.0
    try:
        dd = float(drawdown_pct)
    except (TypeError, ValueError):
        return 1.0

    if dd >= 20.0:
        return 0.25
    if dd >= 10.0:
        return 0.5
    if dd >= 5.0:
        return 0.75
    return 1.0


def _volatility_multiplier(
    *,
    current: Optional[float],
    avg: Optional[float],
    min_scale: float,
    max_scale: float,
) -> float:
    if current is None or avg is None:
        return 1.0

    try:
        cur = float(current)
        av = float(avg)
    except (TypeError, ValueError):
        return 1.0

    if cur <= 0.0 or av <= 0.0:
        return 1.0

    scale = av / cur
    return _clamp(scale, min_scale, max_scale)


def _floor_to_step(x: float, step: float) -> float:
    if step <= 0.0:
        return x
    return (int(x / step)) * step
