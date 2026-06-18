Coletando dados a partir de 2015 por representar uma boa amostragem temporal e evitar as adaptação para anos em que os dados foram disponibilizados por semestre (2013, 2015)

Use o arquivo `.env.example` como exemplo para configuração das suas variáveis de ambiente em `.env`

MinIO como *Object Storage*, simulando estrutura de Data Lake para armazenamento dos dados.

`make minio-up` ou manualmente `docker compose up -d minio` para subir a aplicação do MinIO para armazenamento dos arquivos de dados em estrutura medallion.

`make minio-init` ou manualmente `scripts/minio_bootstrap.py` para criar os buckets de armazenamento dos arquivos no MinIO, definidos em config/settings.yaml.
Os pré-requisitos são estar com o MinIO no ar e o arquivo .env preenchido.


src/utils

src/ingestion
**base.py**: funções comum para ingestão de arquivos com requests ou por streaming
