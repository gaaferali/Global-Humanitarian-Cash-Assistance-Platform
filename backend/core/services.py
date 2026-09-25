from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import (
    AISignal,
    Beneficiary,
    PaymentBatch,
    PaymentEvent,
    ReconciliationItem,
    ReviewTask,
)


def _review_task(tenant, program, task_type, entity_type, entity_id, priority, resolution):
    task, _ = ReviewTask.objects.get_or_create(
        tenant=tenant,
        program=program,
        task_type=task_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        status__in=[ReviewTask.Status.OPEN, ReviewTask.Status.ASSIGNED],
        defaults={"priority": priority, "resolution": resolution},
    )
    return task


def run_deduplication_check(beneficiary):
    """Create advisory duplicate signals and human review tasks for one beneficiary."""
    household = beneficiary.household
    candidates = Beneficiary.objects.filter(
        household__tenant=household.tenant,
        household__program=household.program,
    ).exclude(pk=beneficiary.pk)
    conditions = Q()
    if beneficiary.national_id_hash:
        conditions |= Q(national_id_hash=beneficiary.national_id_hash)
    if beneficiary.phone_last4:
        conditions |= Q(phone_last4=beneficiary.phone_last4)
    if beneficiary.full_name:
        conditions |= Q(full_name__iexact=beneficiary.full_name)

    matches = list(candidates.filter(conditions).distinct())
    signals = []
    for duplicate in matches:
        same_id = bool(beneficiary.national_id_hash and beneficiary.national_id_hash == duplicate.national_id_hash)
        same_phone = bool(beneficiary.phone_last4 and beneficiary.phone_last4 == duplicate.phone_last4)
        same_name = beneficiary.full_name.casefold() == duplicate.full_name.casefold()
        score = Decimal("0.98") if same_id else Decimal("0.90") if same_phone and same_name else Decimal("0.75")
        signal, _ = AISignal.objects.update_or_create(
            tenant=household.tenant,
            program=household.program,
            entity_type="BENEFICIARY",
            entity_id=str(beneficiary.pk),
            signal_type="POSSIBLE_DUPLICATE",
            defaults={
                "score": score,
                "confidence": score,
                "reason": "Potential duplicate detected; human review is required.",
                "evidence": {"matched_beneficiary_id": str(duplicate.pk), "same_national_id": same_id, "same_phone_last4": same_phone, "same_name": same_name},
                "model_version": "dedup-v1",
                "rule_version": "dedup-rules-v1",
                "status": AISignal.Status.OPEN,
            },
        )
        _review_task(household.tenant, household.program, ReviewTask.TaskType.DUPLICATE_REVIEW, "BENEFICIARY", beneficiary.pk, ReviewTask.Priority.HIGH, f"Review possible duplicate {duplicate.pk}.")
        signals.append(signal)
    return {"matches": len(matches), "signals": signals}


def run_anomaly_detection(batch):
    """Create advisory payment risk signals; never changes eligibility or payment status."""
    signals = []
    for instruction in batch.instructions.select_related("enrollment__program").all():
        if instruction.amount <= Decimal("500.00"):
            continue
        signal, _ = AISignal.objects.update_or_create(
            tenant=batch.tenant,
            program=batch.program,
            entity_type="PAYMENT_INSTRUCTION",
            entity_id=str(instruction.pk),
            signal_type="HIGH_AMOUNT_ANOMALY",
            defaults={
                "score": Decimal("0.85"),
                "confidence": Decimal("0.80"),
                "reason": "Payment amount exceeds the configured advisory threshold.",
                "evidence": {"amount": str(instruction.amount), "threshold": "500.00", "currency": instruction.currency},
                "model_version": "anomaly-v1",
                "rule_version": "amount-threshold-v1",
                "status": AISignal.Status.OPEN,
            },
        )
        _review_task(batch.tenant, batch.program, ReviewTask.TaskType.RISK_REVIEW, "PAYMENT_INSTRUCTION", instruction.pk, ReviewTask.Priority.HIGH, "Review advisory high-value payment signal before any human decision.")
        signals.append(signal)
    return signals


def run_automated_reconciliation(batch, provider_report_data):
    """Compare simulated provider records and persist reconciliation items."""
    summary = {"matched": 0, "pending": 0, "discrepancies": 0, "items": []}
    events = PaymentEvent.objects.filter(instruction__batch=batch).select_related("instruction")
    for event in events:
        record = provider_report_data.get(event.provider_transaction_id or event.instruction.provider_reference)
        if not record:
            issue_type = ReconciliationItem.IssueType.MISSING_REFERENCE
            summary["pending"] += 1
            actual_amount = None
            actual_status = "MISSING"
        else:
            actual_amount = Decimal(str(record.get("amount", "0")))
            actual_status = str(record.get("status", "UNKNOWN")).upper()
            if actual_status == "SUCCESS" and actual_amount == event.instruction.amount:
                summary["matched"] += 1
                continue
            issue_type = ReconciliationItem.IssueType.FAILED if actual_status == "FAILED" else ReconciliationItem.IssueType.AMOUNT_MISMATCH if actual_amount != event.instruction.amount else ReconciliationItem.IssueType.STATUS_MISMATCH
            summary["discrepancies"] += 1
        item, _ = ReconciliationItem.objects.update_or_create(
            tenant=batch.tenant,
            program=batch.program,
            instruction=event.instruction,
            issue_type=issue_type,
            defaults={
                "expected_amount": event.instruction.amount,
                "actual_amount": actual_amount,
                "expected_status": event.instruction.status,
                "actual_status": actual_status,
                "provider_reference": event.provider_transaction_id or event.instruction.provider_reference,
                "status": ReconciliationItem.Status.OPEN,
            },
        )
        _review_task(batch.tenant, batch.program, ReviewTask.TaskType.RECONCILIATION, "PAYMENT_INSTRUCTION", event.instruction.pk, ReviewTask.Priority.HIGH, "Reconciliation discrepancy requires human resolution.")
        summary["items"].append(str(item.pk))
    return summary


def verified_program_summary(program):
    from .models import Beneficiary, Complaint, Enrollment, PaymentInstruction
    payments = PaymentInstruction.objects.filter(enrollment__program=program)
    enrollments = Enrollment.objects.filter(program=program)
    return {
        "beneficiaries": Beneficiary.objects.filter(household__program=program).count(),
        "eligibility": list(enrollments.values("eligibility_status").order_by("eligibility_status")),
        "approvals": enrollments.filter(status=Enrollment.Status.APPROVED).count(),
        "payments": list(payments.values("status").order_by("status")),
        "amounts": {"approved": str(program.transfer_amount * enrollments.filter(status=Enrollment.Status.APPROVED).count()), "distributed": str(sum((p.amount for p in payments.filter(status=PaymentInstruction.Status.SUCCESS)), Decimal("0")))},
        "failures": payments.filter(status=PaymentInstruction.Status.FAILED).count(),
        "complaints": Complaint.objects.filter(beneficiary__household__program=program).count(),
        "verified_at": timezone.now(),
    }
