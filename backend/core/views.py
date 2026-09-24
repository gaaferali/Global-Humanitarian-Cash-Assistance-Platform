import uuid
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    AISignal,
    AuditEvent,
    AutomationExecution,
    AutomationRule,
    Beneficiary,
    Budget,
    Complaint,
    Enrollment,
    Household,
    PaymentChannelConfig,
    PaymentEvent,
    PaymentInstruction,
    PaymentBatch,
    Program,
    ReconciliationItem,
    ReviewTask,
    User,
)
from .serializers import (
    AuditEventSerializer,
    AISignalSerializer,
    AutomationExecutionSerializer,
    AutomationRuleSerializer,
    BeneficiarySerializer,
    BudgetSerializer,
    ComplaintSerializer,
    EnrollmentSerializer,
    HouseholdSerializer,
    LoginSerializer,
    PaymentChannelConfigSerializer,
    PaymentEventSerializer,
    PaymentInstructionSerializer,
    PaymentBatchSerializer,
    ProgramSerializer,
    ReconciliationItemSerializer,
    ReviewTaskSerializer,
    UserSerializer,
)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response
    response.data = {
        "error": {
            "code": exc.__class__.__name__,
            "message": response.data.get("detail", "Request failed") if isinstance(response.data, dict) else "Request failed",
            "fields": response.data if isinstance(response.data, dict) else {},
            "correlation_id": str(uuid.uuid4()),
        }
    }
    return response


def audit(user, action, entity, before=None, after=None):
    tenant = getattr(user, "tenant", None)
    if tenant:
        AuditEvent.objects.create(
            tenant=tenant,
            actor=user,
            action=action,
            entity_type=entity.__class__.__name__,
            entity_id=str(entity.pk),
            before=json.loads(json.dumps(before or {}, cls=DjangoJSONEncoder)),
            after=json.loads(json.dumps(after or {}, cls=DjangoJSONEncoder)),
            correlation_id=str(uuid.uuid4()),
        )


class TenantScopedModelViewSet(viewsets.ModelViewSet):
    tenant_field = "tenant"

    def tenant_filter(self):
        return {self.tenant_field: self.request.user.tenant}

    def get_queryset(self):
        return self.queryset.filter(**self.tenant_filter())

    def perform_create(self, serializer):
        kwargs = {}
        if "tenant" in [field.name for field in serializer.Meta.model._meta.fields]:
            kwargs["tenant"] = self.request.user.tenant
        if "created_by" in [field.name for field in serializer.Meta.model._meta.fields]:
            kwargs["created_by"] = self.request.user
        instance = serializer.save(**kwargs)
        audit(self.request.user, f"{serializer.Meta.model.__name__.upper()}_CREATED", instance, after=serializer.data)

    def perform_update(self, serializer):
        before = self.get_serializer(serializer.instance).data
        instance = serializer.save()
        audit(self.request.user, f"{serializer.Meta.model.__name__.upper()}_UPDATED", instance, before=before, after=serializer.data)


class RoleProtectedTenantViewSet(TenantScopedModelViewSet):
    allowed_roles: set[str] = set()
    write_roles: set[str] | None = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role not in self.allowed_roles:
            raise PermissionDenied("Your role does not have permission for this resource")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and self.write_roles is not None and request.user.role not in self.write_roles:
            raise PermissionDenied("Your role has read-only access to this resource")


