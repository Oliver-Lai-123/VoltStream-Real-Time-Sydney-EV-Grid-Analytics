# ⚡ VoltStream: Real-Time Sydney EV Grid Analytics

**VoltStream** is an end-to-end Modern Data Stack (MDS) pipeline designed to monitor and analyze the real-time energy demand of Electric Vehicle (EV) charging infrastructure across Greater Sydney. 

This project demonstrates a full automated lifecycle—moving data from a live production API into a cloud data warehouse, transforming it with dbt, and serving analytics through a custom Python orchestrator.

---

## 🏗️ Architecture Overview

The pipeline is fully containerized using **Docker** and follows industry-standard data engineering patterns:

1.  **Extract:** A Python-based ingestor pulls live charging station data from the **Open Charge Map API**.
2.  **Schema Mapping:** A lightweight Python layer transforms raw API responses into a consistent schema to prevent **Schema Drift**.
3.  **Data Lake (Local):** Raw JSON payloads are backed up to a local **MinIO** (S3-compatible) instance.
4.  **Cloud Warehouse:** Data is automatically transmitted to **Snowflake** using the `PUT` command and loaded into staging tables via `COPY INTO`.
5.  **Transform:** **dbt Core** manages the transformation layer, aggregating raw station data into suburb-level grid-load metrics.
6.  **Orchestrate:** A "Master Orchestrator" script (`run_full_pipeline.py`) handles the entire lifecycle with a single command.

---

## 🛠️ Tech Stack

* **Language:** Python 3.11 (Pandas, Boto3, Snowflake-Connector, Requests)
* **Infrastructure:** Docker & Docker Compose
* **Storage:** MinIO (Local Data Lake)
* **Warehouse:** Snowflake (Cloud Data Warehouse)
* **Transformation:** dbt Core (Data Build Tool)
* **API:** Open Charge Map (Real-time Global EV Registry)

---

## 🚀 Key Features

* **100% Automation:** The script `run_full_pipeline.py` automates the entire flow: Scrape -> Upload -> Load -> Transform -> Report.
* **Security First:** Uses `.env` management and `.gitignore` to ensure Snowflake credentials and API keys are never exposed.
* **Resilient Engineering:** Includes a mapping layer to handle missing API fields (like `PowerKW`) and ensures data types are strictly enforced.
* **Sydney-Centric:** Configured with a specific bounding box to monitor energy consumption across Sydney suburbs.

---

## 📁 Project Structure

```text
voltstream-project/
├── docker-compose.yml          # Container configuration (Python, MinIO)
├── run_full_pipeline.py        # The Master Orchestrator script
├── dashboard.py                # Standalone data consumer script
├── ingestor/
│   ├── .env                    # (Hidden) Credentials & API Keys
│   └── scrape_ev_data.py       # API extraction & mapping logic
└── voltstream_transform/       # dbt project folder
    ├── models/                 # SQL transformation models
    └── dbt_project.yml         # dbt configuration
