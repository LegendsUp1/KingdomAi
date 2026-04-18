"""Split conformal calibration utilities.

This module provides a lightweight SplitConformalCalibrator that can be used to
turn raw model scores into conservative probability upper bounds or to infer a
score threshold corresponding to a desired error level.

It is intended for use by sizing / risk policies and offline analysis; it is
not wired into the live runtime by default.
"""

from __future__ import annotations

from typing import List

import math
import numpy as np


class SplitConformalCalibrator:
    """Simple split-conformal style calibrator over scalar scores.

    ``fit`` should be called with historical scores and binary labels
    (1 = success / win, 0 = failure / loss). The ``calibrated_probability_upper``
    method then returns a conservative upper confidence bound for a new score.
    """

    def __init__(self) -> None:
        self.calib_scores: np.ndarray | None = None
        self.calib_labels: np.ndarray | None = None

    def fit(self, scores: List[float], labels: List[int]) -> None:
        if len(scores) != len(labels):
            raise ValueError("scores and labels must have the same length")
        self.calib_scores = np.asarray(scores, dtype=float)
        self.calib_labels = np.asarray(labels, dtype=int)

    def calibrated_probability_upper(self, score: float, alpha: float = 0.01) -> float:
        """Return a conservative upper bound on P(y=1 | score).

        When no calibration data is available we fall back to returning the raw
        score. ``alpha`` controls how conservative the bound is; smaller alpha
        yields a higher (more pessimistic) requirement.
        """

        if self.calib_scores is None or self.calib_labels is None or len(self.calib_scores) == 0:
            return float(score)

        ge_idx = self.calib_scores >= float(score)
        n = int(ge_idx.sum())
        if n == 0:
            # No comparable calibration points; nudge upward slightly.
            return float(min(1.0, score + alpha))

        pos_rate = float(self.calib_labels[ge_idx].mean())
        # Very simple normal-approximation margin; this is intentionally
        # conservative and easy to reason about.
        margin = math.sqrt(max(1e-6, pos_rate * (1.0 - pos_rate) / n)) * 3.0
        return float(min(1.0, pos_rate + margin + alpha))

    def score_threshold_for_alpha(self, alpha: float = 0.01) -> float:
        """Return the smallest score whose calibrated upper bound >= 1-alpha.

        If calibration data is missing, this returns 1.0 so that callers treat
        all scores as insufficiently certain.
        """

        if self.calib_scores is None or self.calib_labels is None or len(self.calib_scores) == 0:
            return 1.0

        scores_sorted = np.sort(self.calib_scores)
        target = 1.0 - float(alpha)
        for s in scores_sorted[::-1]:
            if self.calibrated_probability_upper(float(s), alpha) >= target:
                return float(s)
        return 1.0
