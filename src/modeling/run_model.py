"""Pipeline ponta a ponta: labels -> features -> consolidação -> treino/avaliação."""

from src.utils.io import load_config
from src.utils.logging import get_logger


log = get_logger("modeling")


def main(do_labels=False, do_features=False, do_consolidate=True, do_train=True):
    cfg = load_config("settings")
    if do_labels:
        from src.features.run_labels import main as gen_labels

        gen_labels()
    if do_features:
        from src.features.run_features import main as gen_features

        gen_features()
    if do_consolidate:
        from src.modeling.consolidate import consolidate

        consolidate(cfg)
    if do_train:
        from src.modeling.train import train

        train(cfg)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--features", action="store_true")
    ap.add_argument("--no-consolidate", action="store_true")
    ap.add_argument("--no-train", action="store_true")
    a = ap.parse_args()
    main(
        do_labels=a.labels,
        do_features=a.features,
        do_consolidate=not a.no_consolidate,
        do_train=not a.no_train,
    )
