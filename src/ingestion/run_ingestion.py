# %%
from __future__ import annotations
import argparse
import importlib
import os
from src.utils.io import load_config
from src.utils.logging import get_logger

# %%
log = get_logger("ingestion_all")


def main(only_frequency: str | None = None):
    if only_frequency is None:
        only_frequency = os.getenv("INGEST_FREQUENCY") or None

    cfg = load_config("settings")
    src = load_config("sources")
    active = [
        (name, c) for name, c in src.items() if isinstance(c, dict) and c.get("enabled")
    ]
    if not active:
        log.warning(
            "Nenhuma fonte de dados ativa em sources.yaml. Verifique a configuração."
        )
        return
    log.info("Filtro de frequência: %s", only_frequency or "(todas)")
    for name, src_cfg in active:
        try:
            mod = importlib.import_module(f"src.ingestion.{name}")
            log.info("Iniciando ingestão da fonte: %s", name)
            mod.ingest(cfg, src_cfg, only_frequency=only_frequency)
            log.info("Ingestão concluída com sucesso: %s", name)
        except ModuleNotFoundError:
            log.error("Erro: Módulo não encontrado para a fonte: %s", name)
        except AttributeError:
            log.error("Erro: Função 'ingest' não encontrada no módulo: %s", name)
        except Exception as e:
            log.error("Falha em %s: %s", name, e)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingestão SICOR -> bronze (MinIO)")
    ap.add_argument(
        "--frequency",
        dest="frequency",
        default=None,
        help="filtra famílias por cadência: monthly | semi-annual",
    )
    args = ap.parse_args()
    main(only_frequency=args.frequency)
