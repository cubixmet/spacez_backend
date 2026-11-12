from datetime import date, timedelta

from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import MemberProfile
from accounts.permissions import IsAdminRole, IsMemberRole
from attendance.models import AttendanceRecord
from billing.models import Invoice, Payment
from catalog.models import PricingItem
from catalog.serializers import pricing_payload
from ops.models import AuditLog, ContactMessage, EmailLog, Enquiry, Notification, SiteSettings
from ops.serializers import (
    ContactSerializer,
    EnquirySerializer,
    SettingsSerializer,
    audit_payload,
    email_payload,
    notification_payload,
    settings_payload,
)
from ops.services import log_audit
from subscriptions.models import Subscription


@api_view(["GET", "PATCH"])
@permission_classes([IsAdminRole])
def settings_view(request):
    obj = SiteSettings.load()
    if request.method == "GET":
        return Response(settings_payload(obj))
    serializer = SettingsSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    mapping = {
        "spaceName": "space_name",
        "poweredBy": "powered_by",
        "address": "address",
        "supportEmail": "support_email",
        "supportPhone": "support_phone",
        "currency": "currency",
        "invoicePrefix": "invoice_prefix",
        "billingRule": "billing_rule",
        "gracePeriodDays": "grace_period_days",
        "allowAdminAttendanceEdit": "allow_admin_attendance_edit",
        "allowMemberClockOutEdit": "allow_member_clock_out_edit",
        "defaultAttendanceStatus": "default_attendance_status",
        "notifyNewMember": "notify_new_member",
        "notifyPayment": "notify_payment",
        "notifyBillingDue": "notify_billing_due",
        "notifyAttendance": "notify_attendance",
    }
    for key, field in mapping.items():
        if key in serializer.validated_data:
            setattr(obj, field, serializer.validated_data[key])
    obj.save()
    log_audit("Settings updated", "Space Z", ", ".join(serializer.validated_data.keys()), admin=request.user.full_name)
    return Response(settings_payload(obj))


@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
def notifications_collection(request):
    qs = Notification.objects.filter(member__isnull=True)
    if request.method == "GET":
        return Response([notification_payload(n) for n in qs])
    qs.update(read=True)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAdminRole])
def notifications_read_all(request):
    Notification.objects.filter(member__isnull=True, read=False).update(read=True)
    return Response({"ok": True})


