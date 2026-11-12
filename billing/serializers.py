from rest_framework import serializers

from billing.models import Invoice, Payment
from spacez_backend.serialize import fmt_date, iso_id, line_item_payload, media_url


def _latest_payment(invoice: Invoice):
    # Prefer prefetched cache (already ordered via Prefetch); avoid .order_by().first() N+1.
    return next(iter(invoice.payments.all()), None)


def invoice_payload(invoice: Invoice) -> dict:
    payment = _latest_payment(invoice)
    return {
        "id": iso_id(invoice.id),
        "number": invoice.number,
        "memberId": iso_id(invoice.member_id),
        "subscriptionId": iso_id(invoice.subscription_id),
        "periodStart": fmt_date(invoice.period_start),
        "periodEnd": fmt_date(invoice.period_end),
        "items": [line_item_payload(item) for item in invoice.items.all()],
        "total": invoice.total,
        "status": invoice.status,
        "issueDate": fmt_date(invoice.issue_date),
        "kind": invoice.kind,
        "paidOn": fmt_date(payment.paid_on) if payment else None,
    }


def payment_payload(payment: Payment, request=None) -> dict:
    return {
        "id": iso_id(payment.id),
        "memberId": iso_id(payment.member_id),
        "subscriptionId": iso_id(payment.subscription_id),
        "invoiceId": iso_id(payment.invoice_id) if payment.invoice_id else None,
        "amount": payment.amount,
        "paidOn": fmt_date(payment.paid_on),
        "method": payment.method,
        "reference": payment.reference,
        "notes": payment.notes,
        "status": payment.status,
        "screenshotUrl": media_url(request, payment.screenshot),
        "screenshotName": payment.screenshot_name,
    }


def member_payment_payload(payment: Payment, space_type: str, request=None) -> dict:
    invoice = payment.invoice
    return {
        "id": iso_id(payment.id),
        "invoiceNumber": invoice.number if invoice else "—",
        "amount": payment.amount,
        "paidOn": fmt_date(payment.paid_on),
        "dueOn": fmt_date(invoice.issue_date) if invoice else fmt_date(payment.paid_on),
        "method": payment.method,
        "periodStart": fmt_date(invoice.period_start) if invoice else fmt_date(payment.paid_on),
        "periodEnd": fmt_date(invoice.period_end) if invoice else fmt_date(payment.paid_on),
        "status": payment.status,
        "planName": space_type,
        "screenshotUrl": media_url(request, payment.screenshot),
        "items": (
            [{"id": item.code, "label": item.name, "amount": item.amount} for item in invoice.items.all()]
            if invoice
            else []
        ),
    }


def member_invoice_payload(invoice: Invoice) -> dict:
    payment = _latest_payment(invoice)
    return {
        "id": iso_id(invoice.id),
        "number": invoice.number,
        "periodStart": fmt_date(invoice.period_start),
        "periodEnd": fmt_date(invoice.period_end),
        "items": [{"id": item.code, "label": item.name, "amount": item.amount} for item in invoice.items.all()],
        "total": invoice.total,
        "status": invoice.status,
        "issueDate": fmt_date(invoice.issue_date),
        "paidOn": fmt_date(payment.paid_on) if payment else None,
        "kind": invoice.kind,
    }


class PaymentWriteSerializer(serializers.Serializer):
    memberId = serializers.UUIDField()
    subscriptionId = serializers.UUIDField(required=False)
    invoiceId = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.IntegerField(min_value=1)
    method = serializers.CharField()
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    paidOn = serializers.DateField()
    screenshot = serializers.ImageField(required=False, allow_null=True)
