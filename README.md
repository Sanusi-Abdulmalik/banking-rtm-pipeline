# 🏦 Real-Time Transaction Monitoring Pipeline

> A production-grade, cloud-native data pipeline for banking fraud detection — built with Apache Kafka, Spark Structured Streaming, Azure, Delta Lake, and Apache Airflow.

![Architecture](https://img.shields.io/badge/Architecture-Lambda%20%2B%20Medallion-blue)
![Cloud](https://img.shields.io/badge/Cloud-Microsoft%20Azure-0078D4?logo=microsoftazure)
![Streaming](https://img.shields.io/badge/Streaming-Apache%20Kafka-231F20?logo=apachekafka)
![Processing](https://img.shields.io/badge/Processing-Apache%20Spark-E25A1C?logo=apachespark)
![Orchestration](https://img.shields.io/badge/Orchestration-Apache%20Airflow-017CEE?logo=apacheairflow)
![Format](https://img.shields.io/badge/Format-Parquet%20%2F%20Delta%20Lake-green)
![IaC](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Data Flow](#-data-flow)
- [Tech Stack](#-tech-stack)
- [Folder Structure](#-folder-structure)
- [Getting Started](#-getting-started)
- [Pipeline Stages](#-pipeline-stages)
- [Fraud Detection Logic](#-fraud-detection-logic)
- [Data Quality](#-data-quality)
- [Monitoring & Observability](#-monitoring--observability)
- [Infrastructure (IaC)](#-infrastructure-iac)
- [CI/CD](#-cicd)
- [Design Decisions](#-design-decisions)

---

## 🔍 Overview

This project implements an **event-driven, real-time transaction monitoring system** for a banking environment. It ingests raw payment transactions from multiple channels (ATM, POS, mobile, online), applies fraud detection rules and ML inference in real time, stores data in a cloud data lake using the Medallion Architecture, and surfaces insights through Power BI dashboards.

### Key Metrics

| Metric | Value |
|---|---|
| End-to-end latency (source → fraud alert) | < 2 seconds |
| Peak throughput | 50,000 transactions/sec |
| Data freshness (Spark micro-batch) | 30 seconds |
| Pipeline availability (Azure SLA) | 99.95% |
| Storage format | Parquet / Delta Lake |

### Compliance

- **PCI-DSS**: Cardholder data isolated in scoped ADLS containers with dedicated ACLs, TDE on Synapse, network-level isolation via Private Endpoints
- **GDPR**: Column-level PII masking in Synapse, Delta Lake `VACUUM` for right-to-erasure, audit logging via Azure Monitor

---

## 🏛️ Architecture

This pipeline follows a **Lambda + Medallion hybrid pattern**:

- **Speed layer**: Spark Structured Streaming for real-time fraud detection (< 2s latency)
- **Batch layer**: Apache Airflow orchestrating Bronze → Silver → Gold Delta Lake transformations
- **Serving layer**: Azure Synapse Analytics + Power BI for analytics and dashboards

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRANSACTION SOURCES                       │
│   Core Banking DB │ ATM/POS │ Mobile App │ Online Gateway        │
└────────────────────────────┬────────────────────────────────────┘
                             │ CDC (Debezium) + REST APIs
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                              │
│        Azure Event Hubs (Kafka API) + Schema Registry            │
│   Topics: raw-transactions │ fraud-alerts │ enriched-transactions│
└────────────────────────────┬────────────────────────────────────┘
                             │ Kafka Consumer (Spark readStream)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  STREAM PROCESSING (Speed Layer)                 │
│          Azure Databricks — Spark Structured Streaming           │
│   Fraud Rules Engine │ ML Inference (MLflow) │ Watermarking      │
└──────────┬──────────────────────────────────────┬───────────────┘
           │ Write Delta Lake                      │ Publish fraud alerts
           ▼                                       ▼
┌──────────────────────────┐          ┌────────────────────────────┐
│    DATA LAKE (ADLS Gen2) │          │  fraud-alerts Kafka Topic  │
│  Bronze │ Silver │ Gold  │          │  → Downstream consumers    │
│  (Delta Lake / Parquet)  │          └────────────────────────────┘
└──────────┬───────────────┘
           │ Airflow DAGs (daily batch)
           ▼
┌─────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION (Batch Layer)                         │
│   Apache Airflow — Silver→Gold ETL │ ML Retraining │ DQ Checks   │
└────────────────────────────┬────────────────────────────────────┘
                             │ Synapse Link (zero-ETL sync)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA WAREHOUSE                                │
│              Azure Synapse Analytics                             │
│   fact_transactions │ dim_account │ dim_merchant │ dim_risk      │
└────────────────────────────┬────────────────────────────────────┘
                             │ DirectQuery / Import
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     VISUALIZATION                                │
│         Power BI Premium — Fraud Dashboard │ Exec Reports        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow

| Step | Stage | Technology | Output |
|---|---|---|---|
| 1 | Transaction emitted | Core Banking / REST API / CDC | Raw JSON event |
| 2 | Published to Kafka | Azure Event Hubs (Kafka API) | Avro-serialized message |
| 3 | Consumed by Spark | Databricks Structured Streaming | Parsed DataFrame |
| 4 | Fraud scoring | Rules engine + MLflow model UDF | `is_fraud` flag + risk score |
| 5 | Write Bronze | ADLS Gen2 Delta Lake | Raw Parquet partition |
| 6 | Enrich & clean (Silver) | Airflow DAG + Spark batch | Deduplicated Delta table |
| 7 | Aggregate (Gold) | Airflow DAG + Spark batch | Fraud metrics, risk scores |
| 8 | Sync to warehouse | Synapse Link | Synapse SQL tables |
| 9 | Dashboard refresh | Power BI DirectQuery | Real-time fraud dashboard |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11 |
| **Ingestion** | Azure Event Hubs (Kafka API), Debezium CDC, Avro + Schema Registry |
| **Stream Processing** | Apache Spark 3.5 (Structured Streaming), Azure Databricks |
| **Storage** | Azure Data Lake Storage Gen2, Delta Lake, Parquet |
| **Orchestration** | Apache Airflow 2.9, Azure Managed Airflow |
| **ML / Models** | MLflow, scikit-learn, XGBoost, Databricks Feature Store |
| **Data Warehouse** | Azure Synapse Analytics, Synapse Link |
| **Data Quality** | Great Expectations 0.18 |
| **Visualization** | Power BI Premium, Row-Level Security |
| **Monitoring** | Azure Monitor, Log Analytics, Grafana, OpenTelemetry |
| **Infrastructure** | Terraform, Azure DevOps / GitHub Actions, Docker, AKS |
| **Security** | Azure Managed Identity, Azure Key Vault, Private Endpoints |

---

## 📁 Folder Structure

```
banking-rtm-pipeline/
├── ingestion/
│   ├── producers/
│   │   ├── transaction_producer.py       # Kafka producer (Confluent Python)
│   │   ├── cdc_debezium_config.json      # Debezium connector config
│   │   └── schema/
│   │       └── transaction.avsc          # Avro schema definition
│   └── tests/
│       └── test_producer.py
│
├── streaming/
│   ├── jobs/
│   │   ├── fraud_detection_stream.py     # Main Spark Structured Streaming job
│   │   ├── transaction_enrichment.py     # Geo + merchant enrichment
│   │   └── alert_publisher.py            # Write fraud alerts → Kafka
│   ├── rules/
│   │   ├── velocity_check.py             # >5 transactions/min rule
│   │   ├── geo_anomaly.py                # Cross-border velocity detection
│   │   └── amount_deviation.py           # Z-score anomaly detection
│   ├── ml/
│   │   ├── model_loader.py               # Load MLflow model as Spark UDF
│   │   └── feature_engineering.py        # Real-time feature computation
│   └── tests/
│       └── test_fraud_rules.py
│
├── datalake/
│   ├── bronze/
│   │   └── schema_definitions.py
│   ├── silver/
│   │   ├── dedup_transactions.py
│   │   └── enrich_transactions.py
│   ├── gold/
│   │   ├── fraud_aggregates.py
│   │   ├── customer_risk_scores.py
│   │   └── regulatory_reports.py
│   └── utils/
│       └── delta_utils.py
│
├── orchestration/
│   ├── dags/
│   │   ├── silver_to_gold_dag.py         # Daily medallion ETL
│   │   ├── ml_retraining_dag.py          # Weekly model retraining
│   │   ├── data_quality_dag.py           # Great Expectations checks
│   │   └── report_dispatch_dag.py        # Regulatory report generation
│   ├── plugins/
│   │   └── azure_synapse_operator.py
│   └── tests/
│       └── test_dags.py
│
├── warehouse/
│   ├── ddl/
│   │   ├── fact_transactions.sql
│   │   ├── dim_account.sql
│   │   └── dim_risk.sql
│   ├── views/
│   │   └── fraud_summary_view.sql
│   └── synapse_link_config.json
│
├── monitoring/
│   ├── alerts/
│   │   ├── kafka_lag_alert.json
│   │   └── pipeline_failure_alert.json
│   ├── dashboards/
│   │   └── grafana_pipeline_health.json
│   └── data_quality/
│       └── expectations/
│           └── transactions_suite.json
│
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── eventhubs.tf
│   │   ├── databricks.tf
│   │   ├── adls.tf
│   │   ├── synapse.tf
│   │   └── variables.tf
│   └── docker/
│       ├── airflow/Dockerfile
│       └── spark/Dockerfile
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│       └── test_pipeline_e2e.py
│
├── docs/
│   ├── architecture.md
│   ├── runbook.md
│   └── data_dictionary.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml                        # Lint, test, type-check on PR
│       └── cd.yml                        # Deploy to Azure on merge to main
│
├── pyproject.toml
├── Makefile
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Azure CLI (`az login`)
- Terraform 1.6+
- Astro CLI (for local Airflow)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/banking-rtm-pipeline.git
cd banking-rtm-pipeline
```

### 2. Install Python dependencies

```bash
pip install poetry
poetry install
```

### 3. Provision Azure infrastructure

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file="dev.tfvars"
terraform apply -var-file="dev.tfvars"
```

### 4. Start local Airflow (Astro CLI)

```bash
cd orchestration
astro dev start
# Airflow UI available at http://localhost:8080
```

### 5. Run the Kafka producer (local test)

```bash
python ingestion/producers/transaction_producer.py \
  --bootstrap-servers localhost:9092 \
  --topic raw-transactions \
  --rate 100  # transactions per second
```

### 6. Submit the Spark Streaming job (Databricks)

```bash
databricks jobs run-now --job-id <fraud-detection-job-id>
```

### 7. Run tests

```bash
make test           # unit + integration tests
make test-e2e       # end-to-end pipeline test
make lint           # ruff + mypy
```

---

## ⚙️ Pipeline Stages

### Bronze Layer — Raw Ingestion

- Spark reads from Kafka topic `raw-transactions` using `readStream`
- Schema enforced via Avro + Schema Registry
- Written to `adls://bronze/transactions/year=*/month=*/day=*` in Parquet
- Checkpointing to ADLS Gen2 for exactly-once delivery semantics
- Retention: 90 days (configurable)

### Silver Layer — Cleansed & Enriched

- Deduplication on `transaction_id` using Delta Lake `MERGE`
- Null handling, type casting, standardised timestamps (UTC)
- Geo-enrichment: reverse geocoding of merchant coordinates
- Merchant lookup: join with `dim_merchant` reference table
- Great Expectations validation gate before write

### Gold Layer — Aggregated & Serving-Ready

- `fraud_aggregates`: hourly/daily fraud counts by region, channel, merchant category
- `customer_risk_scores`: rolling 30-day risk scoring per account
- `regulatory_reports`: pre-aggregated tables for compliance reporting
- Z-ordered on `(transaction_date, account_id)` for query pruning

---

## 🔎 Fraud Detection Logic

Fraud scoring runs in the Spark Structured Streaming job. Each transaction is scored against three rule layers and one ML model:

### Rule 1 — Velocity Check
```
IF count(transactions) by account_id in last 5 minutes > 5
THEN flag = HIGH_VELOCITY
```

### Rule 2 — Geographic Anomaly
```
IF distance(last_transaction_location, current_location) > 500km
AND time_diff < 2 hours
THEN flag = GEO_IMPOSSIBLE
```

### Rule 3 — Amount Deviation (Z-Score)
```
IF (amount - account_avg_30d) / account_std_30d > 3.0
THEN flag = AMOUNT_ANOMALY
```

### ML Model — XGBoost Classifier
- Trained on 12 months of labelled transaction history
- Features: velocity, geo-delta, amount z-score, merchant category risk, time-of-day, device fingerprint
- Registered in MLflow Model Registry; loaded as a Spark UDF for distributed inference
- Champion/challenger A/B deployment managed via MLflow aliases
- Retrained weekly via Airflow `ml_retraining_dag`

### Scoring Output

| Field | Type | Description |
|---|---|---|
| `is_fraud` | boolean | Final fraud determination |
| `fraud_score` | float (0–1) | ML model probability |
| `fraud_flags` | array[string] | Triggered rule names |
| `review_required` | boolean | Score between 0.4–0.7 (manual review queue) |

---

## ✅ Data Quality

Data quality is enforced at every layer transition using **Great Expectations**:

| Checkpoint | Checks |
|---|---|
| Bronze → Silver | Schema conformance, null rate < 0.1%, `transaction_id` uniqueness |
| Silver → Gold | Referential integrity (account_id in dim_account), amount > 0, valid ISO currency codes |
| Gold → Synapse | Row count reconciliation vs. source, sum(amount) match, fraud rate within expected range |

Failed rows are written to a **quarantine table** — never silently dropped. Airflow alerts via Slack on DQ failures.

---

## 📡 Monitoring & Observability

### Metrics Tracked

| Metric | Alert Threshold | Channel |
|---|---|---|
| Kafka consumer lag (per partition) | > 10,000 messages | PagerDuty (P1) |
| Spark job failure | Any failure | PagerDuty (P0) |
| Fraud detection latency p99 | > 5 seconds | Slack (P2) |
| Data quality pass rate | < 99% | Slack (P2) |
| Pipeline data freshness | > 5 minutes stale | Slack (P2) |
| Airflow SLA miss | Per DAG SLA config | PagerDuty (P1) |

### Tools

- **Azure Monitor + Log Analytics**: centralised logs from Databricks, Airflow, Synapse
- **Grafana**: pipeline health dashboard (Kafka lag, Spark throughput, DQ pass rate)
- **OpenTelemetry**: distributed tracing across Kafka → Spark → Synapse
- **Azure Defender**: threat detection on Storage, Databricks, and Synapse

### On-Call Runbook

See [`docs/runbook.md`](docs/runbook.md) for step-by-step remediation of common alerts.

---

## 🏗 Infrastructure (IaC)

All Azure resources are provisioned via **Terraform**. No manual portal configuration.

| Resource | Terraform File |
|---|---|
| Azure Event Hubs (Kafka) | `infrastructure/terraform/eventhubs.tf` |
| Azure Databricks Workspace | `infrastructure/terraform/databricks.tf` |
| ADLS Gen2 + containers | `infrastructure/terraform/adls.tf` |
| Azure Synapse Analytics | `infrastructure/terraform/synapse.tf` |
| Key Vault, Managed Identity | `infrastructure/terraform/main.tf` |

### Environments

| Environment | Azure Subscription | Branch |
|---|---|---|
| `dev` | `dev-banking-sub` | `feature/*` |
| `staging` | `staging-banking-sub` | `develop` |
| `prod` | `prod-banking-sub` | `main` |

---

## 🔁 CI/CD

### On Pull Request → `ci.yml`

```
ruff lint → mypy type check → pytest unit tests → Great Expectations unit suite
```

### On Merge to `main` → `cd.yml`

```
Terraform plan → Terraform apply → Deploy Databricks jobs (Asset Bundles) → Deploy Airflow DAGs → Integration tests
```

---

## 🧠 Design Decisions

| Decision | Rationale |
|---|---|
| **Azure Event Hubs over self-hosted Kafka** | Kafka-compatible API with zero cluster management; auto-inflate handles load spikes |
| **Delta Lake over raw Parquet** | ACID transactions, time travel, schema evolution, and Z-ordering for query pruning |
| **Medallion Architecture (Bronze/Silver/Gold)** | Clear data lineage, isolated failure blast radius, supports both real-time and batch consumers |
| **Spark Structured Streaming over Flink** | Native Databricks integration, shared codebase with batch jobs, strong Delta Lake connector |
| **MLflow for model management** | Experiment tracking, model versioning, champion/challenger deployment without custom tooling |
| **Great Expectations for DQ** | Declarative expectations, quarantine pattern, Airflow-native integration |
| **Terraform for IaC** | Reproducible environments, environment parity, PR-reviewable infrastructure changes |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Your Name**
[LinkedIn](https://linkedin.com/in/yourprofile) · [GitHub](https://github.com/your-username)

> Built as a Data Engineering portfolio project demonstrating production-grade pipeline design on Azure.