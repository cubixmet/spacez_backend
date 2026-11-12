import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection


@pytest.mark.django_db
def test_admin_login_ok(api, seeded_db):
    response = api.post(
        "/api/auth/admin/login/",
        {"email": "admin@spacez.in", "password": "spacez@admin"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert response.data["admin"]["email"] == "admin@spacez.in"


@pytest.mark.django_db
def test_admin_login_rejects_member(api, seeded_db):
    response = api.post(
        "/api/auth/member/login/",
        {"email": "john@spacez.in", "password": "spacez123"},
        format="json",
    )
    assert response.status_code == 200
    token = response.data["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    blocked = api.get("/api/admin/members/")
    assert blocked.status_code in (401, 403)


@pytest.mark.django_db
def test_member_login_rejects_bad_password(api, seeded_db):
    response = api.post(
        "/api/auth/member/login/",
        {"email": "john@spacez.in", "password": "wrong"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_suspended_member_cannot_login(api, seeded_db, admin_client):
    from accounts.models import MemberProfile

    member = MemberProfile.objects.get(user__email="john@spacez.in")
    admin_client.post(
        f"/api/admin/members/{member.id}/status/",
        {"status": "SUSPENDED", "reason": "test"},
        format="json",
    )
    response = api.post(
        "/api/auth/member/login/",
        {"email": "john@spacez.in", "password": "spacez123"},
        format="json",
    )
    assert response.status_code == 400
    assert "not active" in str(response.data).lower()


@pytest.mark.django_db
def test_password_reset_sends_magic_link(api, seeded_db, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail
    from accounts.models import MagicLink

    before = MagicLink.objects.count()
    response = api.post("/api/auth/password-reset/", {"email": "john@spacez.in"}, format="json")
    assert response.status_code == 200
    assert MagicLink.objects.count() == before + 1
    assert len(mail.outbox) == 1
    assert "sign in" in mail.outbox[0].body.lower() or "password" in mail.outbox[0].subject.lower()


@pytest.mark.django_db
def test_active_due_member_can_clock_in(member_client, seeded_db):
    from accounts.models import MemberProfile
    from subscriptions.models import BillingStatus

    member = MemberProfile.objects.get(user__email="john@spacez.in")
    sub = member.subscriptions.filter(status="ACTIVE").first()
    sub.billing_status = BillingStatus.DUE
    sub.save(update_fields=["billing_status"])
    response = member_client.post("/api/member/attendance/clock-in/")
    assert response.status_code == 200
    assert response.data["clockIn"]


@pytest.mark.django_db
def test_cancelled_subscription_blocks_clock_in(member_client, seeded_db, admin_client):
    from accounts.models import MemberProfile

    member = MemberProfile.objects.get(user__email="john@spacez.in")
    sub = member.subscriptions.filter(status="ACTIVE").first()
    admin_client.post(f"/api/admin/subscriptions/{sub.id}/cancel/", {}, format="json")
    response = member_client.post("/api/member/attendance/clock-in/")
    assert response.status_code == 400
