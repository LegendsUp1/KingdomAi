"""Adversarial validation utilities.

This module implements a simple adversarial validation procedure to measure how
much the distribution of live data differs from paper/backtest data. It is
intended for offline analysis and model diagnostics.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split


def run_adversarial_validation(
    paper_df: pd.DataFrame,
    live_df: pd.DataFrame,
    features: List[str],
) -> Tuple[Dict[str, float], LogisticRegression]:
    """Train a classifier to distinguish paper vs live rows.

    Returns a metrics dict and the fitted classifier. Higher AUC indicates a
    stronger distribution shift between paper and live.
    """

    df_p = paper_df.copy()
    df_p["__label__"] = 0
    df_l = live_df.copy()
    df_l["__label__"] = 1
    df = pd.concat([df_p, df_l], ignore_index=True)

    X = df[features].fillna(0.0).values
    y = df["__label__"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)

    pred_proba = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, pred_proba)
    y_pred = (pred_proba >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="binary"
    )

    metrics: Dict[str, float] = {
        "auc": float(auc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "n_train": float(len(X_train)),
        "n_test": float(len(X_test)),
    }

    return metrics, clf
