PY=poetry run python
.PHONY: help sizing minio-up minio-init ingest ingest-monthly ingest-semiannual features train dashboard test lint

help:
	@echo "Alvos: minio-up | minio-init | ingest | ingest-monthly | ingest-semiannual | transform | transform-monthly | transform-semiannual"

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

# features:
# 	$(PY) -m banri_agro.features.feature_engineering

# train:
# 	$(PY) -m banri_agro.models.train

# dashboard:
# 	streamlit run dashboards/streamlit_app.py

# test:
# 	pytest -q

# lint:
# 	$(PY) -m pyflakes src || true
