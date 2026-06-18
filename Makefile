PY=python
.PHONY: help sizing minio-up minio-init ingest ingest-sicor transform features train dashboard test lint

help:
	@echo "Alvos: minio-up | minio-init"
# | sizing | ingest | ingest-sicor | transform | features | train | dashboard | test"

minio-up:
	docker compose up -d minio

minio-init:
	PYTHONPATH=. $(PY) scripts/minio_bootstrap.py

# sizing:
# 	$(PY) -m banri_agro.utils.sizing

# ingest:
# 	$(PY) -m banri_agro.ingestion.run_all

# ingest-sicor:
# 	$(PY) -m banri_agro.ingestion.sicor

# transform:
# 	cd dbt && dbt run && dbt test

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
