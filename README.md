repositório desenvolvido utilizando o `poetry`. makefile configura a variável `PY` para rodar `poetry run python`. caso não queira ou não esteja utilizando o `poetry`, configure a variável para rodar somente com `python`.

utilizando pre-commit com ruff e commitizen para revisão e documentação do repositório.

Use o arquivo `.env.example` como exemplo para configuração das suas variáveis de ambiente em `.env`

MinIO como *Object Storage*, simulando estrutura de Data Lake para armazenamento dos dados.

`make minio-up` ou manualmente `docker compose up -d minio` para subir a aplicação do MinIO para armazenamento dos arquivos de dados em estrutura medallion.

`make minio-init` ou manualmente `scripts/minio_bootstrap.py` para criar os buckets de armazenamento dos arquivos no MinIO, definidos em config/settings.yaml.
Os pré-requisitos são estar com o MinIO no ar e o arquivo .env preenchido.


src/utils
**logging.py**:
**io.py**:
**orchestration.py**:
**minio_client.py**:

src/ingestion
**base.py**: funções comuns para ingestão de arquivos e armazenamento no MinIO
**sicor.py**:
**run_ingestion.py**:

src/transform
**sicor_treat.py**:
**run_transform.py**:
