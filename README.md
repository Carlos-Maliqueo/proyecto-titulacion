# 🚀 Automated DTE Data Platform
### Data Engineering & Business Intelligence System

## 📌 Overview

This project consists of an end-to-end Data Engineering platform designed to automate the extraction, processing, and analysis of Electronic Tax Documents (DTE) in XML format obtained from Gosocket.

The system replaces manual operational processes with automated ETL pipelines, improving data availability, consistency, and decision-making capabilities.

---

## 🧠 Problem

Companies manually process large volumes of DTE documents, generating:

- Operational delays
- Human errors
- Lack of centralized analytics
- Limited business visibility

This platform automates the entire workflow.

---

## ⚙️ Solution Architecture

Data Flow:

Gosocket XML → ETL Pipeline → PostgreSQL → Analytics Layer → Power BI Dashboards

Architecture layers:

- **RAW** → Original XML ingestion
- **STAGE** → Data cleaning & transformation
- **CURATED** → Business-ready analytical data

---

## 🛠️ Tech Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Docker & Docker Compose
- Alembic (Database migrations)
- Power BI
- ETL Pipelines
- REST API

---

## 🐳 Running the Project

### 1 - Clone repository:

```bash
git clone https://github.com/tuusuario/dte-data-platform.git
cd dte-data-platform
```
### 2 - Configure environment variables
```bash
cp .env.example .env
```
Edit .env with your local configuration

### 3 - Run containers
```bash
docker-compose up --build
```
The API and database will start automatically

--- 

## 📊 Core Features

- Automated XML ingestion from external source
- ETL processing pipeline
- Data validation and transformation
- Relational database modeling
- Idempotent data processing
- RESTful API integration
- Containerized infrastructure
- Analytical dashboard integration (Power BI)

---

## 📈 Impact & Engineering Value

- Automation of DTE operational workflows
- Significant reduction of manual data handling
- Improved data quality and traceability
- Structured data ready for business analytics
- Scalable architecture following Data Engineering best practices

---

## 🖼️ System Architecture Diagram


---

## 📊 Dashboard Preview

---

## 🔐 Data Quality & Governance
- Structured RAW → STAGE → CURATED pipeline
- Controlled transformation logic
- Reprocessing safety (idempotent ETL)
- Versioned database schema (Alembic migrations)

---
## 👨‍💻 Author
Carlos Maliqueo
Civil Engineer in Computer Science & Telecommunications
Universidad Diego Portales

🔗 LinkedIn: https://linkedin.com/in/carlos-maliqueo-quijano-20b3792a9
🔗 GitHub: https://github.com/Carlos-Maliqueo