def _paginated(qs, request, payload_fn, default_size=10):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(request.query_params.get("pageSize", default_size))))
    except (TypeError, ValueError):
        page_size = default_size
    count = qs.count()
    start = (page - 1) * page_size
    results = [payload_fn(item) for item in qs[start : start + page_size]]
    total_pages = max(1, (count + page_size - 1) // page_size) if count else 1
    return Response(
        {
            "results": results,
            "count": count,
            "page": page,
            "pageSize": page_size,
            "totalPages": total_pages,
        }
    )


@api_view(["GET"])
@permission_classes([IsAdminRole])
def audit_logs(request):
    return _paginated(AuditLog.objects.all(), request, audit_payload)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def email_logs(request):
    return Response([email_payload(log) for log in EmailLog.objects.all()[:200]])


def _hours(clock_in, clock_out) -> float:
    if not clock_in or not clock_out:
        return 0
    start = clock_in.hour * 60 + clock_in.minute
    end = clock_out.hour * 60 + clock_out.minute
    return max(0, (end - start) / 60)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def reports(request):
    from collections import defaultdict

    today = date.today()
    date_from = date.fromisoformat(request.query_params["from"]) if request.query_params.get("from") else today.replace(day=1)
    date_to = date.fromisoformat(request.query_params["to"]) if request.query_params.get("to") else today
    payments = list(Payment.objects.filter(paid_on__range=(date_from, date_to)))
    invoices = Invoice.objects.filter(issue_date__range=(date_from, date_to))
    attendance_rows = list(AttendanceRecord.objects.filter(date__range=(date_from, date_to)))
    revenue = sum(p.amount for p in payments)
    billed = invoices.aggregate(total=Sum("total"))["total"] or 0
    hours = sum(_hours(a.clock_in, a.clock_out) for a in attendance_rows)
    by_method = {}
    for payment in payments:
        by_method[payment.method] = by_method.get(payment.method, 0) + payment.amount

    by_member_id = defaultdict(list)
    for row in attendance_rows:
        by_member_id[row.member_id].append(row)
    members_map = {
        m.id: m
        for m in MemberProfile.objects.select_related("user").filter(id__in=by_member_id.keys())
    }
    attendance_by_member = []
    for member_id, rows in by_member_id.items():
        member = members_map.get(member_id)
        if not member:
            continue
        attendance_by_member.append(
            {
                "memberId": str(member.id),
                "fullName": member.user.full_name,
                "days": len(rows),
                "hours": round(sum(_hours(a.clock_in, a.clock_out) for a in rows)),
            }
        )
    attendance_by_member.sort(key=lambda row: row["days"], reverse=True)
    attendance_count = len(attendance_rows)
    return Response(
        {
            "revenue": revenue,
            "billed": billed,
            "outstanding": max(0, billed - revenue),
            "averageHours": round(hours / attendance_count, 1) if attendance_count else 0,
            "byMethod": by_method,
            "newMembers": MemberProfile.objects.filter(created_at__range=(date_from, date_to)).count(),
            "attendanceCount": attendance_count,
            "attendanceByMember": attendance_by_member,
        }
    )


@api_view(["GET"])
@permission_classes([IsAdminRole])
def dashboard(request):
    today = date.today()
    month_start = today.replace(day=1)
    members = MemberProfile.objects.all()
    active_count = members.filter(account_status="ACTIVE").count()
    total_count = members.count()
    revenue = Payment.objects.filter(paid_on__gte=month_start).aggregate(total=Sum("amount"))["total"] or 0
    due = Subscription.objects.filter(status="ACTIVE").exclude(billing_status="PAID").count()
    today_att = AttendanceRecord.objects.filter(date=today)
    return Response(
        {
            "totalMembers": total_count,
            "activeMembers": active_count,
            "inactiveMembers": total_count - active_count,
            "currentMonthRevenue": revenue,
            "paymentsDue": due,
            "todaysAttendance": today_att.count(),
            "currentlyCheckedIn": today_att.filter(clock_in__isnull=False, clock_out__isnull=True).count(),
            "paid": Subscription.objects.filter(billing_status="PAID").count(),
            "due": Subscription.objects.filter(billing_status="DUE").count(),
            "partiallyPaid": Subscription.objects.filter(billing_status="PARTIALLY_PAID").count(),
        }
    )


@api_view(["GET"])
@permission_classes([IsMemberRole])
def member_notifications(request):
    profile = request.user.member_profile
    stored = Notification.objects.filter(member=profile)
    items = [notification_payload(n) for n in stored]
    sub = profile.subscriptions.filter(status="ACTIVE").first()
    if sub and sub.billing_status in {"DUE", "PARTIALLY_PAID"}:
        items.insert(
            0,
            {
                "id": "gen_due",
                "title": "Payment is due for your Space Z membership.",
                "body": "Payment is due for your current billing period. You can still use the space and clock in.",
                "createdAt": f"{sub.period_start.isoformat()}T08:00:00",
                "kind": "billing",
                "read": False,
            },
        )
    if sub:
        days = (sub.period_end - date.today()).days
        if days == 0:
            items.insert(
                0,
                {
                    "id": "gen_started",
                    "title": "Your new billing period has started.",
                    "body": f"Billing period {sub.period_start} → {sub.period_end}.",
                    "createdAt": date.today().isoformat(),
                    "kind": "renewal",
                    "read": False,
                },
            )
        elif 0 < days <= 3:
            items.insert(
                0,
                {
                    "id": "gen_3",
                    "title": "Your membership renews in 3 days.",
                    "body": "Your Space Z membership renews shortly. Keep your billing up to date.",
                    "createdAt": date.today().isoformat(),
                    "kind": "renewal",
                    "read": False,
                },
            )
        elif 3 < days <= 7:
            items.insert(
                0,
                {
                    "id": "gen_7",
                    "title": "Your Space Z membership renews in 7 days.",
                    "body": f"Current period ends {sub.period_end}.",
                    "createdAt": date.today().isoformat(),
                    "kind": "renewal",
                    "read": False,
                },
            )
    return Response(items)


@api_view(["POST"])
@permission_classes([IsMemberRole])
def member_notifications_read(request):
    Notification.objects.filter(member=request.user.member_profile).update(read=True)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def public_enquiry(request):
    serializer = EnquirySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    Enquiry.objects.create(
        full_name=data["fullName"],
        phone=data["phone"],
        email=data["email"],
        space_type=data["spaceType"],
        add_ons=data.get("addOns", []),
        message=data.get("message", ""),
        estimated_total=data.get("estimatedTotal", 0),
    )
    return Response({"detail": "Thanks! Your Space Z request has been received. Our team will contact you shortly."}, status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
def public_contact(request):
    serializer = ContactSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    ContactMessage.objects.create(name=data["name"], email=data["email"], phone=data["phone"], message=data["message"])
    return Response({"detail": "Thanks! Your message has been received. We'll reply shortly."}, status=201)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_plans(request):
    items = PricingItem.objects.filter(active=True)
    grouped = {"Co-working": [], "Student": []}
    for item in items:
        grouped.setdefault(item.space_type, []).append(pricing_payload(item))
    return Response(grouped)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "service": "Space Z API", "poweredBy": "Cubixmet"})
