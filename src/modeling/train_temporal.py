"""Validação out-of-time por safra (walk-forward, janela expansível).

Para cada safra de teste t (da (min_train_safras+1)-ésima em diante):
  treina em TODAS as safras < t  e  testa na safra t.
Mesmos 3 modelos (naive, logística, XGBoost) e mesmas métricas/curvas do k-fold.
A partição no tempo é o próprio controle de vazamento (não se agrupa por mutuário).

ATENÇÃO (censura à direita): as safras mais recentes podem não ter os 18 meses
de janela do alvo totalmente observados — a taxa de inadimplência delas fica
subestimada. Confira rate_test/n_test por safra antes de concluir.
"""

from __future__ import annotations
import numpy as np
from datetime import datetime, timezone

from src.features.registry import TARGET
from src.modeling.preprocessing import load_base, make_xy, build_preprocessor
from src.modeling.feature_selection import select_features
from src.modeling import models as M
from src.modeling.metrics import core_metrics, calibration_points, roc_points, ks_curve
from src.modeling.run_storage import save_run
from src.utils.io import duckdb_s3, load_config
from src.utils.logging import get_logger

log = get_logger("modeling")


def _safra_map(cfg: dict):
    """(ref_bacen, nu_ordem) -> safra (ano-safra pelo mês de corte, padrão julho)."""
    cut = cfg["modeling"].get("safra_cutoff_month", 7)
    inpath = cfg["paths"]["silver_sicor"]
    db = duckdb_s3(cfg)
    return db.execute(f"""
        SELECT ob."#REF_BACEN" AS ref_bacen, ob."NU_ORDEM" AS nu_ordem,
               year(ob.DT_EMISSAO) - CAST(month(ob.DT_EMISSAO) < {cut} AS INTEGER) AS safra
        FROM read_parquet('{inpath}operacao_basica.parquet') AS ob
    """).fetchdf()


def _build(name, seg, prep, ytr):
    if name == "naive":
        return M.NaiveSegmentRate(seg)
    if name == "logistic":
        return M.build_logistic(prep())
    pos = float(np.mean(ytr))
    spw = (1 - pos) / max(pos, 1e-6)
    return M.build_xgb(prep(), scale_pos_weight=spw)


def train_temporal(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config("settings")
    mc = cfg["modeling"]
    df = load_base(cfg)
    df = df.merge(_safra_map(cfg), on=["ref_bacen", "nu_ordem"], how="left")
    df = df.dropna(subset=["safra"]).copy()
    df["safra"] = df["safra"].astype(int)

    cat, num = select_features(df, cfg)

    def prep():
        return build_preprocessor(cat, num, mc.get("max_categories", 30))

    seg = [c for c in (mc.get("naive_segment", "uf"),) if c in df.columns] or cat[:1]

    safras = sorted(df["safra"].unique())
    test_safras = safras[mc.get("min_train_safras", 1) :]
    if not test_safras:
        raise RuntimeError(f"Poucas safras para OOT (encontradas: {safras}).")
    log.info("Safras: %s | teste OOT em: %s", safras, test_safras)

    results = []
    for name in ("naive", "logistic", "xgboost"):
        per_safra = []
        for t in test_safras:
            tr = df[df["safra"] < t]
            te = df[df["safra"] == t]
            if te[TARGET].nunique() < 2 or len(te) < 50:
                log.warning(
                    "[%s] safra %s teste inviável (n=%d, classes=%d) — pulada",
                    name,
                    t,
                    len(te),
                    te[TARGET].nunique(),
                )
                continue
            Xtr, ytr, _ = make_xy(tr, cat, num)
            Xte, yte, _ = make_xy(te, cat, num)
            mdl = _build(name, seg, prep, ytr)
            mdl.fit(Xtr, ytr)
            p = mdl.predict_proba(Xte)[:, 1]
            ev = {
                "safra": int(t),
                "safra_label": f"{t}/{str(t + 1)[-2:]}",
                "n_train": int(len(tr)),
                "n_test": int(len(te)),
                "rate_test": float(np.mean(yte)),
                "metrics": core_metrics(yte, p),
                "roc": roc_points(yte, p),
                "ks_curve": ks_curve(yte, p),
                "calibration": calibration_points(yte, p),
            }
            per_safra.append(ev)
            log.info(
                "[%s] safra %s AUROC=%.3f KS=%.3f Brier=%.4f (n_te=%d rate=%.4f)",
                name,
                ev["safra_label"],
                ev["metrics"]["auroc"],
                ev["metrics"]["ks"],
                ev["metrics"]["brier"],
                ev["n_test"],
                ev["rate_test"],
            )
        agg = (
            {
                k: float(np.mean([e["metrics"][k] for e in per_safra]))
                for k in ("auroc", "ks", "brier")
            }
            if per_safra
            else {}
        )
        results.append({"model": name, "per_safra": per_safra, "metrics": agg})

    record = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "validation": "temporal",
        "horizon": mc.get("horizon", 18),
        "safras": [int(s) for s in safras],
        "test_safras": [int(s) for s in test_safras],
        "results": results,
    }
    save_run(record, cfg)
    log.info(
        "OOT: "
        + " | ".join(
            f"{r['model']} AUROC_médio="
            f"{r['metrics'].get('auroc', float('nan')):.3f}"
            for r in results
        )
    )
    return record


if __name__ == "__main__":
    train_temporal()
