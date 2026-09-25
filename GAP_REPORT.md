# H-CAP Gap Report

Baseline: no backend or frontend automated test suite was found. `manage.py check` and the frontend production build are used as the initial checks.

| Requirement | Classification | Evidence / required correction |
|---|---|---|
| Existing tenant-owned models and simulated payment models | Already implemented | Existing `Tenant`, `User`, `Program`, intake, payment, PDM, audit, and AI models are reused. |
| JWT authentication and tenant filtering | Implemented but incorrect/insecure | Query filtering lets superusers bypass tenant scope broadly and user management treats `ADMIN` as tenant admin. |
| Platform admin and tenant manager roles | Partially implemented | A system superuser can manage tenants, but tenant manager rules are not implemented; `MANAGER` must manage only its own tenant and must not create `ADMIN`. |
| CSV/XLSX import | Partially implemented | Import reads files and validates rows, but excludes field officers and has no server-side preview confirmation token. |
| No manual internal IDs in forms | Partially implemented | Program/household and several workflow pages still ask users to type UUIDs. |
| Beneficiary phone display | Partially implemented | Only `phone_last4` exists. It must be labelled as masked data; no full phone number is claimed or exposed. |
| PDM separate from scheduling | Already implemented | `PDMResponse` exists and is separate, but Precedence Diagram is absent. |
| Precedence Diagram / Program Activity Network | Missing | No activity or dependency models, routes, UI, cycle prevention, or list fallback exist. |
| Payment simulation and idempotency | Partially implemented | Simulation exists, but program-level `payment_enabled` behavior and duplicate instruction protection need server-side enforcement. |
| Audit integrity | Partially implemented | Generic API deletion is blocked, but user/role changes need stricter server-side controls and authorization-failure audit coverage. |
| AI code | Preserved | AI services, models, routes, and behavior will not be changed in this work. |
