from src.features.build_features import build_all
from src.utils.io import load_config
from src.utils.logging import get_logger


log = get_logger("features")


def main():
    cfg = load_config("settings")
    log.info("Iniciando geração das features.")
    build_all(cfg)
    log.info("Features registradas geradas.")


if __name__ == "__main__":
    main()
