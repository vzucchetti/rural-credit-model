PY=poetry run python
.PHONY: help sizing minio-up minio-init ingest ingest-monthly ingest-semiannual transform transform-monthly transform-semiannual labels features consolidate train dashboard

help:
	@echo "Alvos: minio-up | minio-init | ingest | ingest-monthly | ingest-semiannual | transform | transform-monthly | transform-semiannual | labels | features | consolidate | train | dashboard"

minio-up:
	docker compose up -d minio

minio-init:
	PYTHONPATH=. $(PY) scripts/minio_bootstrap.py

ingest:
	PYTHONPATH=. $(PY) -m src.ingestion.run_ingestion

ingest-monthly:
	PYTHONPATH=. $(PY) -m src.ingestion.run_ingestion --frequency monthly

ingest-semiannual:
	PYTHONPATH=. $(PY) -m src.ingestion.run_ingestion --frequency semi-annual

transform:
	PYTHONPATH=. $(PY) -m src.transform.run_transform

transform-monthly:
	PYTHONPATH=. $(PY) -m src.transform.run_transform --frequency monthly

transform-semiannual:
	PYTHONPATH=. $(PY) -m src.transform.run_transform --frequency semi-annual

labels:
	PYTHONPATH=. $(PY) -m src.features.run_labels

features:
	PYTHONPATH=. $(PY) -m src.features.run_features

consolidate:
	PYTHONPATH=. $(PY) -m src.modeling.run_model --no-train

train:
	PYTHONPATH=. $(PY) -m src.modeling.run_model

train-temporal:
	PYTHONPATH=. $(PY) -m src.modeling.train_temporal

dashboard:
	PYTHONPATH=. $(PY) -m streamlit run app/dashboard.py

# test:
# 	pytest -q

# lint:
# 	$(PY) -m pyflakes src || true