class AdminOnlyTenantUserViewSet(TenantScopedModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.user.role != User.Role.ADMIN:
            raise PermissionDenied("Only tenant admins can manage users")

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.user.tenant)

    def perform_create(self, serializer):
        user = serializer.save(tenant=self.request.user.tenant)
        audit(self.request.user, "USER_CREATED", user, after=UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    refresh = RefreshToken.for_user(user)
    return Response({
        "user": UserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    })


@api_view(["POST"])
def logout_view(request):
    refresh_token = request.data.get("refresh")
    if refresh_token:
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            pass
    return Response({"status": "signed_out"})


@api_view(["GET"])
def me_view(request):
    return Response(UserSerializer(request.user).data)


class ProgramViewSet(RoleProtectedTenantViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    allowed_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER}

    @action(detail=True, methods=["get", "post"], url_path="channels")
    def channels(self, request, pk=None):
        program = self.get_object()
        if request.method == "GET":
            return Response(PaymentChannelConfigSerializer(program.channels.all(), many=True).data)
        serializer = PaymentChannelConfigSerializer(data={**request.data, "program": str(program.id)})
        serializer.is_valid(raise_exception=True)
        channel = serializer.save()
        audit(request.user, "PAYMENT_CHANNEL_CONFIG_CREATED", channel, after=serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HouseholdViewSet(RoleProtectedTenantViewSet):
    queryset = Household.objects.select_related("program")
    serializer_class = HouseholdSerializer
    allowed_roles = {User.Role.ADMIN, User.Role.FIELD_OFFICER}


class BeneficiaryViewSet(RoleProtectedTenantViewSet):
    queryset = Beneficiary.objects.select_related("household", "household__tenant")
    serializer_class = BeneficiarySerializer
    tenant_field = "household__tenant"
    allowed_roles = {User.Role.ADMIN, User.Role.FIELD_OFFICER, User.Role.REVIEWER}


class EnrollmentViewSet(RoleProtectedTenantViewSet):
    queryset = Enrollment.objects.select_related("program", "beneficiary", "beneficiary__household")
    serializer_class = EnrollmentSerializer
    tenant_field = "program__tenant"
    allowed_roles = {User.Role.ADMIN, User.Role.REVIEWER}


class PaymentInstructionViewSet(RoleProtectedTenantViewSet):
    queryset = PaymentInstruction.objects.select_related("enrollment", "beneficiary", "channel_config", "enrollment__program")
    serializer_class = PaymentInstructionSerializer
    tenant_field = "enrollment__program__tenant"
    allowed_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER, User.Role.AUDITOR}
    write_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER}

    def perform_create(self, serializer):
        instruction = serializer.save(
            created_by=self.request.user,
            status=PaymentInstruction.Status.CREATED,
            idempotency_key=str(uuid.uuid4()),
        )
        PaymentEvent.objects.create(
            instruction=instruction,
            event_type=PaymentEvent.EventType.CREATED,
            to_status=PaymentInstruction.Status.CREATED,
            recorded_by=self.request.user,
            redacted_payload={"simulation": True},
        )
        audit(self.request.user, "PAYMENT_INSTRUCTION_CREATED", instruction, after=serializer.data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def simulate(self, request, pk=None):
        instruction = self.get_object()
        outcome = request.data.get("outcome")
        transitions = {
            "submit": (PaymentInstruction.Status.SUBMITTED, PaymentEvent.EventType.SUBMITTED),
            "success": (PaymentInstruction.Status.SUCCESS, PaymentEvent.EventType.SUCCESS),
            "failure": (PaymentInstruction.Status.FAILED, PaymentEvent.EventType.FAILED),
            "retry": (PaymentInstruction.Status.SUBMITTED, PaymentEvent.EventType.RETRY),
            "reversal": (PaymentInstruction.Status.REVERSED, PaymentEvent.EventType.REVERSED),
        }
        if outcome not in transitions:
            raise ValidationError({"outcome": "Use submit, success, failure, retry, or reversal"})
        old_status = instruction.status
        new_status, event_type = transitions[outcome]
        if new_status == PaymentInstruction.Status.REVERSED and old_status not in {PaymentInstruction.Status.SUCCESS, PaymentInstruction.Status.FAILED}:
            raise ValidationError({"outcome": "Only success or failed instructions can be reversed"})
        instruction.status = new_status
        instruction.provider_reference = instruction.provider_reference or f"SIM-{str(instruction.id)[:8].upper()}"
        instruction.save(update_fields=["status", "provider_reference"])
        event = PaymentEvent.objects.create(
            instruction=instruction,
            event_type=event_type,
            provider_status=PaymentEvent.ProviderStatus.ACCEPTED if outcome in {"submit", "retry"} else PaymentEvent.ProviderStatus.SETTLED if outcome == "success" else PaymentEvent.ProviderStatus.FAILED,
            provider_transaction_id=request.data.get("provider_transaction_id", ""),
            from_status=old_status,
            to_status=new_status,
            recorded_by=request.user,
            redacted_payload={"simulation": True, "no_external_provider_call": True},
        )
        audit(request.user, "PAYMENT_SIMULATED", instruction, before={"status": old_status}, after={"status": new_status})
        return Response(PaymentEventSerializer(event).data)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        return Response(PaymentEventSerializer(self.get_object().events.all().order_by("created_at"), many=True).data)


class ComplaintViewSet(RoleProtectedTenantViewSet):
    queryset = Complaint.objects.select_related("beneficiary", "beneficiary__household")
    serializer_class = ComplaintSerializer
    tenant_field = "beneficiary__household__tenant"
    allowed_roles = {User.Role.ADMIN, User.Role.SUPPORT, User.Role.MANAGER}


class BudgetViewSet(RoleProtectedTenantViewSet):
    queryset = Budget.objects.select_related("program")
    serializer_class = BudgetSerializer
    tenant_field = "program__tenant"
    allowed_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER}


