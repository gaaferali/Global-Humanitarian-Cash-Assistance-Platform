from django.test import TestCase
from rest_framework.test import APIClient

from datetime import date

from .models import (
    AISignal,
    AuditEvent,
    AutomationRule,
    Beneficiary,
    Household,
    PDMResponse,
    PaymentInstruction,
    Program,
    ProgramActivity,
    Tenant,
    User,
)


class TenantBoundaryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant A", tenant_type="NGO", default_currency="USD")
        self.other_tenant = Tenant.objects.create(name="Tenant B", tenant_type="NGO", default_currency="USD")
        self.manager = User.objects.create_user("manager@example.test", "Tenant Manager", self.tenant, "password", role=User.Role.MANAGER)
        self.client = APIClient()
        self.client.force_authenticate(self.manager)

    def test_manager_creates_user_only_in_own_tenant(self):
        response = self.client.post("/api/users/", {"email": "field@example.test", "full_name": "Field Officer", "password": "password", "role": User.Role.FIELD_OFFICER, "tenant_id": str(self.other_tenant.id)}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(email="field@example.test").tenant, self.tenant)

    def test_manager_cannot_create_platform_administrator(self):
        response = self.client.post("/api/users/", {"email": "admin@example.test", "full_name": "Platform Admin", "password": "password", "role": User.Role.ADMIN}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_tenant_administrator_can_create_an_operational_user(self):
        tenant_admin = User.objects.create_user("tenant-admin@example.test", "Tenant Administrator", self.tenant, "password", role=User.Role.ADMIN)
        self.client.force_authenticate(tenant_admin)
        response = self.client.post(
            "/api/users/",
            {"email": "support@example.test", "full_name": "Support Officer", "password": "password", "role": User.Role.SUPPORT},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(email="support@example.test").tenant, self.tenant)


class ActivityDependencyTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant A", tenant_type="NGO", default_currency="USD")
        self.manager = User.objects.create_user("manager@example.test", "Tenant Manager", self.tenant, "password", role=User.Role.MANAGER)
        self.program = Program.objects.create(tenant=self.tenant, name="Cash support", country="Sudan", country_code="SD", currency="USD", reporting_currency="USD", transfer_amount="50.00", payment_cycle=Program.Cycle.MONTHLY, created_by=self.manager)
        self.first = ProgramActivity.objects.create(tenant=self.tenant, program=self.program, name="Register", created_by=self.manager)
        self.second = ProgramActivity.objects.create(tenant=self.tenant, program=self.program, name="Review", created_by=self.manager)
        self.client = APIClient()
        self.client.force_authenticate(self.manager)

    def test_dependency_cycle_is_rejected(self):
        first_response = self.client.post("/api/activity-dependencies/", {"predecessor": str(self.first.id), "successor": str(self.second.id)}, format="json")
        self.assertEqual(first_response.status_code, 201)
        cycle_response = self.client.post("/api/activity-dependencies/", {"predecessor": str(self.second.id), "successor": str(self.first.id)}, format="json")
        self.assertEqual(cycle_response.status_code, 400)


class DuplicateEndpointTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant A", tenant_type="NGO", default_currency="USD")
        self.reviewer = User.objects.create_user("reviewer@example.test", "Reviewer", self.tenant, "password", role=User.Role.REVIEWER)
        self.client = APIClient()
        self.client.force_authenticate(self.reviewer)

    def test_invalid_beneficiary_identifier_returns_validation_error(self):
        response = self.client.post("/api/ai/deduplicate/27/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid beneficiary", response.data["error"]["message"])


class PlatformAdministrationTests(TestCase):
    def setUp(self):
        self.system_tenant = Tenant.objects.create(name="System", tenant_type="SYSTEM", default_currency="USD")
        self.admin = User.objects.create_superuser("admin@example.test", "Platform Admin", "password", tenant=self.system_tenant)
        self.manager = User.objects.create_user("manager@example.test", "Tenant Manager", self.system_tenant, "password", role=User.Role.MANAGER)
        self.auditor = User.objects.create_user("auditor@example.test", "Auditor", self.system_tenant, "password", role=User.Role.AUDITOR)
        self.client = APIClient()

    def test_platform_administrator_creates_tenant(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/tenants/", {"name": "New Partner", "tenant_type": "NGO", "default_currency": "USD", "is_active": True}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Tenant.objects.filter(name="New Partner").exists())
        self.assertTrue(AuditEvent.objects.filter(action="TENANT_CREATED").exists())

    def test_tenant_audit_roles_can_read_only_their_tenant_history(self):
        AuditEvent.objects.create(tenant=self.system_tenant, actor=self.admin, action="TEST", entity_type="Tenant", entity_id=str(self.system_tenant.id))
        self.client.force_authenticate(self.manager)
        manager_response = self.client.get("/api/audit-events/")
        self.assertEqual(manager_response.status_code, 200)
        self.assertEqual(len(manager_response.data.get("results", manager_response.data)), 1)
        self.client.force_authenticate(self.auditor)
        self.assertEqual(self.client.get("/api/audit-events/").status_code, 200)


class ProgramAccessTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant A", tenant_type="NGO", default_currency="USD")
        self.manager = User.objects.create_user("manager@example.test", "Tenant Manager", self.tenant, "password", role=User.Role.MANAGER)
        self.finance = User.objects.create_user("finance@example.test", "Finance Officer", self.tenant, "password", role=User.Role.FINANCE)
        self.field_officer = User.objects.create_user("field@example.test", "Field Officer", self.tenant, "password", role=User.Role.FIELD_OFFICER)
        self.reviewer = User.objects.create_user("reviewer@example.test", "Reviewer", self.tenant, "password", role=User.Role.REVIEWER)
        self.auditor = User.objects.create_user("auditor@example.test", "Auditor", self.tenant, "password", role=User.Role.AUDITOR)
        self.program = Program.objects.create(
            tenant=self.tenant,
            name="Cash support",
            country="Sudan",
            country_code="SD",
            currency="USD",
            reporting_currency="USD",
            transfer_amount="50.00",
            payment_cycle=Program.Cycle.MONTHLY,
            created_by=self.manager,
        )
        self.client = APIClient()

    def test_operational_roles_can_read_tenant_programs(self):
        for user in [self.finance, self.field_officer, self.auditor]:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                response = self.client.get("/api/programs/")
                self.assertEqual(response.status_code, 200)
                programs = response.data.get("results", response.data)
                self.assertEqual(programs[0]["id"], str(self.program.id))

    def test_finance_cannot_create_program_but_can_configure_channel(self):
        self.client.force_authenticate(self.finance)
        create_response = self.client.post("/api/programs/", {}, format="json")
        self.assertEqual(create_response.status_code, 403)
        channel_response = self.client.post(
            f"/api/programs/{self.program.id}/channels/",
            {"channel_type": "MOBILE_MONEY", "provider_name": "Simulated wallet", "currency": "USD", "is_active": True},
            format="json",
        )
        self.assertEqual(channel_response.status_code, 201)

    def test_reviewer_cannot_create_enrollment_for_another_tenant(self):
        other_tenant = Tenant.objects.create(name="Tenant B", tenant_type="NGO", default_currency="USD")
        other_manager = User.objects.create_user("other-manager@example.test", "Other Manager", other_tenant, "password", role=User.Role.MANAGER)
        other_program = Program.objects.create(
            tenant=other_tenant,
            name="Other cash support",
            country="Chad",
            country_code="TD",
            currency="USD",
            reporting_currency="USD",
            transfer_amount="50.00",
            payment_cycle=Program.Cycle.MONTHLY,
            created_by=other_manager,
        )
        household = Household.objects.create(
            tenant=other_tenant,
            program=other_program,
            household_size=2,
            location="N'Djamena",
            registration_date=date(2026, 9, 25),
            created_by=other_manager,
        )
        beneficiary = Beneficiary.objects.create(
            household=household,
            number="OTHER-001",
            full_name="Other Tenant Beneficiary",
            created_by=other_manager,
        )
        self.client.force_authenticate(self.reviewer)
        response = self.client.post(
            "/api/enrollments/",
            {"program": str(other_program.id), "beneficiary": str(beneficiary.id), "eligibility_status": "ELIGIBLE", "status": "ENROLLED"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class PDMAndAuthenticationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant A", tenant_type="NGO", default_currency="USD")
        self.other_tenant = Tenant.objects.create(name="Tenant B", tenant_type="NGO", default_currency="USD")
        self.field_officer = User.objects.create_user("field@example.test", "Field Officer", self.tenant, "password", role=User.Role.FIELD_OFFICER)
        self.manager = User.objects.create_user("manager@example.test", "Tenant Manager", self.tenant, "password", role=User.Role.MANAGER)
        self.program = Program.objects.create(
            tenant=self.tenant,
            name="Cash support",
            country="Sudan",
            country_code="SD",
            currency="USD",
            reporting_currency="USD",
            transfer_amount="50.00",
            payment_cycle=Program.Cycle.MONTHLY,
            created_by=self.manager,
        )
        self.client = APIClient()

    def test_jwt_login_can_call_current_user_endpoint(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {"email": self.field_officer.email, "password": "password"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("access", login_response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        me_response = self.client.get("/api/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["email"], self.field_officer.email)

    def test_jwt_logout_blacklists_the_refresh_token(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {"email": self.field_officer.email, "password": "password"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        logout_response = self.client.post(
            "/api/auth/logout/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        self.assertEqual(logout_response.status_code, 200)
        refresh_response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 401)

    def test_field_officer_can_submit_pdm_without_channel_or_location(self):
        self.client.force_authenticate(self.field_officer)
        response = self.client.post(
            "/api/pdm/",
            {"program": str(self.program.id), "received_rate": 98, "amount_received": 50, "access_problem_rate": 2, "complaint_rate": 1, "satisfaction": 95},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        pdm_response = PDMResponse.objects.get(id=response.data["id"])
        self.assertEqual(pdm_response.tenant, self.tenant)
        self.assertEqual(pdm_response.channel, "UNSPECIFIED")
        self.assertEqual(pdm_response.location, "UNSPECIFIED")

    def test_field_officer_cannot_request_another_tenant_pdm_summary(self):
        self.client.force_authenticate(self.field_officer)
        response = self.client.get(f"/api/pdm/summary/?tenant={self.other_tenant.id}")
        self.assertEqual(response.status_code, 403)


class EndToEndWorkflowTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Partner A", tenant_type="NGO", default_currency="USD")
        self.manager = User.objects.create_user("manager@example.test", "Tenant Manager", self.tenant, "password", role=User.Role.MANAGER)
        self.field_officer = User.objects.create_user("field@example.test", "Field Officer", self.tenant, "password", role=User.Role.FIELD_OFFICER)
        self.reviewer = User.objects.create_user("reviewer@example.test", "Reviewer", self.tenant, "password", role=User.Role.REVIEWER)
        self.finance = User.objects.create_user("finance@example.test", "Finance Officer", self.tenant, "password", role=User.Role.FINANCE)
        self.support = User.objects.create_user("support@example.test", "Support Officer", self.tenant, "password", role=User.Role.SUPPORT)
        self.auditor = User.objects.create_user("auditor@example.test", "Auditor", self.tenant, "password", role=User.Role.AUDITOR)
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_end_to_end_workflow_and_role_scoped_reporting(self):
        self.authenticate(self.manager)
        program_response = self.client.post(
            "/api/programs/",
            {
                "name": "Cash assistance",
                "country": "Sudan",
                "country_code": "SD",
                "currency": "USD",
                "currency_type": "PROGRAM",
                "reporting_currency": "USD",
                "exchange_rate": "1",
                "timezone": "Africa/Khartoum",
                "language": "en",
                "transfer_amount": "50.00",
                "payment_cycle": "MONTHLY",
                "status": "ACTIVE",
                "workflow_config": {"payment_enabled": True},
                "country_pack": {},
            },
            format="json",
        )
        self.assertEqual(program_response.status_code, 201)
        program_id = program_response.data["id"]
        budget_response = self.client.post(
            "/api/budgets/",
            {"program": program_id, "currency": "USD", "status": "ACTIVE", "planned_total": "1000.00", "actual_total": "0.00", "line_items": []},
            format="json",
        )
        self.assertEqual(budget_response.status_code, 201)

        self.authenticate(self.finance)
        channel_response = self.client.post(
            f"/api/programs/{program_id}/channels/",
            {"channel_type": "MOBILE_MONEY", "provider_name": "Internal simulator", "currency": "USD", "is_active": True},
            format="json",
        )
        self.assertEqual(channel_response.status_code, 201)
        batch_response = self.client.post(
            "/api/payment-batches/",
            {"program": program_id, "name": "September simulator", "status": "DRAFT", "provider_response": {}},
            format="json",
        )
        self.assertEqual(batch_response.status_code, 201)

        self.authenticate(self.field_officer)
        household_response = self.client.post(
            "/api/households/",
            {"program": program_id, "household_size": 4, "location": "Khartoum", "registration_date": "2026-09-25"},
            format="json",
        )
        self.assertEqual(household_response.status_code, 201)
        beneficiary_response = self.client.post(
            "/api/beneficiaries/",
            {"household": household_response.data["id"], "number": "BEN-001", "full_name": "Amina Ahmed", "gender": "F", "phone_last4": "1234", "consent_given": True},
            format="json",
        )
        self.assertEqual(beneficiary_response.status_code, 201)
        beneficiary_id = beneficiary_response.data["id"]

        duplicate_household_response = self.client.post(
            "/api/households/",
            {"program": program_id, "household_size": 3, "location": "Khartoum", "registration_date": "2026-09-25"},
            format="json",
        )
        self.assertEqual(duplicate_household_response.status_code, 201)
        duplicate_beneficiary_response = self.client.post(
            "/api/beneficiaries/",
            {"household": duplicate_household_response.data["id"], "number": "BEN-002", "full_name": "Amina Ahmed", "gender": "F", "phone_last4": "1234", "consent_given": True},
            format="json",
        )
        self.assertEqual(duplicate_beneficiary_response.status_code, 201)

        self.authenticate(self.reviewer)
        dedup_response = self.client.post(f"/api/ai/deduplicate/{beneficiary_id}/", {}, format="json")
        self.assertEqual(dedup_response.status_code, 200)
        self.assertTrue(dedup_response.data["duplicate_flagged"])
        signal = AISignal.objects.get(entity_id=beneficiary_id, signal_type="POSSIBLE_DUPLICATE")
        review_response = self.client.post(
            f"/api/ai-signals/{signal.id}/review/",
            {"status": "REVIEWED", "review_note": "Evidence checked; keep records separate pending documents."},
            format="json",
        )
        self.assertEqual(review_response.status_code, 200)
        enrollment_response = self.client.post(
            "/api/enrollments/",
            {"program": program_id, "beneficiary": beneficiary_id, "eligibility_status": "ELIGIBLE", "status": "ENROLLED"},
            format="json",
        )
        self.assertEqual(enrollment_response.status_code, 201)
        approval_response = self.client.patch(
            f"/api/enrollments/{enrollment_response.data['id']}/",
            {"status": "APPROVED"},
            format="json",
        )
        self.assertEqual(approval_response.status_code, 200)

        self.authenticate(self.finance)
        instruction_response = self.client.post(
            "/api/payment-instructions/",
            {
                "batch": batch_response.data["id"],
                "enrollment": enrollment_response.data["id"],
                "beneficiary": beneficiary_id,
                "channel_config": channel_response.data["id"],
                "amount": "50.00",
                "currency": "USD",
            },
            format="json",
        )
        self.assertEqual(instruction_response.status_code, 201)
        instruction_id = instruction_response.data["id"]
        simulation_response = self.client.post(
            f"/api/payment-instructions/{instruction_id}/simulate/",
            {"outcome": "success"},
            format="json",
        )
        self.assertEqual(simulation_response.status_code, 200)
        instruction = PaymentInstruction.objects.get(id=instruction_id)
        anomaly_response = self.client.post("/api/ai/anomalies/", {"batch_id": batch_response.data["id"]}, format="json")
        self.assertEqual(anomaly_response.status_code, 200)
        reconciliation_response = self.client.post(
            "/api/ai/reconcile/",
            {"batch_id": batch_response.data["id"], "provider_report_data": {instruction.provider_reference: {"amount": "50.00", "status": "SUCCESS"}}},
            format="json",
        )
        self.assertEqual(reconciliation_response.status_code, 200)

        self.authenticate(self.field_officer)
        pdm_response = self.client.post(
            "/api/pdm/",
            {"program": program_id, "received_rate": 100, "amount_received": "50.00", "access_problem_rate": 0, "complaint_rate": 0, "satisfaction": 100},
            format="json",
        )
        self.assertEqual(pdm_response.status_code, 201)

        self.authenticate(self.support)
        complaint_response = self.client.post(
            "/api/complaints/",
            {"beneficiary": beneficiary_id, "category": "Information request", "description": "Beneficiary asked about the payment date.", "severity": "LOW", "status": "OPEN"},
            format="json",
        )
        self.assertEqual(complaint_response.status_code, 201)

        self.authenticate(self.manager)
        assign_response = self.client.patch(
            f"/api/complaints/{complaint_response.data['id']}/",
            {"assigned_to": str(self.support.id), "status": "IN_PROGRESS", "resolution_notes": "Assigned for follow-up."},
            format="json",
        )
        self.assertEqual(assign_response.status_code, 200)

        self.authenticate(self.support)
        resolve_response = self.client.patch(
            f"/api/complaints/{complaint_response.data['id']}/",
            {"status": "RESOLVED", "resolution_notes": "Payment date explained to the beneficiary."},
            format="json",
        )
        self.assertEqual(resolve_response.status_code, 200)

        self.authenticate(self.manager)
        manager_dashboard = self.client.get(f"/api/reports/?program={program_id}")
        self.assertEqual(manager_dashboard.status_code, 200)
        self.assertEqual(manager_dashboard.data["dashboards"]["paid"], 1)
        self.assertEqual(manager_dashboard.data["dashboards"]["budget_planned"], "1000.00")
        self.assertEqual(self.client.get("/api/audit-events/").status_code, 403)

        self.authenticate(self.field_officer)
        field_dashboard = self.client.get(f"/api/reports/?program={program_id}")
        self.assertEqual(field_dashboard.status_code, 200)
        self.assertEqual(set(field_dashboard.data["dashboards"]), {"beneficiaries", "approvals"})

        self.authenticate(self.auditor)
        self.assertEqual(self.client.get("/api/audit-events/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/reporting/programs/{program_id}/summary/").status_code, 200)

    def test_ineligible_enrollment_cannot_be_approved(self):
        program = Program.objects.create(
            tenant=self.tenant,
            name="Cash assistance",
            country="Sudan",
            country_code="SD",
            currency="USD",
            reporting_currency="USD",
            transfer_amount="50.00",
            payment_cycle=Program.Cycle.MONTHLY,
            created_by=self.manager,
        )
        self.authenticate(self.field_officer)
        household_response = self.client.post(
            "/api/households/",
            {"program": str(program.id), "household_size": 2, "location": "Omdurman", "registration_date": "2026-09-25"},
            format="json",
        )
        beneficiary_response = self.client.post(
            "/api/beneficiaries/",
            {"household": household_response.data["id"], "number": "BEN-003", "full_name": "Mahmoud Ali", "gender": "M", "consent_given": True},
            format="json",
        )
        self.authenticate(self.reviewer)
        enrollment_response = self.client.post(
            "/api/enrollments/",
            {"program": str(program.id), "beneficiary": beneficiary_response.data["id"], "eligibility_status": "INELIGIBLE", "status": "ENROLLED"},
            format="json",
        )
        self.assertEqual(enrollment_response.status_code, 201)
        response = self.client.patch(
            f"/api/enrollments/{enrollment_response.data['id']}/",
            {"status": "APPROVED"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
