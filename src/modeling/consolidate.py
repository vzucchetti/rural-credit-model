from __future__ import annotations
from src.features.registry import FEATURE_SPEC, TARGET
from src.utils.io import duckdb_s3, load_config
from src.utils.logging import get_logger


log = get_logger("features")


def consolidate(cfg: dict | None = None) -> str:
    cfg = cfg or load_config("settings")
    labels = cfg["paths"]["labels"]
    features = cfg["paths"]["features"]
    out = cfg["modeling"]["base_uri"]
    ctes, joins, cols = [], [], []
    for fname, keys, col, _ in FEATURE_SPEC:
        alias = f"f_{col}"
        klist = ", ".join(keys)
        ctes.append(
            f'{alias} AS (SELECT {klist}, any_value("{col}") AS "{col}" '
            f"FROM read_parquet('{features}{fname}.parquet') GROUP BY {klist})"
        )
        joins.append(f"LEFT JOIN {alias} USING ({klist})")
        cols.append(f'{alias}."{col}"')
    db = duckdb_s3(cfg)
    db.execute(f"""
      COPY (
        WITH {", ".join(ctes)}
        SELECT t.ref_bacen, t.nu_ordem, t.mutuario, t.{TARGET}, {", ".join(cols)}
        FROM read_parquet('{labels}target_18m.parquet') t
        {" ".join(joins)}
      ) TO '{out}' (FORMAT PARQUET)
    """)
    n = db.execute(
        f"SELECT COUNT(*), AVG({TARGET}) FROM read_parquet('{out}')"
    ).fetchone()
    log.info("Base consolidada -> %s | linhas=%d taxa=%.4f", out, n[0], n[1])
    return out
