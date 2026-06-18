from datetime import datetime

from src.ingestion.base import fetch_to_buffer
from src.utils.logging import get_logger
from src.utils.minio_client import get_client, upload_buffer


log = get_logger("sicor")


def _basename(url: str) -> str:
    return url.split("?")[0].rstrip("/").split("/")[-1]


def _freq_match(grp: dict, only_frequency: str | None) -> bool:
    return only_frequency is None or grp.get("frequency") == only_frequency


def _ingest_static(client, bucket, table, snapshot):
    url = table["url"]
    key = f"sicor/{table['name']}/ingest_month={snapshot}/{_basename(url)}"
    buf = fetch_to_buffer(url)
    if buf is None:
        return
    upload_buffer(client, bucket, key, buf)


def _ingest_temporal(client, bucket, table, start_year, current_year, snapshot):
    exc = table.get("exceptions") or {}
    exc_years = set(exc.get("years", []))
    for year in range(start_year, current_year + 1):
        if str(year) in exc_years:
            urls = [
                exc["url"].format(year=year, period=period)
                for period in exc.get("periods", [])
            ]
        else:
            urls = [table["url"].format(year=year)]
        for url in urls:
            key = f"sicor/{table['name']}/year={year}/ingest_month={snapshot}/{_basename(url)}"
            buf = fetch_to_buffer(url)
            if buf is None:
                continue
            upload_buffer(client, bucket, key, buf)


def ingest(cfg: dict, src: dict, only_frequency: str | None = None) -> None:
    bucket = cfg["object_storage"]["buckets"]["bronze"]
    client = get_client(cfg)
    date = datetime.now()
    snapshot = date.strftime("%Y-%m")
    current_year = date.year

    for category in ("dominios", "operacionais"):
        grp = src.get(category)
        if not grp:
            continue
        if not _freq_match(grp, only_frequency):
            log.info(
                "Pulando categoria %s (frequencia %s não bate com filtro %s)",
                category,
                grp.get("frequency"),
                only_frequency,
            )
            continue
        for table in grp.get("tables", []):
            if not table.get("enabled"):
                log.info("Pulando tabela %s (desabilitada)", table.get("name"))
                continue
            try:
                _ingest_static(client, bucket, table, snapshot)
            except Exception as e:
                log.error("Erro ao ingerir tabela %s: %s", table.get("name"), e)

    grp = src.get("temporais")
    if grp and not _freq_match(grp, only_frequency):
        log.info(
            "Pulando categoria temporais (frequencia %s não bate com filtro %s)",
            grp.get("frequency"),
            only_frequency,
        )
    elif grp:
        start_year = grp.get("start_year", current_year)
        for table in grp.get("tables", []):
            if not table.get("enabled"):
                log.info("Pulando tabela %s (desabilitada)", table.get("name"))
                continue
            try:
                _ingest_temporal(
                    client, bucket, table, start_year, current_year, snapshot
                )
            except Exception as e:
                log.error("Erro ao ingerir tabela %s: %s", table.get("name"), e)
