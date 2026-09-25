# H-CAP Full Test Guide

## Before testing

1. Start PostgreSQL and the application, then apply migrations:

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe manage.py migrate
   .\.venv\Scripts\python.exe manage.py runserver
   ```

2. In another terminal:

   ```powershell
   cd frontend
   npm run dev
   ```

3. Create one Django superuser if one does not exist. A superuser is the H-CAP system administrator and can see every tenant. A normal `ADMIN` is a tenant administrator and sees only their own tenant.

## Test roles and responsibilities

| Role | Main test responsibility |
|---|---|
| System superuser | Create/manage tenants and create users for any tenant; inspect global dashboard. |
| Tenant administrator | Create users only in their tenant; create programs, budgets, channels, and review all tenant data. |
| Field officer | Register households and beneficiaries; record consent/verification; submit PDM. |
| Reviewer | Create eligibility records, approve/reject enrollments, review duplicate/risk signals and tasks. |
| Finance officer | Create payment batches and simulated payment instructions; run simulated outcomes and reconciliation. |
| Support officer | Register, assign, and resolve complaints; record PDM where permitted. |
| Manager | Monitor dashboards, programs, budgets, imports, complaints, controlled automation, and reports. |
| Auditor | Read dashboards, payments, reconciliation, AI signals, and audit history; cannot create payments. |

## End-to-end operational workflow

1. **System setup**
   - Sign in as the system superuser.
   - Open `User administration`.
   - Confirm all tenant users are visible.
   - Create a tenant administrator for the target tenant. Confirm the tenant dropdown is required.

2. **Tenant setup**
   - Sign in as the tenant administrator.
   - Confirm only that tenant's users are visible.
   - Create field officer, reviewer, finance officer, support officer, manager, and auditor accounts.
   - Confirm the tenant administrator cannot choose another tenant.

3. **Program and budget**
   - Sign in as tenant administrator, manager, or finance officer.
   - Open `Programs`.
   - Create a program with country, country code, program/reporting currency, transfer amount, payment cycle, and budget envelope.
   - Configure a simulated payment channel.
   - Confirm the program appears immediately in the program list.

4. **Household and beneficiary intake**
   - Sign in as field officer.
   - Open `Households`; register a household with program, location, registration date, and optional offline client ID.
   - Open `Beneficiaries`; select the household and register a beneficiary with number, full name, `F` or `M` gender, consent, and verification status.
   - Confirm both records appear in their lists.
   - Confirm a field officer cannot see budgets, audit, user administration, payments, or automation navigation.

5. **CSV/XLSX import test**
   - Sign in as tenant administrator or manager.
   - Open `Import records`.
   - Select a program and upload a CSV/XLSX with the required columns:
     `client_generated_id`, `household_size`, `location`, `beneficiary_number`, `full_name`.
   - Choose `preview`: verify validation results are returned and no records are saved.
   - Choose `import`: verify households/beneficiaries are created and client IDs are preserved.
   - Upload a duplicate national ID hash or phone suffix: verify an advisory duplicate signal and review task are created.

6. **Eligibility and enrollment**
   - Sign in as reviewer.
   - Open `Eligibility review`; create or update an enrollment with `ELIGIBLE`, `INELIGIBLE`, or `ON_HOLD`.
   - Open `Enrollment decisions`; approve an eligible enrollment or reject it.
   - Confirm payment creation is rejected by the backend until the enrollment is approved.

7. **Simulated payment and reconciliation**
   - Sign in as finance officer.
   - Create a payment batch for the program. Confirm the backend generates its idempotency key.
   - Create a payment instruction for an approved enrollment, the matching beneficiary, and the configured channel.
   - Simulate `submit`, then `success` or `failure`.
   - Inspect payment events; confirm events are append-only and the payment is simulated only.
   - Run reconciliation from `AI & Automation` using provider report JSON. Confirm matched/pending/discrepancy counts and review tasks where required.

8. **AI and automation test**
   - Sign in as reviewer: run a duplicate check for a beneficiary. Confirm an advisory signal and review task; confirm no eligibility or payment status changes automatically.
   - Sign in as finance, manager, or admin: run a payment risk scan for a batch. Confirm risk signals are advisory only.
   - Sign in as manager/admin: create an active automation rule and execute it with an idempotency key. Test `CREATE_REVIEW_TASK` and confirm a human review task is created.
   - Run the reporting copilot for a program. Confirm it returns verified metrics only and does not make a final decision.

9. **PDM and complaints**
   - Sign in as field/support/manager/admin.
   - Open `PDM`; submit received rate, amount received, access problem rate, complaint rate, and satisfaction.
   - Open PDM summary and filter by program/channel/location. Confirm averages and totals match submitted data.
   - Sign in as support or manager; register a complaint, assign/update it, then resolve it.

10. **Dashboard, audit, and RBAC checks**
    - Sign in as each role and confirm unavailable navigation items are hidden.
    - Paste an unauthorized route hash manually, for example `#/users` as a field officer; confirm redirect to dashboard.
    - Try the same API with that user's JWT; confirm `403`.
    - Sign in as auditor; confirm payment/audit/reconciliation data is visible but write controls are unavailable.
    - Sign in as superuser; confirm the dashboard includes all tenants and the user page lists users across tenants.
    - Open `Audit`; confirm creates, updates, payment simulations, imports, PDM submissions, AI reviews, and automation executions appear.

## Expected safety rules

- No real bank, mobile-money, or card payment is sent.
- AI signals are advisory and require a human reviewer.
- Users cannot cross tenant boundaries.
- Auditable operational records cannot be deleted through the REST API.
- Repeating a payment or automation operation requires idempotency controls where the model supports them.
