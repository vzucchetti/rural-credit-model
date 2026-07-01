from __future__ import annotations
import pandas as pd
from src.features.registry import CAT_FEATURES, NUM_FEATURES
from src.utils.logging import get_logger

log = get_logger("modeling")


def select_features(df: pd.DataFrame, cfg: dict):
    """Retorna (cat_cols, num_cols) selecionados conforme config + filtros de qualidade.
    config.modeling.features: lista desejada (None/[] = todas)."""
    mc = cfg["modeling"]
    desired = mc.get("features") or (CAT_FEATURES + NUM_FEATURES)
    max_null = mc.get("max_null_frac", 0.95)
    cat = [c for c in CAT_FEATURES if c in desired and c in df.columns]
    num = [c for c in NUM_FEATURES if c in desired and c in df.columns]

    # filtro: descarta colunas quase totalmente nulas ou constantes
    kept_cat, kept_num = [], []
    for c in cat:
        nullf = df[c].isna().mean()
        nun = df[c].nunique(dropna=True)
        if nullf > max_null or nun < 2:
            log.warning("descartada %s (null=%.2f, n_unique=%d)", c, nullf, nun)
            continue
        kept_cat.append(c)
    for c in num:
        nullf = df[c].isna().mean()
        if nullf > max_null or df[c].nunique(dropna=True) < 2:
            log.warning("descartada %s (null=%.2f)", c, nullf)
            continue
        kept_num.append(c)
    log.info("Features selecionadas: %d cat, %d num", len(kept_cat), len(kept_num))
    return kept_cat, kept_num
