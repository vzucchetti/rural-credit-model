"""Treino e avaliação dos 3 modelos (naive, logística, XGBoost) com validação
cruzada estratificada e AGRUPADA por mutuário (sem vazamento de tomador).
Métricas por fold + OOF + calibração, persistidas via run_store."""

from __future__ import annotations
import numpy as np
from datetime import datetime, timezone
from sklearn.model_selection import StratifiedGroupKFold

from src.modeling.preprocessing import load_base, make_xy, build_preprocessor
from src.modeling.feature_selection import select_features
from src.modeling import models as M
from src.modeling.metrics import core_metrics, calibration_points, roc_points, ks_curve
from src.modeling.run_storage import save_run
from src.utils.io import load_config
from src.utils.logging import get_logger


log = get_logger("modeling")


def _eval_model(name, make, proba, X, y, groups, splits):
    oof = np.full(len(y), np.nan)
    folds = []
    for k, (tr, te) in enumerate(splits, 1):
        leak = len(set(groups[tr]) & set(groups[te]))
        mdl = make()
        mdl.fit(X.iloc[tr], y[tr])
        p = proba(mdl, X.iloc[te])
        oof[te] = p
        m = core_metrics(y[te], p)
        m.update(fold=k, leak_mutuario=leak)
        folds.append(m)
        log.info(
            "  [%s] fold %d AUROC=%.4f KS=%.4f Brier=%.4f leak=%d",
            name,
            k,
            m["auroc"],
            m["ks"],
            m["brier"],
            leak,
        )
    agg = {
        kk: float(np.mean([f[kk] for f in folds])) for kk in ("auroc", "ks", "brier")
    }
    agg_std = {
        f"{kk}_std": float(np.std([f[kk] for f in folds]))
        for kk in ("auroc", "ks", "brier")
    }
    mask = ~np.isnan(oof)
    yt, ps = y[mask], oof[mask]
    return {
        "model": name,
        "metrics": {**agg, **agg_std},
        "folds": folds,
        "calibration": calibration_points(yt, ps),
        "roc": roc_points(yt, ps),
        "ks_curve": ks_curve(yt, ps),
    }


def train(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config("settings")
    mc = cfg["modeling"]
    rs = mc.get("random_state", 42)
    n_splits = mc.get("n_splits", 5)
    df = load_base(cfg)
    cat_cols, num_cols = select_features(df, cfg)
    X, y, groups = make_xy(df, cat_cols, num_cols)

    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=rs)
    splits = list(skf.split(X, y, groups))

    def prep():
        return build_preprocessor(cat_cols, num_cols, mc.get("max_categories", 30))

    pos = float(np.mean(y))
    spw = (1 - pos) / max(pos, 1e-6)
    seg = [c for c in (mc.get("naive_segment", "uf"),) if c in X.columns] or cat_cols[
        :1
    ]

    defs = {
        "naive": (
            lambda: M.NaiveSegmentRate(seg),
            lambda m, Xt: m.predict_proba(Xt)[:, 1],
        ),
        "logistic": (
            lambda: M.build_logistic(prep()),
            lambda m, Xt: m.predict_proba(Xt)[:, 1],
        ),
        "xgboost": (
            lambda: M.build_xgb(prep(), scale_pos_weight=spw),
            lambda m, Xt: m.predict_proba(Xt)[:, 1],
        ),
    }

    results = []
    for name, (make, proba) in defs.items():
        log.info("== %s ==", name)
        results.append(_eval_model(name, make, proba, X, y, groups, splits))

    record = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "horizon": mc.get("horizon", 18),
        "n_splits": n_splits,
        "target_rate": pos,
        "n_rows": int(len(y)),
        "features": {"cat": cat_cols, "num": num_cols},
        "results": results,
    }
    save_run(record, cfg)
    log.info(
        "Resumo: "
        + " | ".join(
            f"{r['model']} AUROC={r['metrics']['auroc']:.3f} - KS={r['metrics']['ks']:.3f}"
            for r in results
        )
    )
    return record


if __name__ == "__main__":
    train()
