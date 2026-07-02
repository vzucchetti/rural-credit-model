"""Agregações de negócio para o dashboard: concessões e inadimplência por dimensão.

Fonte: base_modelagem (dedup no grão de OPERAÇÃO ref_bacen+nu_ordem) + safra derivada
de DT_EMISSAO. A curva de safra (vintage) vem da matriz base_safra.
Retorna DataFrames pequenos (agregados) — pesado fica no DuckDB, não em pandas.
"""

from __future__ import annotations
from src.utils.io import duckdb_s3, load_config

DIMS = ["safra", "uf", "finalidade", "atividade", "produto"]


def _op_cols(db, silver: str) -> list[str]:
    return [
        r[0]
        for r in db.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{silver}operacao_basica.parquet')"
        ).fetchall()
    ]


def _opbase_ddl(cfg: dict, valcol: str) -> str:
    base = cfg["modeling"]["base_uri"]
    silver = cfg["paths"]["silver_sicor"]
    cut = cfg["modeling"].get("safra_cutoff_month", 7)
    return f"""
      CREATE OR REPLACE TEMP TABLE opbase AS
      WITH op AS (
        SELECT ref_bacen, nu_ordem,
               any_value(uf) AS uf, any_value(finalidade) AS finalidade,
               any_value(atividade) AS atividade, any_value(produto) AS produto,
               MAX(target_18m) AS inadimplente
        FROM read_parquet('{base}') GROUP BY ref_bacen, nu_ordem
      ),
      saf AS (
        SELECT ob."#REF_BACEN" AS ref_bacen, ob."NU_ORDEM" AS nu_ordem,
               year(ob.DT_EMISSAO) - CAST(month(ob.DT_EMISSAO) < {cut} AS INTEGER) AS safra,
               TRY_CAST(ob."{valcol}" AS DOUBLE) AS valor
        FROM read_parquet('{silver}operacao_basica.parquet') AS ob
      )
      SELECT op.ref_bacen, op.nu_ordem, op.uf, op.finalidade, op.atividade,
             op.produto, op.inadimplente, saf.safra, saf.valor
      FROM op LEFT JOIN saf USING (ref_bacen, nu_ordem)
    """


def load_aggregates(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config("settings")
    silver = cfg["paths"]["silver_sicor"]
    valcol = cfg["modeling"].get("valor_credito_col", "VL_PARC_CREDITO")
    db = duckdb_s3(cfg)
    opcols = _op_cols(db, silver)
    if valcol not in opcols:
        vls = [c for c in opcols if c.upper().startswith("VL_")]
        raise ValueError(
            f"Coluna de valor do crédito '{valcol}' não existe em operacao_basica. "
            f"Defina modeling.valor_credito_col com uma destas colunas VL_: {vls}"
        )
    db.execute(_opbase_ddl(cfg, valcol))
    out = {}
    for d in DIMS:
        order = "categoria" if d == "safra" else "volume DESC"
        out[d] = db.execute(f"""
            SELECT CAST({d} AS VARCHAR) AS categoria,
                   COUNT(*) AS concessoes,
                   SUM(valor) AS volume,
                   SUM(inadimplente) AS inadimplentes,
                   AVG(inadimplente) AS taxa
            FROM opbase WHERE {d} IS NOT NULL
            GROUP BY {d} ORDER BY {order}
        """).fetchdf()
    return out


def load_vintage(cfg: dict | None = None, n_deltas: int = 24) -> "object":
    """Curva de safra: inadimplência acumulada média por delta (mês após emissão), por safra."""
    cfg = cfg or load_config("settings")
    labels = cfg["paths"]["labels"]
    silver = cfg["paths"]["silver_sicor"]
    cut = cfg["modeling"].get("safra_cutoff_month", 7)
    base_safra = f"{labels}base_safra.parquet"
    db = duckdb_s3(cfg)
    cols = [
        r[0]
        for r in db.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{base_safra}')"
        ).fetchall()
    ]
    deltas = sorted([c for c in cols if c.isdigit()], key=int)[: n_deltas + 1]
    avg = ", ".join(f'AVG("{d}") AS "{d}"' for d in deltas)
    return db.execute(f"""
        WITH saf AS (
          SELECT ob."#REF_BACEN" AS ref_bacen, ob."NU_ORDEM" AS nu_ordem,
                 year(ob.DT_EMISSAO) - CAST(month(ob.DT_EMISSAO) < {cut} AS INTEGER) AS safra
          FROM read_parquet('{silver}operacao_basica.parquet') AS ob
        )
        SELECT saf.safra, {avg}
        FROM read_parquet('{base_safra}') bs
        LEFT JOIN saf USING (ref_bacen, nu_ordem)
        WHERE saf.safra IS NOT NULL
        GROUP BY saf.safra ORDER BY saf.safra
    """).fetchdf()
