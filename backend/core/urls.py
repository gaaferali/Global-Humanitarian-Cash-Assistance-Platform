from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditEventViewSet,
    BeneficiaryViewSet,
    BudgetViewSet,
    ComplaintViewSet,
    EnrollmentViewSet,
    HouseholdViewSet,
    PaymentBatchViewSet,
    PaymentInstructionViewSet,
    ProgramViewSet,
    ReconciliationItemViewSet,
    ReviewTaskViewSet,
    AdminOnlyTenantUserViewSet,
    imports_view,
    login_view,
    logout_view,
    me_view,
    pdm_summary_view,
    pdm_view,
    program_summary_view,
    registration_sync_view,
    reports_view,
    trigger_deduplication_api,
    trigger_reconciliation_api,
    trigger_anomaly_detection_api,
    AISignalViewSet,
    AutomationRuleViewSet,
    AutomationExecutionViewSet,
    ai_automation_status_view,
)

router = DefaultRouter()
router.register("programs", ProgramViewSet)
router.register("households", HouseholdViewSet)
router.register("beneficiaries", BeneficiaryViewSet)
router.register("enrollments", EnrollmentViewSet)
router.register("payment-instructions", PaymentInstructionViewSet)
router.register("complaints", ComplaintViewSet)
router.register("budgets", BudgetViewSet)
router.register("audit-events", AuditEventViewSet, basename="audit-event")
router.register("users", AdminOnlyTenantUserViewSet, basename="user")
router.register("payment-batches", PaymentBatchViewSet)
router.register("reconciliation-items", ReconciliationItemViewSet)
router.register("review-tasks", ReviewTaskViewSet)
router.register("ai-signals", AISignalViewSet, basename="ai-signal")
router.register("automation-rules", AutomationRuleViewSet, basename="automation-rule")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", login_view),
    path("auth/logout/", logout_view),
    path("me/", me_view),
    path("reports/", reports_view),
    path("reporting/programs/<uuid:program_id>/summary/", program_summary_view),
    path("imports/", imports_view),
    path("pdm/", pdm_view),
    path("pdm/summary/", pdm_summary_view),
    path("sync/registrations/", registration_sync_view),
    
    # مسارات الذكاء الاصطناعي والأتمتة
    path("ai/status/", ai_automation_status_view, name="ai-automation-status"),
    path("ai/deduplicate/<str:beneficiary_id>/", trigger_deduplication_api, name="api-deduplicate"),
    path("ai/reconcile/", trigger_reconciliation_api, name="api-reconcile"),
    path("ai/anomalies/", trigger_anomaly_detection_api, name="api-anomalies"),
]