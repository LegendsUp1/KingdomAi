"""Conservative RL-inspired sizing policy scaffold.

This module provides a ``ConservativeSizingPolicy`` that can either operate in a
purely heuristic mode (using recent volatility/drawdown) or leverage a learned
Q-estimator from an offline CQL training pipeline.

It is designed to be called by higher-level agents (Thoth, order routers,
research notebooks) and does not talk to the event bus directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


class ConservativeSizingPolicy:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = config or {}
        self.cvar_alpha: float = float(cfg.get("cvar_alpha", 0.05))
        self.cql_penalty: float = float(cfg.get("cql_penalty", 1.0))
        self.max_fraction: float = float(cfg.get("max_fraction", 0.05))
        self.min_fraction: float = float(cfg.get("min_fraction", 0.0))
        self.q_estimator: Any = None

    def load_q_estimator(self, estimator: Any) -> None:
        """Attach a fitted Q-estimator.

        The estimator is expected to expose a ``predict(np.ndarray) -> np.ndarray``
        interface that returns estimated Q-values for state-action vectors.
        """

        self.q_estimator = estimator

    def suggested_fraction(
        self,
        state: Dict[str, Any],
        candidate_fractions: Optional[List[float]] = None,
    ) -> float:
        """Suggest a position fraction for the given state.

        ``state`` is a small feature dict (recent_volatility, win_rate, etc.).
        ``candidate_fractions`` is an optional grid of fractions to search over.
        """

        if candidate_fractions is None:
            candidate_fractions = [0.001, 0.0025, 0.005, 0.01, 0.02, 0.05]

        # No Q-estimator: fall back to a simple volatility/drawdown heuristic.
        if self.q_estimator is None:
            vol = float(state.get("recent_volatility", 0.01) or 0.01)
            dd = float(state.get("recent_drawdown_pct", 0.0) or 0.0)
            base = 0.02 / max(1e-6, vol * 10.0 + dd / 100.0)
            return float(
                max(self.min_fraction, min(self.max_fraction, base))
            )

        best_f = self.min_fraction
        best_val = -1e9
        for f in candidate_fractions:
            s_vec = self._state_action_vector(state, float(f))
            q = float(self.q_estimator.predict(s_vec))
            cvar = self._approx_cvar_for_action(state, float(f))
            cql_pen = self.cql_penalty * max(
                0.0,
                q - self._conservative_q_lower_bound(state, float(f)),
            )
            val = q - (cvar * 10.0) - cql_pen
            if val > best_val:
                best_val = val
                best_f = float(f)

        return float(max(self.min_fraction, min(self.max_fraction, best_f)))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state_action_vector(self, state: Dict[str, Any], fraction: float) -> np.ndarray:
        keys = [
            "recent_volatility",
            "recent_drawdown_pct",
            "win_rate",
            "edge_estimate",
        ]
        vals = [float(state.get(k, 0.0) or 0.0) for k in keys]
        vals.append(float(fraction))
        return np.asarray(vals, dtype=float).reshape(1, -1)

    def _approx_cvar_for_action(self, state: Dict[str, Any], fraction: float) -> float:
        vol = float(state.get("recent_volatility", 0.01) or 0.01)
        return float(vol * (1.0 + float(fraction) * 20.0))

    def _conservative_q_lower_bound(self, state: Dict[str, Any], fraction: float) -> float:
        wr = float(state.get("win_rate", 0.5) or 0.5)
        aw = float(state.get("avg_win", 0.01) or 0.01)
        al = float(state.get("avg_loss", 0.01) or 0.01)
        expected = wr * aw - (1.0 - wr) * al
        return float(expected * 0.5)
