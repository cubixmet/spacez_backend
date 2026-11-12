from django.db.models import Prefetch
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import MemberProfile
from accounts.permissions import IsAdminRole, IsMemberRole
from billing.models import Invoice, Payment
from billing.serializers import (
    PaymentWriteSerializer,
    invoice_payload,
    member_invoice_payload,
    member_payment_payload,
    payment_payload,
)
from billing.services import generate_invoice, record_payment
from subscriptions.models import Subscription


def _payment_prefetch():
    return Prefetch("payments", queryset=Payment.objects.order_by("-paid_on", "-created_at"))


@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def payments_collection(request):
    if request.method == "GET":
        qs = Payment.objects.select_related("member__user", "invoice")
        member_id = request.query_params.get("memberId")
        method = request.query_params.get("method")
        status_filter = request.query_params.get("status")
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        if member_id:
            qs = qs.filter(member_id=member_id)
        if method:
            qs = qs.filter(method=method)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if date_from:
            qs = qs.filter(paid_on__gte=date_from)
        if date_to:
            qs = qs.filter(paid_on__lte=date_to)
        return Response([payment_payload(p, request) for p in qs])
    serializer = PaymentWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    member = MemberProfile.objects.get(pk=data["memberId"])
    subscription = (
        Subscription.objects.get(pk=data["subscriptionId"])
        if data.get("subscriptionId")
        else member.subscriptions.order_by("-created_at").first()
    )
    invoice = Invoice.objects.filter(pk=data["invoiceId"]).first() if data.get("invoiceId") else None
    payment = record_payment(
        member=member,
        subscription=subscription,
        invoice=invoice,
        amount=data["amount"],
        method=data["method"],
        reference=data.get("reference", ""),
        notes=data.get("notes", ""),
        paid_on=data["paidOn"],
        admin=request.user,
        screenshot=request.FILES.get("screenshot") or data.get("screenshot"),
    )
    return Response(payment_payload(payment, request), status=201)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def invoices_collection(request):
    qs = Invoice.objects.select_related("member__user").prefetch_related("items", _payment_prefetch())
    member_id = request.query_params.get("memberId")
    if member_id:
        qs = qs.filter(member_id=member_id)
    return Response([invoice_payload(inv) for inv in qs])


@api_view(["GET"])
@permission_classes([IsAdminRole])
def invoice_detail(request, invoice_id):
    invoice = (
        Invoice.objects.select_related("member__user")
        .prefetch_related("items", _payment_prefetch())
        .get(pk=invoice_id)
    )
    return Response(invoice_payload(invoice))


@api_view(["POST"])
@permission_classes([IsAdminRole])
def invoice_generate(request):
    subscription_id = request.data.get("subscriptionId")
    sub = Subscription.objects.prefetch_related("items").get(pk=subscription_id)
    invoice = generate_invoice(sub, admin=request.user.full_name)
    invoice = (
        Invoice.objects.select_related("member__user")
        .prefetch_related("items", _payment_prefetch())
        .get(pk=invoice.id)
    )
    return Response(invoice_payload(invoice), status=201)


@api_view(["GET"])
@permission_classes([IsMemberRole])
def member_payments(request):
    profile = request.user.member_profile
    qs = Payment.objects.filter(member=profile).select_related("invoice").prefetch_related("invoice__items")
    return Response([member_payment_payload(p, profile.space_type, request) for p in qs])


@api_view(["GET"])
@permission_classes([IsMemberRole])
def member_invoices(request):
    profile = request.user.member_profile
    qs = Invoice.objects.filter(member=profile).prefetch_related("items", _payment_prefetch())
    return Response([member_invoice_payload(inv) for inv in qs])
