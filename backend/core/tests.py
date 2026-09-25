from django.test import TestCase
from rest_framework.test import APIClient

from .models import Program, ProgramActivity, Tenant, User


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
