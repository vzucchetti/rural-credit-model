from src.utils.io import load_config
from src.utils.minio_client import get_client, ensure_buckets
from src.utils.logging import get_logger


log = get_logger("minio_bootstrap")


def main():
    cfg = load_config("settings")
    if not cfg["object_storage"].get("enabled"):
        log.warning(
            "object_storage.enabled = false em settings.yaml. "
            "Ligue para usar o MinIO."
        )
        return
    cli = get_client(cfg)
    ensure_buckets(cli, cfg)
    log.info("Buckets prontos: %s", list(cfg["object_storage"]["buckets"].values()))


if __name__ == "__main__":
    main()
