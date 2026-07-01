from src.features.build_labels import build_target, build_matriz
from src.utils.io import load_config
from src.utils.logging import get_logger


log = get_logger("labels")


def main():
    cfg = load_config("settings")
    log.info("Iniciando geração de labels.")
    build_target(cfg)
    build_matriz(cfg)
    log.info("Labels gerados.")


if __name__ == "__main__":
    main()
