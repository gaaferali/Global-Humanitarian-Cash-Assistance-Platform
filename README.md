# H-CAP Master SRS/SDD MVP

Scalable humanitarian cash assistance platform built from the supplied master SRS/SDD, database schema, and frontend mockup colors.

## Stack

- Backend: Django REST Framework with PostgreSQL
- Frontend: Vite `8.3.0`, React `19.3.0`, TypeScript `7.0.2`, Bootstrap `5.3.8`
- Payments: fake simulated adapter only
- AI/automation: API boundaries are closed for this phase

## Run Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d postgres
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

## Implemented Scope

- 12 core persisted tables from the master SRS/SDD.
- Required corrections: beneficiary number/status, program country/currency type, household location.
- Dashboards for beneficiaries, approvals, paid/pending/failed, approved/distributed amounts, geography, reconciliation, complaints, exceptions, and program KPIs.
- Multi-tenant, multi-country, multi-language/RTL, multi-currency, auditability, controlled import/export, and fake payment simulation foundations.
