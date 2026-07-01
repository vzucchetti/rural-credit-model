from __future__ import annotations

from src.utils.io import duckdb_s3, load_config
from src.utils.logging import get_logger


log = get_logger("labels")


def _base_cte(inpath: str, def_sit: list[str]) -> str:
    lst = ", ".join("'" + s.replace("'", "''") + "'" for s in def_sit)
    return f"""
      op AS (
        SELECT "#REF_BACEN" AS ref_bacen, NU_ORDEM AS nu_ordem, DT_EMISSAO
        FROM read_parquet('{inpath}operacao_basica.parquet')
      ),
      def_codes AS (
        SELECT "#CODIGO" AS cod FROM read_parquet('{inpath}situacao_operacao.parquet')
        WHERE DESCRICAO IN ({lst})
      ),
      sld AS (
        SELECT "#REF_BACEN" AS ref_bacen, NU_ORDEM AS nu_ordem,
               ANO_BASE, MES_BASE, CD_SITUACAO_OPERACAO
        FROM read_parquet('{inpath}saldos.parquet')
      ),
      mut AS (
        SELECT "REF_BACEN" AS ref_bacen, CD_CPF_CNPJ AS mutuario
        FROM read_parquet('{inpath}mutuarios.parquet')
      ),
      base AS (
        SELECT s.ref_bacen, s.nu_ordem, m.mutuario,
               datediff('month', date_trunc('month', o.DT_EMISSAO),
                        make_date(TRY_CAST(s.ANO_BASE AS INT), TRY_CAST(s.MES_BASE AS INT), 1)) AS delta,
               CASE WHEN s.CD_SITUACAO_OPERACAO IN (SELECT cod FROM def_codes) THEN 1 ELSE 0 END AS situacao
        FROM sld s
        JOIN op o ON s.ref_bacen = o.ref_bacen AND s.nu_ordem = o.nu_ordem
        JOIN mut m ON s.ref_bacen = m.ref_bacen
      )"""


def build_target(cfg: dict | None = None, horizon: int | None = None) -> str:
    cfg = cfg or load_config("settings")
    lc = cfg["labels"]
    inpath = cfg["paths"]["silver_sicor"]
    labels = cfg["paths"]["labels"]
    H = horizon or lc.get("horizon", 18)
    out = f"{labels}target_{H}m.parquet"
    db = duckdb_s3(cfg)
    db.execute(f"""
      COPY (
        WITH {_base_cte(inpath, lc["def_situacoes"])}
        SELECT ref_bacen, nu_ordem, mutuario,
               MAX(CASE WHEN delta BETWEEN 0 AND {H} THEN situacao ELSE 0 END) AS target_{H}m
        FROM base
        GROUP BY ref_bacen, nu_ordem, mutuario
      ) TO '{out}' (FORMAT PARQUET)
    """)
    n = db.execute(
        f"SELECT COUNT(*), AVG(target_{H}m) FROM read_parquet('{out}')"
    ).fetchone()
    log.info("target_%dm -> %s | linhas=%d taxa=%.4f", H, out, n[0], n[1])
    return out


def build_matriz(cfg: dict | None = None, n_deltas: int | None = None) -> str:
    cfg = cfg or load_config("settings")
    lc = cfg["labels"]
    inpath = cfg["paths"]["silver_sicor"]
    labels = cfg["paths"]["labels"]
    N = n_deltas or lc.get("n_deltas", 24)
    case_cols = ",\n         ".join(
        f'CASE WHEN first_default IS NOT NULL AND {d} >= first_default THEN 1 ELSE 0 END AS "{d}"'
        for d in range(0, N + 1)
    )
    out = f"{labels}base_safra.parquet"
    db = duckdb_s3(cfg)
    db.execute(f"""
      COPY (
        WITH {_base_cte(inpath, lc["def_situacoes"])},
        fd AS (
          SELECT ref_bacen, nu_ordem, mutuario,
                 MIN(CASE WHEN situacao = 1 THEN delta END) AS first_default
          FROM base WHERE delta BETWEEN 0 AND {N}
          GROUP BY ref_bacen, nu_ordem, mutuario
        )
        SELECT ref_bacen, nu_ordem, mutuario, {case_cols}
        FROM fd
      ) TO '{out}' (FORMAT PARQUET)
    """)
    log.info("base_safra -> %s (deltas 0..%d)", out, N)
    return out
