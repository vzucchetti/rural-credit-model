"""Modelos: naive (taxa por segmento), regressão logística e XGBoost."""

from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier


class NaiveSegmentRate:
    """Benchmark: PD = taxa histórica de inadimplência do segmento (ex.: uf)."""

    def __init__(self, segment_cols):
        self.segment_cols = list(segment_cols)
        self.rates_ = None
        self.global_ = 0.0

    def fit(self, X: pd.DataFrame, y):
        d = X[self.segment_cols].astype("string").fillna("NA").copy()
        d["_y"] = np.asarray(y)
        self.global_ = float(d["_y"].mean())
        self.rates_ = d.groupby(self.segment_cols)["_y"].mean()
        return self

    def predict_proba(self, X: pd.DataFrame):
        key = X[self.segment_cols].astype("string").fillna("NA")
        idx = (
            pd.MultiIndex.from_frame(key)
            if len(self.segment_cols) > 1
            else key.iloc[:, 0].to_numpy()
        )
        pd_hat = self.rates_.reindex(idx).fillna(self.global_).to_numpy()
        return np.column_stack([1 - pd_hat, pd_hat])


def build_logistic(preprocessor, C=1.0, max_iter=2000):
    return Pipeline(
        [
            ("prep", preprocessor),
            (
                "clf",
                LogisticRegression(class_weight="balanced", C=C, max_iter=max_iter),
            ),
        ]
    )


def build_xgb(preprocessor, scale_pos_weight=None, **kw):
    params = dict(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="aucpr",
        tree_method="hist",
        n_jobs=4,
    )
    if scale_pos_weight:
        params["scale_pos_weight"] = scale_pos_weight
    params.update(kw)
    return Pipeline([("prep", preprocessor), ("clf", XGBClassifier(**params))])
