from rest_framework import serializers

from spacez_backend.serialize import fmt_date, fmt_dt, iso_id, line_item_payload
from subscriptions.models import Subscription, SubscriptionEvent


def subscription_payload(sub: Subscription) -> dict:
    return {
        "id": iso_id(sub.id),
        "memberId": iso_id(sub.member_id),
        "spaceType": sub.space_type,
        "items": [line_item_payload(item) for item in sub.items.all()],
        "amount": sub.amount,
        "startDate": fmt_date(sub.start_date),
        "periodStart": fmt_date(sub.period_start),
        "periodEnd": fmt_date(sub.period_end),
        "billingStatus": sub.billing_status,
        "status": sub.status,
    }


def event_payload(event: SubscriptionEvent) -> dict:
    return {
        "id": iso_id(event.id),
        "subscriptionId": iso_id(event.subscription_id),
        "memberId": iso_id(event.member_id),
        "createdAt": fmt_dt(event.created_at),
        "action": event.action,
        "admin": event.admin,
        "oldValue": event.old_value,
        "newValue": event.new_value,
        "adjustment": event.adjustment,
        "note": event.note,
    }


def member_subscription_payload(sub: Subscription, account_status: str) -> dict:
    return {
        "id": iso_id(sub.id),
        "planName": sub.space_type,
        "periodStart": fmt_date(sub.period_start),
        "periodEnd": fmt_date(sub.period_end),
        "renewsOn": fmt_date(sub.period_end),
        "status": account_status,
        "billingStatus": sub.billing_status,
        "items": [{"id": item.code, "label": item.name, "amount": item.amount} for item in sub.items.all()],
        "total": sub.amount,
    }


class SubscriptionCreateSerializer(serializers.Serializer):
    memberId = serializers.UUIDField()
    startDate = serializers.DateField()
    spaceType = serializers.CharField()
    pricingItemIds = serializers.ListField(child=serializers.UUIDField(), min_length=1)


class ChangePlanSerializer(serializers.Serializer):
    pricingItemIds = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    changeDate = serializers.DateField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, default="")