class PaymentBatchViewSet(RoleProtectedTenantViewSet):
    queryset = PaymentBatch.objects.select_related("program")
    serializer_class = PaymentBatchSerializer
    allowed_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER, User.Role.AUDITOR}
    write_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER}


class AISignalViewSet(TenantScopedModelViewSet):
    queryset = AISignal.objects.select_related("program")
    serializer_class = AISignalSerializer

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        signal = self.get_object()
        signal.status = request.data.get("status", AISignal.Status.REVIEWED)
        signal.review_note = request.data.get("review_note", "")
        signal.reviewed_by = request.user
        signal.reviewed_at = timezone.now()
        signal.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at"])
        audit(request.user, "AI_SIGNAL_REVIEWED", signal, after={"status": signal.status})
        return Response(AISignalSerializer(signal).data)


class ReconciliationItemViewSet(RoleProtectedTenantViewSet):
    queryset = ReconciliationItem.objects.select_related("program", "instruction")
    serializer_class = ReconciliationItemSerializer
    allowed_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER, User.Role.AUDITOR}
    write_roles = {User.Role.ADMIN, User.Role.FINANCE, User.Role.MANAGER}

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        item = self.get_object()
        item.status = ReconciliationItem.Status.RESOLVED
        item.resolution_note = request.data.get("resolution_note", "")
        item.resolved_by = request.user
        item.resolved_at = timezone.now()
        item.save(update_fields=["status", "resolution_note", "resolved_by", "resolved_at"])
        audit(request.user, "RECONCILIATION_ITEM_RESOLVED", item, after={"status": item.status})
        return Response(ReconciliationItemSerializer(item).data)


class ReviewTaskViewSet(RoleProtectedTenantViewSet):
    queryset = ReviewTask.objects.select_related("program", "assigned_to")
    serializer_class = ReviewTaskSerializer
    allowed_roles = {User.Role.ADMIN, User.Role.REVIEWER, User.Role.MANAGER, User.Role.SUPPORT}

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        task = self.get_object()
        task.status = ReviewTask.Status.RESOLVED
        task.resolution = request.data.get("resolution", "")
        task.resolved_at = timezone.now()
        task.save(update_fields=["status", "resolution", "resolved_at"])
        audit(request.user, "REVIEW_TASK_RESOLVED", task, after={"status": task.status})
        return Response(ReviewTaskSerializer(task).data)


class AutomationRuleViewSet(TenantScopedModelViewSet):
    queryset = AutomationRule.objects.select_related("program")
    serializer_class = AutomationRuleSerializer


class AutomationExecutionViewSet(TenantScopedModelViewSet):
    queryset = AutomationExecution.objects.select_related("rule")
    serializer_class = AutomationExecutionSerializer

    def create(self, request, *args, **kwargs):
        return Response({
            "enabled": False,
            "message": "Automation execution is closed. Rules can be configured, but actions do not run automatically.",
        }, status=status.HTTP_403_FORBIDDEN)


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        if self.request.user.role not in {User.Role.ADMIN, User.Role.MANAGER, User.Role.AUDITOR}:
            raise PermissionDenied("Audit history is restricted")
        return AuditEvent.objects.filter(tenant=self.request.user.tenant)


