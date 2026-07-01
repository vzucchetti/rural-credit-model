from __future__ import annotations
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from src.features.registry import TARGET, GROUP
from src.utils.io import duckdb_s3, load_config
from src.utils.logging import get_logger


log = get_logger("modeling")


def load_base(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config("settings")
    uri = cfg["modeling"]["base_uri"]
    return duckdb_s3(cfg).execute(f"SELECT * FROM read_parquet('{uri}')").fetchdf()


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
