"""Métricas: AUROC, KS, Brier e pontos da curva de calibração."""

from __future__ import annotations
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss, roc_curve
from sklearn.calibration import calibration_curve


def ks_statistic(y_true, y_score) -> float:
    y = np.asarray(y_true)
    p = np.asarray(y_score)
    pos = np.sort(p[y == 1])
    neg = np.sort(p[y == 0])
    grid = np.sort(np.unique(p))
    cp = np.searchsorted(pos, grid, "right") / max(len(pos), 1)
    cn = np.searchsorted(neg, grid, "right") / max(len(neg), 1)
    return float(np.max(np.abs(cp - cn)))


def core_metrics(y_true, y_score) -> dict:
    return {
        "auroc": float(roc_auc_score(y_true, y_score)),
        "ks": ks_statistic(y_true, y_score),
        "brier": float(brier_score_loss(y_true, y_score)),
    }


def calibration_points(y_true, y_score, n_bins=10):
    frac_pos, mean_pred = calibration_curve(
        y_true, y_score, n_bins=n_bins, strategy="quantile"
    )
    return [
        {"mean_pred": float(a), "frac_pos": float(b)}
        for a, b in zip(mean_pred, frac_pos)
    ]


def roc_points(y_true, y_score, n=101):
    """Pontos da ROC interpolados numa grade uniforme de FPR (downsample p/ o run store)."""
    fpr, tpr, _ = roc_curve(y_true, y_score)
    grid = np.linspace(0.0, 1.0, n)
    tpr_i = np.interp(grid, fpr, tpr)
    return [{"fpr": float(a), "tpr": float(b)} for a, b in zip(grid, tpr_i)]


def ks_curve(y_true, y_score, n=101):
    """CDF do score para inadimplentes e adimplentes (o gap máximo = KS)."""
    y = np.asarray(y_true)
    p = np.asarray(y_score)
    pos = np.sort(p[y == 1])
    neg = np.sort(p[y == 0])
    grid = np.quantile(p, np.linspace(0.0, 1.0, n))
    cdf_pos = np.searchsorted(pos, grid, "right") / max(len(pos), 1)
    cdf_neg = np.searchsorted(neg, grid, "right") / max(len(neg), 1)
    return [
        {"score": float(t), "cdf_pos": float(a), "cdf_neg": float(b)}
        for t, a, b in zip(grid, cdf_pos, cdf_neg)
    ]
