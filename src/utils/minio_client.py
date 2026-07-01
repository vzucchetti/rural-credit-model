# %%
from __future__ import annotations
import os
from io import BytesIO
from minio import Minio
from minio.error import S3Error
from src.utils.io import load_config
from src.utils.logging import get_logger


log = get_logger("storage")


def get_client(cfg: dict | None = None) -> Minio:
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
        raise


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
        raise


def ensure_buckets(client, cfg: dict | None = None):
    cfg = cfg or load_config("settings")
    for b in cfg["object_storage"]["buckets"].values():
        ensure_bucket(client, b)


def upload_buffer(
    client: Minio,
    bucket_name: str,
    object_name: str,
    buffer: BytesIO,
    content_type: str,
) -> None:
    try:
        buffer.seek(0)
        client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=buffer,
            length=buffer.getbuffer().nbytes,
            content_type=content_type,
        )
        log.info("Upload concluído: s3://%s/%s", bucket_name, object_name)
    except S3Error as e:
        log.error(
            "Erro ao fazer upload para s3://%s/%s: %s", bucket_name, object_name, e
        )
        raise


def download_object(client: Minio, bucket: str, object: str):
    r = client.get_object(bucket, object)
    try:
        return r.read()
    finally:
        r.close()
        r.release_conn()


def list_objects(client, bucket: str, prefix: str = ""):
    return [
        o.object_name
        for o in client.list_objects(bucket, prefix=prefix, recursive=True)
    ]
