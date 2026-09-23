# H-CAP MVP API Baseline

The master SRS/SDD is the authority for this implementation. AI and automation endpoints are present only as closed API boundaries and return `403` until explicitly enabled later.

## Active MVP APIs

- `POST /api/auth/login/`
- `GET /api/me/`
- `GET|POST /api/programs/`
- `PATCH /api/programs/{id}/`
- `GET|POST /api/programs/{id}/channels/`
- `GET|POST /api/households/`
- `GET|POST /api/beneficiaries/`
- `GET|POST /api/enrollments/`
- `GET|POST /api/payment-instructions/`
- `POST /api/payment-instructions/{id}/simulate/`
- `GET /api/payment-instructions/{id}/events/`
- `GET|POST /api/complaints/`
- `PATCH /api/complaints/{id}/`
- `GET|POST /api/budgets/`
- `GET /api/reports/`
- `GET /api/audit-events/`
- `POST /api/imports/`
- `GET|POST /api/pdm/`

## Closed AI/Automation Boundaries

- `GET|POST /api/ai/assistant/context/`
- `GET|POST /api/ai/assistant/query/`
- `GET /api/ai/automation/tasks/`
- `POST /api/ai/automation/tasks/{id}/run/`
- `GET /api/ai/signals/`
- `POST /api/ai/signals/{id}/review/`
- `POST /api/ai/reports/draft/`

## Design Guarantees

- Multi-country configuration through `Program.country`, `Program.country_pack`, and currency fields.
- Multi-tenant separation through tenant-scoped querysets and protected ownership checks.
- Multi-language and RTL frontend support for Arabic/English.
- Multi-currency support through program currency, reporting currency, and exchange rate fields.
- Payment-agnostic fake adapter with simulated events only.
- Configurable workflows through `Program.workflow_config`.
- Auditability through append-only `AuditEvent` and `PaymentEvent` records.
- Interoperability through controlled import placeholder and export-ready report data.