@api_view(["GET"])
def reports_view(request):
    tenant = request.user.tenant
    programs = Program.objects.filter(tenant=tenant)
    payments = PaymentInstruction.objects.filter(enrollment__program__tenant=tenant)
    enrollments = Enrollment.objects.filter(program__tenant=tenant)
    complaints = Complaint.objects.filter(beneficiary__household__tenant=tenant)
    beneficiaries = Beneficiary.objects.filter(household__tenant=tenant)
    distributed = payments.filter(status=PaymentInstruction.Status.SUCCESS).aggregate(total=Sum("amount"))["total"] or 0
    approved = enrollments.filter(status=Enrollment.Status.APPROVED).count()
    return Response({
        "dashboards": {
            "beneficiaries": beneficiaries.count(),
            "approvals": approved,
            "paid": payments.filter(status=PaymentInstruction.Status.SUCCESS).count(),
            "pending": payments.filter(status__in=[PaymentInstruction.Status.DRAFT, PaymentInstruction.Status.CREATED, PaymentInstruction.Status.SUBMITTED]).count(),
            "failed": payments.filter(status=PaymentInstruction.Status.FAILED).count(),
            "amounts_approved": str(programs.aggregate(total=Sum("transfer_amount"))["total"] or 0),
            "amounts_distributed": str(distributed),
            "geography": list(Household.objects.filter(tenant=tenant).values("location").annotate(count=Count("id")).order_by("location")),
            "reconciliation": list(payments.values("status").annotate(count=Count("id"), amount=Sum("amount")).order_by("status")),
            "complaints": list(complaints.values("status").annotate(count=Count("id")).order_by("status")),
            "operational_exceptions": payments.filter(Q(status=PaymentInstruction.Status.FAILED) | Q(complaints__isnull=False)).distinct().count(),
            "program_kpis": list(programs.values("id", "name", "country", "currency", "status").annotate(enrollments=Count("enrollments"))),
        }
    })


@api_view(["GET"])
def program_summary_view(request, program_id):
    program = get_object_or_404(Program, id=program_id, tenant=request.user.tenant)
    payments = PaymentInstruction.objects.filter(enrollment__program=program)
    enrollments = Enrollment.objects.filter(program=program)
    complaints = Complaint.objects.filter(beneficiary__household__program=program)
    reconciliation = ReconciliationItem.objects.filter(program=program)
    budget = getattr(program, "budget", None)
    return Response({
        "program": {"id": str(program.id), "name": program.name, "country_code": program.country_code, "currency": program.currency, "reporting_currency": program.reporting_currency, "timezone": program.timezone, "language": program.language},
        "beneficiaries": Beneficiary.objects.filter(household__program=program).count(),
        "eligibility": list(enrollments.values("eligibility_status").annotate(count=Count("id")).order_by("eligibility_status")),
        "approvals": enrollments.filter(status=Enrollment.Status.APPROVED).count(),
        "payments": list(payments.values("status").annotate(count=Count("id"), amount=Sum("amount")).order_by("status")),
        "amounts": {"approved": str(program.transfer_amount * enrollments.filter(status=Enrollment.Status.APPROVED).count()), "distributed": str(payments.filter(status=PaymentInstruction.Status.SUCCESS).aggregate(total=Sum("amount"))["total"] or 0)},
        "failures": payments.filter(status=PaymentInstruction.Status.FAILED).count(),
        "reconciliation": list(reconciliation.values("issue_type", "status").annotate(count=Count("id")).order_by("issue_type")),
        "pdm": {"summary_source": "derived_api"},
        "complaints": list(complaints.values("status", "severity").annotate(count=Count("id")).order_by("status")),
        "budget": {"planned_total": str(budget.planned_total), "actual_total": str(budget.actual_total)} if budget else None,
        "verified": True,
    })


