from __future__ import annotations
import math
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from src.features.registry import (
    TARGET,
    GROUP,
    PRIMARY_KEYS,
    CAT_FEATURES,
    NUM_FEATURES,
)
from src.utils.io import duckdb_s3, load_config
from src.utils.logging import get_logger


log = get_logger("modeling")


def _base_cols(db, uri: str) -> list[str]:
    return [
        r[0]
        for r in db.execute(f"DESCRIBE SELECT * FROM read_parquet('{uri}')").fetchall()
    ]


def load_base(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config("settings")
    mc = cfg["modeling"]
    uri = mc["base_uri"]
    max_rows = int(mc.get("max_rows", 4_000_000))
    seed = int(mc.get("sample_state", 42))
    db = duckdb_s3(cfg)
    present = set(_base_cols(db, uri))
    wanted = [
        c for c in PRIMARY_KEYS + [TARGET] + CAT_FEATURES + NUM_FEATURES if c in present
    ]
    collist = ", ".join(f'"{c}"' for c in wanted)
    total = db.execute(f"SELECT COUNT(*) FROM read_parquet('{uri}')").fetchone()[0]
    sample = ""
    if total > max_rows:
        pct = min(100, math.ceil(100 * max_rows / total))
        sample = f"USING SAMPLE {pct}% (bernoulli, {seed})"
        log.info(
            "base tem linhas (%.1f%%) —> max_rows=%d - amostrando %d%%",
            total,
            max_rows,
            pct,
        )
    df = db.execute(f"SELECT {collist} FROM read_parquet('{uri}') {sample}").fetchdf()
    for c in NUM_FEATURES:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in CAT_FEATURES:
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("NA")
    log.info(
        "base carregada: %d linhas x %d colunas | taxa=%.1f%%",
        len(df),
        len(df.columns),
        df[TARGET].mean() * 100,
    )
    return df


def make_xy(df: pd.DataFrame, cat_cols, num_cols):
    X = df[cat_cols + num_cols].copy()
    for c in num_cols:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    for c in cat_cols:
        X[c] = X[c].astype("string").fillna("NA")
    y = df[TARGET].astype(int).to_numpy()
    groups = df[GROUP].to_numpy()
    return X, y, groups


def build_preprocessor(
    cat_cols, num_cols, max_categories: int = 30
) -> ColumnTransformer:
    cat = Pipeline(
        [
            ("imp", SimpleImputer(strategy="constant", fill_value="NA")),
            (
                "oh",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    max_categories=max_categories,
                    sparse_output=True,
                ),
            ),
        ]
    )
    num = Pipeline(
        [
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler(with_mean=False)),
        ]
    )
    return ColumnTransformer(
        [("cat", cat, cat_cols), ("num", num, num_cols)],
        remainder="drop",
        sparse_threshold=1.0,
    )
