"""Options hedging helpers.

These helpers are templates for constructing simple protective put hedges and
approximate delta-neutral synthetic hedges given a position and an options
chain. They do not talk to exchanges directly and can be used by research
notebooks, Thoth prompts, or higher-level order routers.
"""

from __future__ import annotations

from typing import Any, Dict, List


def construct_protective_put_hedge(
    position: Dict[str, Any],
    options_chain: List[Dict[str, Any]],
    hedge_coverage: float = 1.0,
) -> List[Dict[str, Any]]:
    """Construct a simple protective put hedge for a long position.

    ``position`` is expected to contain ``side`` ("long"/"short") and
    ``notional`` (USD or base-currency notional). ``options_chain`` should be a
    list of option descriptors including at least ``type``, ``delta``,
    ``symbol``, ``price``, and ``multiplier``.
    """

    if position.get("side") != "long":
        return []

    target_notional = float(position.get("notional", 0.0) or 0.0) * float(
        hedge_coverage or 0.0
    )
    if target_notional <= 0.0:
        return []

    candidates = [
        o
        for o in options_chain
        if o.get("type") == "put" and -0.5 < float(o.get("delta", 0.0) or 0.0) < -0.2
    ]
    candidates = sorted(
        candidates,
        key=lambda x: (
            str(x.get("expiry", "")),
            abs(float(x.get("delta", -0.25) or -0.25)),
        ),
    )
    if not candidates:
        return []

    chosen = candidates[0]
    option_price = float(chosen.get("price", 0.0) or 0.0)
    multiplier = float(chosen.get("multiplier", 1.0) or 1.0)
    if option_price <= 0.0 or multiplier <= 0.0:
        return []

    qty = int(max(1, round(target_notional / max(1e-6, option_price * multiplier))))
    return [
        {
            "action": "buy",
            "symbol": chosen["symbol"],
            "quantity": qty,
            "leg": chosen,
        }
    ]


def delta_neutral_synthetic(
    position: Dict[str, Any], options_chain: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Approximate a delta-neutral hedge using listed options.

    This is a simple greedy algorithm that walks options sorted by |delta| and
    accumulates contracts until the net delta is close to zero.
    """

    pos_size = float(position.get("size", 0.0) or 0.0)
    if pos_size == 0.0:
        return []

    target_delta = -pos_size
    options = sorted(
        [o for o in options_chain],
        key=lambda o: -abs(float(o.get("delta", 0.0) or 0.0)),
    )
    legs: List[Dict[str, Any]] = []
    remaining = abs(target_delta)

    for opt in options:
        del_per_contract = abs(float(opt.get("delta", 0.0) or 0.0))
        if del_per_contract == 0.0:
            continue
        qty = int(min(remaining / del_per_contract, 1000))
        if qty <= 0:
            continue
        legs.append(
            {
                "action": "buy" if target_delta > 0 else "sell",
                "symbol": opt["symbol"],
                "quantity": qty,
                "leg": opt,
            }
        )
        remaining -= qty * del_per_contract
        if remaining <= 0:
            break

    return legs
