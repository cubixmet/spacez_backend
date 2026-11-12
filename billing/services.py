from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Q, Sum
from rest_framework.exceptions import ValidationError

from billing.models import Invoice, InvoiceKind, InvoiceLineItem, InvoiceStatus, Payment, PaymentStatus
from ops.models import SiteSettings
from ops.services import actor_name, log_audit, next_invoice_number, notify
from subscriptions.models import BillingStatus, Subscription


def snapshot_items(invoice: Invoice, items):
    for item in items:
        InvoiceLineItem.objects.create(
            invoice=invoice,
            code=item.code,
            name=item.name,
            unit_price=item.unit_price,
            quantity=item.quantity,
            amount=item.amount,
            pricing_item_id=str(item.pricing_item_id) if getattr(item, "pricing_item_id", None) else "",
        )


def generate_invoice(
    subscription: Subscription,
    *,
    kind: str = InvoiceKind.SUBSCRIPTION,
    extra_items=None,
    total=None,
    status=None,
    period_start=None,
    period_end=None,
    issue_date=None,
    admin="System",
) -> Invoice:
    start = period_start or subscription.period_start
    end = period_end or subscription.period_end
    # One subscription invoice per billing period — avoid duplicates from retries / "Generate Invoice".
    if kind == InvoiceKind.SUBSCRIPTION and extra_items is None and total is None:
        existing = (
            subscription.invoices.filter(kind=InvoiceKind.SUBSCRIPTION, period_start=start, period_end=end)
            .order_by("created_at")
            .first()
        )
        if existing:
            return existing

    items = extra_items if extra_items is not None else list(subscription.items.all())
    amount = total if total is not None else subscription.amount
    invoice = Invoice.objects.create(
        number=next_invoice_number(),
        member=subscription.member,
        subscription=subscription,
        period_start=start,
        period_end=end,
        total=amount,
        status=status or subscription.billing_status,
        issue_date=issue_date or start,
        kind=kind,
    )
    snapshot_items(invoice, items)
    log_audit(
        "Invoice generated",
        invoice.number,
        f"{subscription.member.user.full_name} · ₹{invoice.total}",
        admin=admin,
    )
    return invoice


def period_invoices(subscription: Subscription):
    """Subscription + adjustment/credit invoices that belong to the current billing period."""
    return subscription.invoices.filter(
        Q(kind=InvoiceKind.SUBSCRIPTION, period_start=subscription.period_start)
        | Q(kind__in=[InvoiceKind.ADJUSTMENT, InvoiceKind.CREDIT], period_end=subscription.period_end)
    )


def unpaid_charge_invoices(subscription: Subscription):
    return (
        period_invoices(subscription)
        .exclude(kind=InvoiceKind.CREDIT)
        .exclude(status=InvoiceStatus.PAID)
        .order_by("created_at")
    )


def refresh_billing_status(subscription: Subscription, invoice: Invoice | None = None):
    invoices = list(period_invoices(subscription))
    net_due = sum(row.total for row in invoices)
    invoice_ids = [row.id for row in invoices]
    paid_by_invoice = {
        row["invoice_id"]: row["total"]
        for row in Payment.objects.filter(invoice_id__in=invoice_ids, status=PaymentStatus.PAID)
        .values("invoice_id")
        .annotate(total=Sum("amount"))
    }
    paid = sum(paid_by_invoice.values())

    for row in invoices:
        if row.kind == InvoiceKind.CREDIT:
            continue
        row_paid = paid_by_invoice.get(row.id, 0)
        if row_paid >= row.total:
            row_status = InvoiceStatus.PAID
        elif row_paid > 0:
            row_status = InvoiceStatus.PARTIALLY_PAID
        else:
            row_status = InvoiceStatus.DUE
        if row.status != row_status:
            row.status = row_status
            row.save(update_fields=["status"])

    remaining = net_due - paid
    if remaining <= 0:
        status = BillingStatus.PAID
    elif paid > 0:
        status = BillingStatus.PARTIALLY_PAID
    else:
        status = BillingStatus.DUE

    subscription.billing_status = status
    subscription.save(update_fields=["billing_status"])
    return status


@transaction.atomic
def record_payment(
    *,
    member,
    subscription,
    invoice,
    amount: int,
    method: str,
    reference: str,
    notes: str,
    paid_on: date,
    admin,
    screenshot=None,
) -> Payment:
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if subscription.member_id != member.id:
        raise ValidationError("Subscription does not belong to this member.")
    if isinstance(paid_on, str):
        paid_on = date.fromisoformat(paid_on[:10])

    if invoice is None:
        invoice = unpaid_charge_invoices(subscription).first()
    elif invoice.member_id != member.id or invoice.subscription_id != subscription.id:
        raise ValidationError("Invoice does not belong to this member/subscription.")

    payment = Payment.objects.create(
        member=member,
        subscription=subscription,
        invoice=invoice,
        amount=amount,
        method=method,
        reference=reference,
        notes=notes,
        paid_on=paid_on,
        status=PaymentStatus.PAID,
        screenshot=screenshot,
    )
    refresh_billing_status(subscription, invoice)
    name = actor_name(admin)
    log_audit("Payment recorded", member.user.full_name, f"₹{amount} via {method}", admin=name)
    notify(
        "Payment recorded",
        f"₹{amount} received from {member.user.full_name}.",
        "payment",
        enabled=SiteSettings.load().notify_payment,
    )
    return payment
