# %%
from __future__ import annotations
import os
import pathlib
import yaml
from dotenv import load_dotenv


load_dotenv()
_CFG_DIR = pathlib.Path(os.getenv("CFG_PATH"))


def _expand(obj):
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        return os.getenv(obj[2:-1], "")
    return obj


def load_config(name: str = "settings") -> dict:
    with open(_CFG_DIR / f"{name}.yaml", encoding="utf-8") as fh:
        return _expand(yaml.safe_load(fh))


# def configure_duckdb_s3(con, cfg: dict | None = None):
#     """Configura o DuckDB para ler/gravar Parquet no MinIO/S3 (read_parquet('s3://...'))."""
#     cfg = cfg or load_config("settings")
#     os_cfg = cfg.get("object_storage", {})
#     if not os_cfg.get("enabled"):
#         return con
#     endpoint = (os_cfg.get("endpoint_url") or "").replace("http://", "").replace("https://", "")
#     con.execute("INSTALL httpfs; LOAD httpfs;")
#     con.execute("SET s3_url_style='path';")           # MinIO usa path-style
#     con.execute(f"SET s3_endpoint='{endpoint}';")
#     con.execute(f"SET s3_region='{os_cfg.get('region', 'us-east-1')}';")
#     con.execute(f"SET s3_access_key_id='{os.getenv('AWS_ACCESS_KEY_ID', '')}';")
#     con.execute(f"SET s3_secret_access_key='{os.getenv('AWS_SECRET_ACCESS_KEY', '')}';")
#     con.execute(f"SET s3_use_ssl={'true' if os_cfg.get('use_ssl') else 'false'};")
#     return con


# def duckdb_conn():
#     import duckdb
#     cfg = load_config("settings")
#     con = duckdb.connect(cfg["paths"]["duckdb"])
#     con.execute("INSTALL httpfs; LOAD httpfs;")
#     configure_duckdb_s3(con, cfg)
#     return con


# def write_parquet(df, path: str, partition_cols=None):
#     p = pathlib.Path(path)
#     p.parent.mkdir(parents=True, exist_ok=True)
#     try:
#         import polars as pl
#         if isinstance(df, pl.DataFrame):
#             df.write_parquet(path)
#             return
#     except ImportError:
#         pass
#     df.to_parquet(path, index=False, partition_cols=partition_cols)
