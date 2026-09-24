#  Global Humanitarian Cash Assistance Platform (GHCAP)
## Technical Architecture, AI Pipelines, and System Documentation

**Lead Architect & Engineer:** Amjad Nizar (AI, Automation & Data Engineering Lead)

---

### 1. Executive Summary
The **Global Humanitarian Cash Assistance Platform (GHCAP)** is an enterprise-grade, highly secure, and automated humanitarian aid distribution system. Built and led by **Amjad Nizar**, the platform integrates robust data pipelines, real-time AI-driven anomaly and deduplication detection engines, a human-in-the-review loop queue, financial reconciliation logic, and an autonomous AI reporting copilot.

---

### 2. Core Technical Components & Engineering Scope
Led under the engineering vision of **Amjad Nizar**, the system is structured using a Modular Service-Oriented Architecture powered by Django and PostgreSQL, incorporating the following core pillars:

* **A. Data Pipeline (`import_data` & ETL):**
  * Developed custom Django management commands designed to parse heavy CSV/Excel beneficiary datasets seamlessly.
  * Automatically provisions tenant contexts, household linkages, and generates unique identifier constraints (`number`, `national_id_hash`) to maintain transactional integrity.

* **B. AI & Automation Engines (`core/services.py`):**
  * **Deduplication Engine:** Evaluates phonetic name similarity, phone number matches (`phone_last4`), and national ID hashes (`national_id_hash`) to catch fraudulent or double registrations.
  * **Anomaly & Fraud-Risk Flags:** Monitors transaction thresholds in real-time (e.g., flagging payments exceeding standard caps like $5,000.00) to isolate high-risk cases.
  * **Reconciliation Logic:** Compares local ledger payments with external Financial Service Provider (FSP) reports to flag discrepancies instantly.

* **C. Human-in-the-Loop (HITL) Review Queue:**
  * Automatically converts raw AI signals (`AISignal`) into structured review tasks (`ReviewTask`) assigned with specific priorities (`HIGH`, `MEDIUM`) for manual operational audit.

* **D. AI Reporting Copilot (`AICopilotService`):**
  * Aggregates real-time database metrics to evaluate overall system health.
  * Generates immediate executive summaries and operational recommendations via a natural-language reporting layer.

---

### 3. Core Database Models
* **`Tenant & Program`**: Multi-tenant isolation framework supporting multi-donor humanitarian operations.
* **`Household & Beneficiary`**: Hierarchical representation of recipient units carrying encrypted hash identifiers and status flags.
* **`AISignal`**: Polymorphic storage for detection flags (`POSSIBLE_DUPLICATE`, `HIGH_AMOUNT_ANOMALY`, `FINANCIAL_DISCREPANCY`).
* **`ReviewTask`**: Operational tracking model managing the lifecycle of flagged anomalies.

---

### 4. API Endpoints & Management Commands

#### Data Pipeline Command Usage
To ingest bulk beneficiary lists and trigger immediate AI evaluation pipelines:
```bash
python manage.py import_data test_beneficiaries.csv