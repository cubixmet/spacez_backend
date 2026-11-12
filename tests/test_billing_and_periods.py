import pytest
from datetime import date

from django.test.utils import CaptureQueriesContext
from django.db import connection


@pytest.mark.django_db
def test_period_anniversary_month_end():
    from spacez_backend.periods import period_from_start, next_period

    p = period_from_start(date(2026, 1, 31), anchor_day=31)
    assert p.end == date(2026, 2, 27)
    p2 = next_period(p.end, anchor_day=31)
    assert p2.start == date(2026, 2, 28)
    p3 = next_period(p2.end, anchor_day=31)
    assert p3.start == date(2026, 3, 31)


@pytest.mark.django_db
def test_generate_invoice_idempotent(admin_client, seeded_db):
    from subscriptions.models import Subscription

    sub = Subscription.objects.filter(status="ACTIVE").first()
    first = admin_client.post("/api/admin/invoices/generate/", {"subscriptionId": str(sub.id)}, format="json")
    second = admin_client.post("/api/admin/invoices/generate/", {"subscriptionId": str(sub.id)}, format="json")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["id"] == second.data["id"]
    assert first.data["number"] == second.data["number"]


@pytest.mark.django_db
def test_payment_rejects_mismatched_subscription(admin_client, seeded_db):
    from accounts.models import MemberProfile
    from subscriptions.models import Subscription

    john = MemberProfile.objects.get(user__email="john@spacez.in")
    other_sub = Subscription.objects.exclude(member=john).first()
    response = admin_client.post(
        "/api/admin/payments/",
        {
            "memberId": str(john.id),
            "subscriptionId": str(other_sub.id),
            "amount": 100,
            "method": "UPI",
            "reference": "x",
            "notes": "",
            "paidOn": "2026-09-15",
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_payment_updates_billing_across_period_invoices(admin_client, seeded_db):
    from accounts.models import MemberProfile
    from billing.models import Invoice, InvoiceKind, InvoiceStatus
    from billing.services import generate_invoice, refresh_billing_status
    from subscriptions.models import BillingStatus

    john = MemberProfile.objects.get(user__email="john@spacez.in")
    sub = john.subscriptions.filter(status="ACTIVE").first()
    main = generate_invoice(sub, admin="test")
    # Simulate unpaid adjustment for current period
    from types import SimpleNamespace

    adj = generate_invoice(
        sub,
        kind=InvoiceKind.ADJUSTMENT,
        extra_items=[
            SimpleNamespace(
                code="proration-charge",
                name="Proration",
                unit_price=200,
                quantity=1,
                amount=200,
                pricing_item_id="",
            )
        ],
        total=200,
        status=InvoiceStatus.DUE,
        period_start=sub.period_start,
        period_end=sub.period_end,
        issue_date=sub.period_start,
        admin="test",
    )
    # Pay only the adjustment — subscription should not become fully PAID if main unpaid
    admin_client.post(
        "/api/admin/payments/",
        {
            "memberId": str(john.id),
            "subscriptionId": str(sub.id),
            "invoiceId": str(adj.id),
            "amount": 200,
            "method": "UPI",
            "reference": "adj",
            "notes": "",
            "paidOn": str(sub.period_start),
        },
        format="json",
    )
    sub.refresh_from_db()
    assert sub.billing_status != BillingStatus.PAID


@pytest.mark.django_db
def test_admin_invoices_query_budget(admin_client, seeded_db):
    # Warm caches / auth
    admin_client.get("/api/admin/invoices/")
    with CaptureQueriesContext(connection) as ctx:
        response = admin_client.get("/api/admin/invoices/")
    assert response.status_code == 200
    assert len(response.data) >= 1
    # Should be constant-ish: auth user + invoices + items + payments (not per-row payments)
    assert len(ctx) <= 12, f"Too many queries ({len(ctx)}): {[q['sql'][:80] for q in ctx.captured_queries]}"


@pytest.mark.django_db
def test_admin_members_query_budget(admin_client, seeded_db):
    admin_client.get("/api/admin/members/")
    with CaptureQueriesContext(connection) as ctx:
        response = admin_client.get("/api/admin/members/")
    assert response.status_code == 200
    assert len(ctx) <= 10, f"Too many queries ({len(ctx)})"


@pytest.mark.django_db
def test_admin_attendance_query_budget(admin_client, seeded_db):
    admin_client.get("/api/admin/attendance/")
    with CaptureQueriesContext(connection) as ctx:
        response = admin_client.get("/api/admin/attendance/")
    assert response.status_code == 200
    assert len(ctx) <= 10, f"Too many queries ({len(ctx)})"


@pytest.mark.django_db
def test_member_delete(admin_client, seeded_db):
    from accounts.models import MemberProfile, User

    member = MemberProfile.objects.get(user__email="rahul@spacez.in")
    mid = member.id
    uid = member.user_id
    response = admin_client.delete(f"/api/admin/members/{mid}/")
    assert response.status_code == 204
    assert not MemberProfile.objects.filter(pk=mid).exists()
    assert not User.objects.filter(pk=uid).exists()


@pytest.mark.django_db
def test_duplicate_email_on_patch(admin_client, seeded_db):
    from accounts.models import MemberProfile

    member = MemberProfile.objects.get(user__email="rahul@spacez.in")
    response = admin_client.patch(
        f"/api/admin/members/{member.id}/",
        {"email": "john@spacez.in"},
        format="json",
    )
    assert response.status_code == 400
