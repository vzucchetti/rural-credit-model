# %%
from __future__ import annotations
import os
from io import BytesIO
from minio import Minio
from minio.error import S3Error
from src.utils.io import load_config
from src.utils.logging import get_logger


log = get_logger("storage")


def get_client(cfg: dict | None = None):
    cfg = cfg or load_config("settings")
    os_cfg = cfg["object_storage"]

    endpoint = (
        os_cfg.get("endpoint_url", "http://localhost:9000")
        .replace("http://", "")
        .replace("https://", "")
    )
    access_key = os.getenv("MINIO_ROOT_USER")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD")
    region = os_cfg.get("region", "us-east-1")
    secure = bool(os_cfg.get("secure", False))

    try:
        client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            secure=secure,
        )
        log.info("Conectado ao MinIO em %s", endpoint)
        return client
    except S3Error as e:
        log.error("Erro ao conectar ao MinIO: %s", e)
        raise e


def ensure_bucket(client, bucket: str):
    try:
        if not client.bucket_exists(bucket):
            log.info("Bucket %s não encontrado, criando...", bucket)
            client.make_bucket(bucket)
            log.info("Bucket criado com sucesso: %s", bucket)
        else:
            log.info("Bucket já existe: %s", bucket)
    except S3Error as e:
        log.error("Erro ao criar/verificar bucket %s: %s", bucket, e)
        raise e


def ensure_buckets(client, cfg: dict | None = None):
    cfg = cfg or load_config("settings")
    for b in cfg["object_storage"]["buckets"].values():
        ensure_bucket(client, b)


def upload_buffer(
    client: Minio, bucket_name: str, object_name: str, buffer: BytesIO
) -> None:
    try:
        buffer.seek(0)
        client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=buffer,
            length=buffer.getbuffer().nbytes,
            content_type="application/gzip",
        )
        log.info("Upload concluído: s3://%s/%s", bucket_name, object_name)
    except S3Error as e:
        log.error(
            "Erro ao fazer upload para s3://%s/%s: %s", bucket_name, object_name, e
        )
        raise e


# def upload_file(client, local_path: str, bucket: str, key: str):
#     client.upload_file(str(local_path), bucket, key)
#     log.info("Upload s3://%s/%s", bucket, key)


# def download_file(client, bucket: str, key: str, local_path: str):
#     import pathlib
#     pathlib.Path(local_path).parent.mkdir(parents=True, exist_ok=True)
#     client.download_file(bucket, key, str(local_path))


# def list_objects(client, bucket: str, prefix: str = ""):
#     paginator = client.get_paginator("list_objects_v2")
#     keys = []
#     for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
#         keys += [o["Key"] for o in page.get("Contents", [])]
#     return keys