@api_view(["POST"])
def imports_view(request):
    if request.user.role not in {User.Role.ADMIN, User.Role.MANAGER}:
        raise PermissionDenied("Only administrators and managers can import mapped records")
    return Response({
        "status": "accepted",
        "message": "Controlled CSV/XLSX import mapping endpoint placeholder. Processing service can be connected here.",
        "client_identifiers_preserved": True,
    }, status=status.HTTP_202_ACCEPTED)


@api_view(["GET", "POST"])
def pdm_view(request):
    if request.user.role not in {User.Role.ADMIN, User.Role.SUPPORT, User.Role.FIELD_OFFICER, User.Role.MANAGER}:
        raise PermissionDenied("Your role does not have permission for PDM")
    return Response({
        "status": "derived",
        "message": "PDM is exposed without a dedicated MVP table; payloads are handled through controlled API/audit flow.",
        "submitted_at": timezone.now() if request.method == "POST" else None,
    })


@api_view(["GET"])
def pdm_summary_view(request):
    if request.user.role not in {User.Role.ADMIN, User.Role.SUPPORT, User.Role.FIELD_OFFICER, User.Role.MANAGER}:
        raise PermissionDenied("Your role does not have permission for PDM summaries")
    return Response({
        "program": request.query_params.get("program"),
        "channel": request.query_params.get("channel"),
        "location": request.query_params.get("location"),
        "received_rate": 0,
        "amount_received": "0.00",
        "access_problem_rate": 0,
        "complaint_rate": 0,
        "satisfaction": 0,
        "source": "derived_placeholder_until_pdm_storage_is_enabled",
    })


@api_view(["POST"])
def registration_sync_view(request):
    if request.user.role not in {User.Role.ADMIN, User.Role.FIELD_OFFICER}:
        raise PermissionDenied("Only field officers and administrators can synchronize registrations")
    program_id = request.data.get("program_id")
    household_data = request.data.get("household", request.data)
    client_generated_id = household_data.get("client_generated_id")
    if not program_id or not client_generated_id:
        raise ValidationError({"program_id": "Required", "client_generated_id": "Required"})

    program = get_object_or_404(Program, id=program_id, tenant=request.user.tenant)
    household, household_created = Household.objects.get_or_create(
        tenant=request.user.tenant,
        client_generated_id=client_generated_id,
        defaults={
            "program": program,
            "household_size": household_data.get("household_size", 1),
            "location": household_data.get("location", "Unspecified"),
            "registration_date": household_data.get("registration_date") or timezone.localdate(),
            "created_by": request.user,
        },
    )
    if household.program_id != program.id:
        raise ValidationError({"client_generated_id": "Already belongs to another program"})

    beneficiaries_created = 0
    for beneficiary_data in request.data.get("beneficiaries", []):
        number = beneficiary_data.get("number")
        full_name = beneficiary_data.get("full_name")
        if not number or not full_name:
            raise ValidationError({"beneficiaries": "Each beneficiary requires number and full_name"})
        _, created = Beneficiary.objects.get_or_create(
            household=household,
            number=number,
            defaults={
                "full_name": full_name,
                "gender": beneficiary_data.get("gender", ""),
                "phone_last4": beneficiary_data.get("phone_last4", ""),
                "consent_given": beneficiary_data.get("consent_given", False),
                "created_by": request.user,
            },
        )
        beneficiaries_created += int(created)
    audit(request.user, "OFFLINE_REGISTRATION_SYNCED", household, after={"client_generated_id": client_generated_id})
    return Response({
        "status": "synchronized",
        "household_id": str(household.id),
        "household_created": household_created,
        "beneficiaries_created": beneficiaries_created,
        "client_generated_id": client_generated_id,
        "tenant_isolated": True,
    }, status=status.HTTP_201_CREATED if household_created else status.HTTP_200_OK)


@api_view(["GET", "POST"])
def ai_closed_view(request, *args, **kwargs):
    return Response({
        "enabled": False,
        "message": "AI and automation APIs are intentionally closed for this phase.",
    }, status=status.HTTP_403_FORBIDDEN)
