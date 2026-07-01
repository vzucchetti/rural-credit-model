from __future__ import annotations
from src.features.features_sql import FEATURE_SQL
from src.features.registry import FEATURE_SPEC, FILE_OF
from src.utils.io import duckdb_s3, load_config
from src.utils.logging import get_logger


log = get_logger("features")


def build_one(db, col: str, cfg: dict) -> str:
    sql = FEATURE_SQL.get(col)
    if not sql:
        raise NotImplementedError(
            f"SQL da feature '{col}' não registrada. Cole a SQL do seu notebook em "
            f"src/features/features_sql.py (chave '{col}')."
        )
    inpath = cfg["paths"]["silver_sicor"]
    labels = cfg["paths"]["labels"]
    features = cfg["paths"]["features"]
    out = f"{features}{FILE_OF[col]}.parquet"
    db.execute(sql.format(inpath=inpath, labels=labels, features=features, out=out))
    log.info("feature %s -> %s", col, out)
    return out


def build_all(cfg: dict | None = None, only: list[str] | None = None) -> None:
    cfg = cfg or load_config("settings")
    db = duckdb_s3(cfg)
    cols = only or [c for _, _, c, _ in FEATURE_SPEC]
    for col in cols:
        try:
            build_one(db, col, cfg)
        except NotImplementedError as e:
            log.warning("%s", e)
