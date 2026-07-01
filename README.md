# Modelo Agnóstico de Crédito Rural

BI e Analytics para Crédito Rural — um modelo agnóstico de risco de crédito (PD) construído sobre os microdados públicos do SICOR/Bacen, com pipeline de dados em lakehouse medallion e dashboard de monitoramento em Streamlit.

> Contexto de negócio completo, referencial teórico e metodologia acadêmica em [`paper/projeto.tex`](paper/projeto.tex).

---

## Sumário

- [Visão geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Stack tecnológica](#stack-tecnológica)
- [Pré-requisitos](#pré-requisitos)
- [Configuração](#configuração)
- [Como executar](#como-executar)
- [Pipeline de dados](#pipeline-de-dados)
- [Modelagem](#modelagem)
- [Dashboard](#dashboard)
- [Status atual e limitações](#status-atual-e-limitações)

---

## Visão geral

O projeto propõe um ecossistema de BI e Analytics para subsidiar a entrada de uma instituição financeira no mercado de **crédito rural**, sem depender de histórico comportamental próprio do tomador. Para isso, utiliza como fundamento analítico os microdados públicos do **SICOR** (Sistema de Operações do Crédito Rural e do Proagro, mantido pelo Bacen), disponíveis desde 2013.

O repositório cobre a cadeia completa:

1. **Ingestão** dos microdados brutos do SICOR;
2. **Transformação** e padronização em uma base analítica estruturada;
3. **Construção de features e do alvo** de inadimplência;
4. **Modelagem preditiva de PD** (Probabilidade de Default), com validação k-fold e out-of-time;
5. **Dashboard de monitoramento** dos modelos.

## Arquitetura

Lakehouse medallion (bronze → silver → gold) sobre object storage (MinIO), com DuckDB como motor de processamento SQL direto sobre Parquet:

```
Fontes externas (SICOR/Bacen — CSV/GZ via HTTP)
        │
        ▼
Ingestão (httpx)  ───────────────►  MinIO bucket: bronze  (arquivos brutos, por ingest_month=)
        │
        ▼
Transformação (DuckDB)  ─────────►  MinIO bucket: silver  (Parquet tipado, 1 tabela por arquivo)
        │
        ▼
Features & labels (SQL/DuckDB) ──►  MinIO bucket: gold    (target_18m, base_safra, features)
        │
        ▼
Modelagem (scikit-learn / XGBoost) ─► Registro de execuções (JSON em gold/modeling/runs/)
        │
        ▼
Dashboard (Streamlit) ── lê as runs e exibe métricas/curvas
```

Cada camada é independente e pode ser executada isoladamente via `Makefile` (ver [Como executar](#como-executar)). A infraestrutura stateful (MinIO) roda localmente via Docker Compose; não há cluster distribuído — todo o processamento é feito em DuckDB embarcado.

## Estrutura do repositório

```
rural-credit-model/
├── app/
│   └── dashboard.py            # Dashboard Streamlit (validação k-fold e out-of-time)
├── config/
│   ├── settings.yaml           # Paths, buckets, parâmetros de labels e modelagem
│   └── sources.yaml            # Catálogo de fontes SICOR (tabelas, URLs, frequência, liga/desliga)
├── scripts/
│   └── minio_bootstrap.py      # Cria os buckets no MinIO a partir de settings.yaml
├── src/
│   ├── ingestion/
│   │   ├── base.py             # Download em streaming (httpx) com tratamento de 404/timeout
│   │   ├── sicor.py            # Ingestão das tabelas do SICOR -> bucket bronze
│   │   └── run_ingestion.py    # Entry point (make ingest)
│   ├── transform/
│   │   ├── sicor_treat.py      # Detecção de encoding/delimitador, casts, escrita em silver
│   │   └── run_transform.py    # Entry point (make transform)
│   ├── features/
│   │   ├── registry.py         # Catálogo de features (FEATURE_SPEC), alvo e chaves
│   │   ├── features_sql.py     # SQL de cada feature (lookups sobre operacao_basica/mutuarios)
│   │   ├── build_features.py   # Materializa cada feature registrada em gold
│   │   ├── build_labels.py     # Constrói target_18m e a matriz de safra (base_safra)
│   │   ├── run_features.py     # Entry point (make features)
│   │   └── run_labels.py       # Entry point (make labels)
│   ├── modeling/
│   │   ├── consolidate.py      # Junta labels + features na base de modelagem (gold)
│   │   ├── preprocessing.py    # Carrega a base, monta X/y/groups, ColumnTransformer
│   │   ├── feature_selection.py# Filtra colunas por nulidade/cardinalidade
│   │   ├── models.py           # NaiveSegmentRate, regressão logística, XGBoost
│   │   ├── metrics.py          # AUROC, KS, Brier, curvas ROC/KS/calibração
│   │   ├── train.py            # Validação k-fold agrupada por mutuário (make train)
│   │   ├── train_temporal.py   # Validação out-of-time por safra (make train-temporal)
│   │   ├── run_model.py        # Pipeline ponta a ponta: labels -> features -> consolidação -> treino
│   │   └── run_storage.py      # Persiste/lê execuções (runs) em JSON, local ou S3
│   └── utils/
│       ├── io.py                # load_config, conexões DuckDB (local e S3/MinIO)
│       ├── minio_client.py      # Cliente MinIO, buckets, upload/download/list
│       ├── orchestration.py     # Filtro de frequência (monthly | semi-annual)
│       └── logging.py           # Logger padrão do projeto
├── notebooks/
│   └── teste.ipynb              # Notebook de exploração
├── paper/                       # Projeto acadêmico (contexto, referencial teórico, metodologia)
├── docker-compose.yml            # Infraestrutura local: MinIO (MLflow planejado, comentado)
├── Makefile                       # Alvos de orquestração de todo o pipeline
├── pyproject.toml / poetry.lock   # Dependências (Poetry)
├── .env.example                   # Modelo de variáveis de ambiente
└── README.md
```

## Stack tecnológica

| Camada | Ferramenta |
|---|---|
| Linguagem / dependências | Python 3.12, Poetry |
| Object storage (data lake) | MinIO (via Docker Compose) |
| Motor de processamento | DuckDB (SQL direto sobre Parquet em S3) |
| Ingestão HTTP | httpx (streaming) |
| Modelagem | scikit-learn (regressão logística, `StratifiedGroupKFold`), XGBoost |
| Dashboard | Streamlit + Matplotlib |
| Qualidade de código | pre-commit, ruff, commitizen |
| Versionamento | Git |
| Rastreamento de experimentos | MLflow — **planejado, não ativado** (bloco comentado em `docker-compose.yml` e `config/settings.yaml`) |

## Pré-requisitos

- Python 3.12+
- [Poetry](https://python-poetry.org/)
- Docker e Docker Compose (para o MinIO)

## Configuração

1. Instale as dependências:

   ```bash
   poetry install
   ```

2. Copie `.env.example` para `.env` e preencha as variáveis. **Atenção:** o código (`src/utils/minio_client.py`, `src/utils/io.py`) lê as variáveis `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` e `CFG_PATH` — os nomes atuais em `.env.example` (`MINIO_ACCESS_KEY_ID`, `MINIO_SECRET_ACCESS_KEY`, `MINIO_ENDPOINT_URL`) estão desatualizados e precisam ser corrigidos/alinhados antes do primeiro uso.

   ```bash
   # .env
   MINIO_ROOT_USER=
   MINIO_ROOT_PASSWORD=
   CFG_PATH=config
   ```

3. Ajuste `config/settings.yaml` (buckets, parâmetros de labels/modelagem) e `config/sources.yaml` (quais tabelas do SICOR ficam ativas — cada tabela tem um flag `enabled` individual) conforme a necessidade.

4. Se o Makefile não for usado, defina `PY=python` (o padrão é `PY=poetry run python`).

## Como executar

Todos os alvos abaixo estão definidos no `Makefile`:

```bash
# 1. Sobe o MinIO
make minio-up

# 2. Cria os buckets (bronze/silver/gold) definidos em settings.yaml
make minio-init

# 3. Ingestão dos microdados do SICOR -> bronze
make ingest                 # todas as frequências
make ingest-monthly         # apenas tabelas mensais
make ingest-semiannual      # apenas tabelas semestrais

# 4. Transformação bronze -> silver (Parquet tipado)
make transform
make transform-monthly
make transform-semiannual

# 5. Construção do alvo e das features -> gold
make labels
make features

# 6. Consolidação da base de modelagem (sem treinar)
make consolidate

# 7. Treino e validação dos modelos
make train                  # k-fold agrupado por mutuário
make train-temporal         # out-of-time (walk-forward) por safra

# 8. Dashboard de monitoramento
make dashboard
```

`src/modeling/run_model.py` também expõe um pipeline ponta a ponta (labels → features → consolidação → treino), com flags `--labels`, `--features`, `--no-consolidate`, `--no-train`.

## Pipeline de dados

- **Ingestão** (`src/ingestion/`): `config/sources.yaml` cataloga as tabelas do SICOR (mais de 40 mapeadas, cada uma com URL, frequência e `enabled` individual). O download é feito em streaming via `httpx`, com tratamento de 404/timeout, e gravado sem transformação no bucket `bronze`, particionado por `ingest_month=`.
- **Transformação** (`src/transform/sicor_treat.py`): para cada tabela, o DuckDB lê o(s) arquivo(s) brutos mais recentes, detecta automaticamente **encoding** (utf-8/cp1252) e **delimitador**, aplica casts (data, double, string) por heurística de nome de coluna (prefixos `dt_`, `vl_`, `pc_`) ou por overrides explícitos em `sources.yaml`, e grava um Parquet tipado por tabela no bucket `silver`.
- **Labels** (`src/features/build_labels.py`): constrói `target_18m` — alvo binário de inadimplência observada em até 18 meses da emissão, a partir das situações configuradas em `settings.yaml` (`labels.def_situacoes`) — e `base_safra`, uma matriz auxiliar por delta de meses usada na validação temporal.
- **Features** (`src/features/registry.py` + `features_sql.py`): 19 features registradas (16 categóricas, 3 numéricas), cada uma com sua SQL de lookup sobre as tabelas do silver, materializadas individualmente no bucket `gold`.
- **Consolidação** (`src/modeling/consolidate.py`): junta o alvo e todas as features numa única base de modelagem (`modeling.base_uri` em `settings.yaml`).

## Modelagem

Três modelos, em ordem crescente de complexidade (`src/modeling/models.py`):

| Modelo | Descrição |
|---|---|
| **Naive** (`NaiveSegmentRate`) | Taxa histórica de inadimplência por segmento (padrão: UF) — benchmark de referência, não é ML |
| **Regressão logística** | Pipeline com pré-processamento embutido (imputação + one-hot/scaling), `class_weight="balanced"` |
| **XGBoost** | 400 árvores, profundidade 5, `scale_pos_weight` recalculado por fold/safra |

Duas validações independentes, ambas usando as mesmas features e métricas (`src/modeling/metrics.py`: AUROC, KS, Brier Score, curvas ROC/KS/calibração):

- **K-fold agrupado** (`train.py`): `StratifiedGroupKFold` (5 folds), estratificado pelo alvo e agrupado por `mutuario` — evita que o mesmo tomador apareça em treino e teste. Registra `leak_mutuario` como checagem de sanidade.
- **Out-of-time / walk-forward** (`train_temporal.py`): particiona por safra agrícola (corte configurável em `settings.yaml`, padrão julho); treina em todas as safras anteriores e testa na safra seguinte, simulando o comportamento em produção. Alerta explícito de censura à direita nas safras mais recentes.

Cada execução (run) é persistida como JSON em `modeling.runs_uri` (local ou `s3://.../gold/modeling/runs/`) via `src/modeling/run_storage.py`.

## Dashboard

`app/dashboard.py` (Streamlit) lê todas as runs persistidas e organiza duas abas:

- **Validação k-fold**: evolução das métricas entre execuções, curvas ROC/KS/calibração por run, métricas por fold.
- **Out-of-time (por safra)**: AUROC/KS/Brier por safra de teste, volume e taxa observada por safra, com aviso de censura à direita.

## Status atual e limitações

- Enriquecimento com fontes externas (IBGE-SIDRA, Bacen-SGS, CEPEA/ESALQ) mencionado no paper ainda **não está implementado** no pipeline de ingestão.
- Rastreamento de experimentos via **MLflow está planejado, mas não ativado** — as execuções hoje ficam em JSON simples no bucket gold.
- Próximos passos de modelagem: categorização e checagem de sanidade das variáveis, avaliação do impacto de cada variável na PD (ex.: coeficientes / SHAP) e execução de mais simulações dos três modelos para consolidar as métricas.
