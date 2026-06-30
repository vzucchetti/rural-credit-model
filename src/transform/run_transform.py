from __future__ import annotations
import argparse
import os

from src.transform.sicor_treat import transform
from src.utils.io import load_config
from src.utils.logging import get_logger


log = get_logger("transform")


def main(only_frequency: str | None = None):
    if only_frequency is None:
        only_frequency = os.getenv("INGEST_FREQUENCY") or None
    cfg = load_config("settings")
    sources = load_config("sources")
    active = [
        (n, c) for n, c in sources.items() if isinstance(c, dict) and c.get("enabled")
    ]
    if not active:
        log.warning("Nenhuma fonte ativa em sources.yaml. Verifique a configuração..")
        return
    for name, src_cfg in active:
        log.info(
            "Transform: fonte=%s | filtro de frequencia=%s",
            name,
            only_frequency or "(todas)",
        )
        transform(cfg, name, src_cfg, only_frequency=only_frequency)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Transformação bronze -> silver (Parquet por tabela)"
    )
    ap.add_argument("--frequency", default=None, help="monthly | semi-annual")
    args = ap.parse_args()
    main(only_frequency=args.frequency)
