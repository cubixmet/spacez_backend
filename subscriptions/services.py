from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from django.db import transaction
from rest_framework.exceptions import ValidationError

from billing.models import InvoiceKind, InvoiceStatus
from billing.services import generate_invoice
from catalog.services import line_payload, resolve_pricing_items
from ops.services import actor_name, log_audit, notify
from spacez_backend.periods import current_period_for, next_period, parse_iso_date, prorate
from subscriptions.models import (
    BillingStatus,
    Subscription,
    SubscriptionAction,
    SubscriptionItem,
    SubscriptionEvent,
    SubscriptionStatus,
)


def describe_items(items) -> str:
    names = ", ".join(item.name for item in items)
    total = sum(item.amount for item in items)
    return f"{names} · ₹{total}"


def add_event(subscription: Subscription, action: str, old_value: str, new_value: str, adjustment: int, admin: str, note: str = ""):
    return SubscriptionEvent.objects.create(
        subscription=subscription,
        member=subscription.member,
        action=action,
        admin=admin,
        old_value=old_value,
        new_value=new_value,
        adjustment=adjustment,
        note=note,
    )


def replace_items(subscription: Subscription, pricing_items):
    subscription.items.all().delete()
    created = []
    for item in pricing_items:
        payload = line_payload(item)
        created.append(
            SubscriptionItem.objects.create(
                subscription=subscription,
                pricing_item=item,
                code=payload["code"],
                name=payload["name"],
                unit_price=payload["unit_price"],
                quantity=payload["quantity"],
                amount=payload["amount"],
            )
        )
    subscription.amount = sum(row.amount for row in created)
    subscription.save(update_fields=["amount"])
    return created


@transaction.atomic
def create_subscription(*, member, start_date: date, space_type: str, pricing_item_ids: list, admin) -> Subscription:
    start_date = parse_iso_date(start_date)
    if member.subscriptions.filter(status=SubscriptionStatus.ACTIVE).exists():
        raise ValidationError("Member already has an active subscription.")
    items = resolve_pricing_items(pricing_item_ids, space_type=space_type)
    if not items:
        raise ValidationError("Select at least one pricing item.")
    period = current_period_for(start_date)
    subscription = Subscription.objects.create(
        member=member,
        space_type=space_type,
        amount=0,
        start_date=start_date,
        period_start=period.start,
        period_end=period.end,
        billing_status=BillingStatus.DUE,
        status=SubscriptionStatus.ACTIVE,
    )
    created_items = replace_items(subscription, items)
    add_event(subscription, SubscriptionAction.CREATED, "—", describe_items(created_items), 0, actor_name(admin))
    return subscription


def preview_change(subscription: Subscription, pricing_item_ids: list, change_date: date | None = None) -> dict:
    items = resolve_pricing_items(pricing_item_ids, space_type=subscription.space_type)
    payloads = [line_payload(item) for item in items]
    new_amount = sum(p["amount"] for p in payloads)
    result = prorate(
        old_amount=subscription.amount,
        new_amount=new_amount,
        period_start=subscription.period_start,
        period_end=subscription.period_end,
        change_date=change_date or date.today(),
    )
    preview_items = [SimpleNamespace(**p) for p in payloads]
    return {
        "subscription": subscription,
        "items": preview_items,
        "pricing_items": items,
        "totalDays": result.total_days,
        "remainingDays": result.remaining_days,
        "dailyRateDelta": result.daily_rate_delta,
        "amountDelta": result.amount_delta,
        "adjustment": result.adjustment,
        "oldAmount": result.old_amount,
        "newAmount": result.new_amount,
    }


@transaction.atomic
def change_subscription_items(subscription: Subscription, pricing_item_ids: list, change_date: date, note: str, admin) -> dict:
    preview = preview_change(subscription, pricing_item_ids, change_date)
    old_description = describe_items(subscription.items.all())
    is_upgrade = preview["newAmount"] > preview["oldAmount"]
    if preview["newAmount"] == preview["oldAmount"]:
        action = SubscriptionAction.PRICE_CHANGED
    elif is_upgrade:
        action = SubscriptionAction.UPGRADED
    else:
        action = SubscriptionAction.DOWNGRADED

    created = replace_items(subscription, preview["pricing_items"])
    add_event(subscription, action, old_description, describe_items(created), preview["adjustment"], actor_name(admin), note)

    invoice = None
    if preview["adjustment"] != 0:
        extra = [
            SimpleNamespace(
                code="proration-charge" if is_upgrade else "proration-credit",
                name=(
                    f"Prorated {'upgrade charge' if is_upgrade else 'downgrade credit'} "
                    f"({preview['remainingDays']} of {preview['totalDays']} days)"
                ),
                unit_price=preview["adjustment"],
                quantity=1,
                amount=preview["adjustment"],
                pricing_item_id="",
            )
        ]
        invoice = generate_invoice(
            subscription,
            kind=InvoiceKind.ADJUSTMENT if is_upgrade else InvoiceKind.CREDIT,
            extra_items=extra,
            total=preview["adjustment"],
            status=InvoiceStatus.DUE if is_upgrade else InvoiceStatus.CREDIT,
            period_start=change_date,
            period_end=subscription.period_end,
            issue_date=change_date,
            admin=actor_name(admin),
        )
        if is_upgrade:
            subscription.billing_status = BillingStatus.DUE
            subscription.save(update_fields=["billing_status"])

    log_audit(
        f"Subscription {action.lower()}",
        subscription.member.user.full_name,
        f"{old_description} → {describe_items(created)} · adjustment ₹{preview['adjustment']}",
        admin=actor_name(admin),
    )
    notify(
        f"Subscription {action.lower()}",
        f"{subscription.member.user.full_name}: new recurring ₹{preview['newAmount']}",
        "subscription",
        enabled=True,
    )
    return {"subscription": subscription, "invoice": invoice, "preview": preview}


@transaction.atomic
def renew_subscription(subscription: Subscription, admin) -> dict:
    if subscription.status == SubscriptionStatus.CANCELLED:
        raise ValidationError("Reactivate or create a new subscription before renewing a cancelled plan.")
    previous = f"{subscription.period_start} → {subscription.period_end}"
    period = next_period(subscription.period_end, anchor_day=subscription.start_date.day)
    subscription.period_start = period.start
    subscription.period_end = period.end
    subscription.billing_status = BillingStatus.DUE
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.save()
    add_event(
        subscription,
        SubscriptionAction.RENEWED,
        previous,
        f"{period.start} → {period.end}",
        subscription.amount,
        actor_name(admin),
    )
    invoice = generate_invoice(subscription, admin=actor_name(admin))
    log_audit(
        "Subscription renewed",
        subscription.member.user.full_name,
        f"New period {previous} → {period.start}",
        admin=actor_name(admin),
    )
    return {"subscription": subscription, "invoice": invoice}


def cancel_subscription(subscription: Subscription, admin) -> Subscription:
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.save(update_fields=["status"])
    add_event(subscription, SubscriptionAction.CANCELLED, describe_items(subscription.items.all()), "Cancelled", 0, actor_name(admin))
    log_audit("Subscription cancelled", subscription.member.user.full_name, "Marked cancelled", admin=actor_name(admin))
    return subscription
