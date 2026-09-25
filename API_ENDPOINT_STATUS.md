# H-CAP API Endpoint Status

All API endpoints require a JWT access token except `POST /api/auth/login/` and `POST /api/auth/refresh/`. Every operational query is restricted to the signed-in user's tenant. A user without a permitted role receives `403`; the frontend also hides that navigation item.

| Endpoint | Status | Purpose | Roles |
|---|---|---|---|
| `POST /api/auth/login/` | Working | Returns JWT access and refresh tokens. | All staff |
| `POST /api/auth/refresh/` | Working | Replaces an expired access token. | Auth flow |
| `POST /api/auth/logout/` | Working | Blacklists the submitted refresh token. | Signed-in staff |
| `GET /api/me/` | Working | Returns the current user, role, and tenant. | All staff |
| `GET/POST/PATCH /api/programs/` | Working | Creates and manages tenant programs. | Admin, finance, manager |
| `GET/POST /api/programs/{id}/channels/` | Working | Manages simulated payment channels. | Admin, finance, manager |
| `GET/POST/PATCH /api/households/` | Working | Registers and searches households. | Admin, field officer |
| `GET/POST/PATCH /api/beneficiaries/` | Working | Registers beneficiaries with number, status, consent, and verification. | Admin, field officer, reviewer |
| `GET/POST/PATCH /api/enrollments/` | Working | Records eligibility and approval workflow. | Admin, reviewer |
| `GET/POST/PATCH /api/payment-instructions/` | Working | Creates simulated instructions for approved enrollments. | Finance roles; auditor read-only |
| `POST /api/payment-instructions/{id}/simulate/` | Working | Creates append-only simulated payment events. No real provider call. | Admin, finance, manager |
| `GET /api/payment-instructions/{id}/events/` | Working | Returns payment event history. | Payment roles |
| `GET/POST/PATCH /api/complaints/` | Working | Registers, assigns, and resolves complaints. | Admin, support, manager |
| `GET/POST/PATCH /api/budgets/` | Working | Manages budget envelopes and line items. | Admin, finance, manager |
| `GET /api/reports/` | Working | Returns tenant dashboard KPIs. | All staff |
| `GET /api/reporting/programs/{id}/summary/` | Working | Returns verified program metrics. | Signed-in staff in tenant |
| `GET /api/audit-events/` | Working | Returns restricted audit history. | Admin, manager, auditor |
| `POST /api/imports/` | Working | Validates or imports CSV/XLSX rows, preserves client IDs, and runs advisory duplicate checks. | Admin, manager |
| `GET/POST /api/pdm/` | Working | Stores and lists PDM responses. | Admin, support, field, manager |
| `GET /api/pdm/summary/` | Working | Returns PDM averages and amounts by program, channel, or location. | Admin, support, field, manager |
| `POST /api/sync/registrations/` | Working | Idempotent offline registration synchronization. | Admin, field officer |
| `GET/POST /api/payment-batches/` | Working | Creates/view simulated payment batches with server-generated idempotency keys. | Finance roles; auditor read-only |
| `GET /api/reconciliation-items/` and `POST /resolve/` | Working | Views and resolves persisted reconciliation discrepancies. | Finance roles; auditor read-only |
| `GET /api/review-tasks/` and `POST /resolve/` | Working | Views and resolves human review queue tasks. | Admin, reviewer, manager, support |
| `GET /api/ai-signals/` and `POST /review/` | Working | Views and records human review of advisory AI signals. | Admin, manager, reviewer, auditor read-only |
| `POST /api/ai/deduplicate/{beneficiary_id}/` | Working | Checks potential duplicate beneficiaries and creates review tasks. | Admin, manager, reviewer |
| `POST /api/ai/anomalies/` | Working | Creates advisory payment-risk signals for a batch. | Admin, finance, manager, auditor |
| `POST /api/ai/reconcile/` | Working | Compares simulated provider report JSON with payment events. | Admin, finance, manager, auditor |
| `POST /api/ai/copilot/` | Working | Returns verified program metrics for a reporting question. | Admin, manager, auditor, reviewer |
| `GET/POST /api/ai/status/` | Working | Shows AI status/rules; accepts controlled action requests. | Admin, manager, reviewer |
| `POST /api/ai/automation/execute/` | Working | Runs active safe rules with idempotency tracking. | Admin, manager |
| `GET/POST/PATCH /api/automation-rules/` | Working | Configures `Event → Rule → Action` records. | Admin/manager write; reviewer read-only |
| `GET /api/automation-executions/` | Working | Views automation execution history. | Admin, manager, reviewer, auditor |
| `GET /api/pipeline/status/` | Working | Returns tenant-scoped pipeline counts and stages. | Admin, manager, auditor |

No endpoint can automatically approve eligibility, confirm fraud, delete auditable operational records, or release/send real payments. Those remain human-controlled; payments are simulated only.
