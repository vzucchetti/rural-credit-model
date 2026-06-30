from __future__ import annotations
import os
import tempfile
import pathlib
import yaml
from dotenv import load_dotenv
import duckdb


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


def duckdb_mem(
    memory_limit: str | None = "8GB",
    temp_dir: str | None = None,
    threads: int | None = None,
) -> duckdb.DuckDBPyConnection:
    temp_dir = temp_dir or os.path.join(tempfile.gettempdir(), "duckdb_spill")
    os.makedirs(temp_dir, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{temp_dir.replace(os.sep, '/')}'")
    if memory_limit:
        con.execute(f"SET memory_limit='{memory_limit}'")
    if threads:
        con.execute(f"SET threads={threads}")
    con.execute("SET preserve_insertion_order=false")
    return con


def duckdb_s3(
    cfg: dict | None = None,
    memory_limit: str | None = "8GB",
    threads: int | None = None,
) -> duckdb.DuckDBPyConnection:
    """Configura o DuckDB para ler/gravar Parquet no MinIO/S3 em memória"""
    cfg = cfg or load_config("settings")
    os_cfg = cfg.get("object_storage", {})
    endpoint = (
        (os_cfg.get("endpoint_url") or "")
        .replace("http://", "")
        .replace("https://", "")
    )
    con = duckdb_mem(
        memory_limit=memory_limit,
        temp_dir=cfg["paths"].get("duckdb_temp", None),
        threads=threads,
    )
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_url_style='path';")
    con.execute(f"SET s3_endpoint='{endpoint}';")
    con.execute(f"SET s3_region='{os_cfg.get('region', 'us-east-1')}';")
    con.execute(f"SET s3_access_key_id='{os.getenv('MINIO_ROOT_USER', '')}';")
    con.execute(f"SET s3_secret_access_key='{os.getenv('MINIO_ROOT_PASSWORD', '')}';")
    con.execute(f"SET s3_use_ssl={'true' if os_cfg.get('secure') else 'false'};")
    return con
