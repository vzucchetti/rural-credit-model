"""Armazena e lê os resultados de cada execução de treino (para o Streamlit).
Cada run = 1 JSON em {runs_uri}. Funciona em s3:// (MinIO) ou caminho local."""

from __future__ import annotations
import json
from datetime import datetime, timezone
from io import BytesIO

from src.utils.logging import get_logger


log = get_logger("modeling")


def _is_s3(uri: str) -> bool:
    return uri.startswith("s3://")


def _bucket_key(uri: str):
    rest = uri[len("s3://") :]
    b, _, k = rest.partition("/")
    return b, k


def save_run(record: dict, cfg: dict, client=None) -> str:
    runs_uri = cfg["modeling"]["runs_uri"].rstrip("/") + "/"
    rid = record.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    record["run_id"] = rid
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    data = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
    if _is_s3(runs_uri):
        from src.utils.minio_client import get_client

        client = client or get_client(cfg)
        bucket, prefix = _bucket_key(runs_uri)
        client.put_object(
            bucket,
            f"{prefix}{rid}.json",
            BytesIO(data),
            length=len(data),
            content_type="application/json",
        )
    else:
        import os

        os.makedirs(runs_uri, exist_ok=True)
        with open(f"{runs_uri}{rid}.json", "wb") as fh:
            fh.write(data)
    log.info("run salva: %s", rid)
    return rid


def load_runs(cfg: dict, client=None) -> list[dict]:
    runs_uri = cfg["modeling"]["runs_uri"].rstrip("/") + "/"
    out = []
    if _is_s3(runs_uri):
        from src.utils.minio_client import get_client

        client = client or get_client(cfg)
        bucket, prefix = _bucket_key(runs_uri)
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
            if obj.object_name.endswith(".json"):
                raw = client.get_object(bucket, obj.object_name).read()
                out.append(json.loads(raw))
    else:
        import glob

        for p in glob.glob(f"{runs_uri}*.json"):
            with open(p, encoding="utf-8") as fh:
                out.append(json.load(fh))
    return sorted(out, key=lambda r: r.get("created_at", ""))
