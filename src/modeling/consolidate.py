from __future__ import annotations
import os
import tempfile

from src.features.registry import FEATURE_SPEC, TARGET
from src.utils.io import duckdb_s3, load_config
from src.utils.logging import get_logger


log = get_logger("features")


KEYCANDS = ("ref_bacen", "nu_ordem", "mutuario")


def _cols(db, uri: str) -> list[str]:
    return [
        r[0]
        for r in db.execute(f"DESCRIBE SELECT * FROM read_parquet('{uri}')").fetchall()
    ]


def _discover(db, features: str, tgt_cols: set) -> list[dict]:
    """Resolve, por feature, as chaves de junção e a coluna real (a renomear p/ registry)."""
    specs = []
    for fname, _, col, _ in FEATURE_SPEC:
        uri = f"{features}{fname}.parquet"
        try:
            fcols = _cols(db, uri)
        except Exception as e:  # noqa: BLE001
            log.warning("feature '%s' inacessível (%s) — pulada", fname, e)
            continue
        fset = set(fcols)
        keys = [k for k in KEYCANDS if k in fset and k in tgt_cols]
        if not keys:
            log.warning(
                "feature '%s' sem chave em comum (cols=%s) — pulada", fname, fcols
            )
            continue
        feat = (
            col
            if col in fset
            else next((c for c in fcols if c not in KEYCANDS and c != TARGET), None)
        )
        if feat is None:
            log.warning("feature '%s' sem coluna de atributo — pulada", fname)
            continue
        specs.append({"uri": uri, "keys": keys, "feat": feat, "col": col})
        log.info(
            "feature '%s': chaves=%s coluna_real='%s' -> '%s'", fname, keys, feat, col
        )
    return specs


def _sql_local(p: str) -> str:
    return p.replace(os.sep, "/")


def consolidate(cfg: dict | None = None) -> str:
    cfg = cfg or load_config("settings")
    mc = cfg.get("modeling", {})
    batch_size = int(mc.get("consolidate_batch_size", 6))
    log.info("consolidate (discovery + lotes de %d) iniciando", batch_size)

    labels = cfg["paths"]["labels"]
    features = cfg["paths"]["features"]
    out = cfg["modeling"]["base_uri"]
    db = duckdb_s3(cfg)

    tgt_uri = f"{labels}target_18m.parquet"
    tgt_cols = set(_cols(db, tgt_uri))
    specs = _discover(db, features, tgt_cols)
    if not specs:
        raise RuntimeError("Nenhuma feature válida para consolidar.")

    tmp_dir = (cfg.get("paths", {}) or {}).get("duckdb_temp") or tempfile.gettempdir()
    tmp_dir = os.path.join(tmp_dir, "consolidate_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    batches = [specs[i : i + batch_size] for i in range(0, len(specs), batch_size)]
    acc = tgt_uri
    tmp_files, usados = [], []
    try:
        for i, batch in enumerate(batches):
            last = i == len(batches) - 1
            dest = out if last else os.path.join(tmp_dir, f"cons_step_{i}.parquet")
            ctes, joins, sel = [], [], []
            for sp in batch:
                a = f'f_{sp["col"]}'
                kl = ", ".join(sp["keys"])
                ctes.append(
                    f'{a} AS (SELECT {kl}, any_value("{sp["feat"]}") AS "{sp["col"]}" '
                    f"FROM read_parquet('{sp['uri']}') GROUP BY {kl})"
                )
                joins.append(f"LEFT JOIN {a} USING ({kl})")
                sel.append(f'{a}."{sp["col"]}"')
                usados.append(
                    sp["col"]
                    if sp["feat"] == sp["col"]
                    else f'{sp["col"]}(<-{sp["feat"]})'
                )
            db.execute(f"""
              COPY (
                WITH {", ".join(ctes)}
                SELECT acc.*, {", ".join(sel)}
                FROM read_parquet('{_sql_local(acc)}') acc
                {" ".join(joins)}
              ) TO '{_sql_local(dest)}' (FORMAT PARQUET)
            """)
            log.info(
                "lote %d/%d gravado (%d features) -> %s",
                i + 1,
                len(batches),
                len(batch),
                dest,
            )
            if not last:
                tmp_files.append(dest)
            acc = dest
    finally:
        for f in tmp_files:
            try:
                os.remove(f)
            except OSError:
                pass

    n = db.execute(
        f"SELECT COUNT(*), AVG({TARGET}) FROM read_parquet('{out}')"
    ).fetchone()
    log.info(
        "Base consolidada -> %s | linhas=%d taxa=%.4f | %d features: %s",
        out,
        n[0],
        n[1],
        len(usados),
        ", ".join(usados),
    )
    return out
