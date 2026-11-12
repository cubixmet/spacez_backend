from datetime import date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import MemberProfile
from accounts.permissions import IsAdminRole, IsMemberRole
from billing.serializers import invoice_payload
from subscriptions.models import Subscription
from subscriptions.serializers import ChangePlanSerializer, SubscriptionCreateSerializer, event_payload, member_subscription_payload, subscription_payload
from subscriptions.services import cancel_subscription, change_subscription_items, create_subscription, preview_change, renew_subscription


@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
def subscriptions_collection(request):
    if request.method == "GET":
        qs = Subscription.objects.select_related("member__user").prefetch_related("items")
        return Response([subscription_payload(sub) for sub in qs])
    serializer = SubscriptionCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    member = MemberProfile.objects.get(pk=data["memberId"])
    sub = create_subscription(
        member=member,
        start_date=data["startDate"],
        space_type=data["spaceType"],
        pricing_item_ids=data["pricingItemIds"],
        admin=request.user,
    )
    from billing.services import generate_invoice

    invoice = generate_invoice(sub, admin=request.user.full_name)
    return Response({"subscription": subscription_payload(sub), "invoice": invoice_payload(invoice)}, status=201)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def subscription_detail(request, subscription_id):
    sub = Subscription.objects.select_related("member__user").prefetch_related("items", "events").get(pk=subscription_id)
    return Response(
        {
            **subscription_payload(sub),
            "events": [event_payload(event) for event in sub.events.all()],
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminRole])
def subscription_preview(request, subscription_id):
    sub = Subscription.objects.prefetch_related("items").get(pk=subscription_id)
    serializer = ChangePlanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    preview = preview_change(sub, serializer.validated_data["pricingItemIds"], serializer.validated_data.get("changeDate"))
    return Response(
        {
            "oldAmount": preview["oldAmount"],
            "newAmount": preview["newAmount"],
            "totalDays": preview["totalDays"],
            "remainingDays": preview["remainingDays"],
            "dailyRateDelta": preview["dailyRateDelta"],
            "adjustment": preview["adjustment"],
            "items": [
                {"code": i.code, "name": i.name, "unitPrice": i.unit_price, "quantity": i.quantity, "amount": i.amount}
                for i in preview["items"]
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminRole])
def subscription_change(request, subscription_id):
    sub = Subscription.objects.prefetch_related("items").get(pk=subscription_id)
    serializer = ChangePlanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = change_subscription_items(
        sub,
        serializer.validated_data["pricingItemIds"],
        serializer.validated_data.get("changeDate") or date.today(),
        serializer.validated_data.get("note", ""),
        request.user,
    )
    return Response(
        {
            "subscription": subscription_payload(result["subscription"]),
            "invoice": invoice_payload(result["invoice"]) if result["invoice"] else None,
            "preview": {
                "oldAmount": result["preview"]["oldAmount"],
                "newAmount": result["preview"]["newAmount"],
                "totalDays": result["preview"]["totalDays"],
                "remainingDays": result["preview"]["remainingDays"],
                "dailyRateDelta": result["preview"]["dailyRateDelta"],
                "adjustment": result["preview"]["adjustment"],
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminRole])
def subscription_renew(request, subscription_id):
    from billing.models import Invoice, Payment
    from django.db.models import Prefetch

    sub = Subscription.objects.prefetch_related("items").get(pk=subscription_id)
    result = renew_subscription(sub, request.user)
    subscription = Subscription.objects.prefetch_related("items").get(pk=result["subscription"].id)
    invoice = (
        Invoice.objects.select_related("member__user")
        .prefetch_related(
            "items",
            Prefetch("payments", queryset=Payment.objects.order_by("-paid_on", "-created_at")),
        )
        .get(pk=result["invoice"].id)
    )
    return Response(
        {
            "subscription": subscription_payload(subscription),
            "invoice": invoice_payload(invoice),
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminRole])
def subscription_cancel(request, subscription_id):
    sub = Subscription.objects.prefetch_related("items").get(pk=subscription_id)
    cancel_subscription(sub, request.user)
    sub = Subscription.objects.prefetch_related("items").get(pk=subscription_id)
    return Response(subscription_payload(sub))


@api_view(["GET"])
@permission_classes([IsAdminRole])
def subscription_events(request, subscription_id):
    sub = Subscription.objects.prefetch_related("events").get(pk=subscription_id)
    return Response([event_payload(event) for event in sub.events.all()])


@api_view(["GET"])
@permission_classes([IsAdminRole])
def all_subscription_events(request):
    from subscriptions.models import SubscriptionEvent

    return Response([event_payload(event) for event in SubscriptionEvent.objects.all()[:500]])


@api_view(["GET"])
@permission_classes([IsMemberRole])
def member_subscription(request):
    profile = request.user.member_profile
    sub = (
        profile.subscriptions.filter(status="ACTIVE")
        .prefetch_related("items")
        .order_by("-created_at")
        .first()
    )
    if not sub:
        return Response(None)
    return Response(member_subscription_payload(sub, profile.account_status))
