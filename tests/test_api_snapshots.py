"""Baseline GET snapshots — response keys and status must stay stable after optimizations."""

import pytest


ADMIN_GETS = [
    "/api/admin/dashboard/",
    "/api/admin/settings/",
    "/api/admin/members/",
    "/api/admin/pricing/",
    "/api/admin/subscriptions/",
    "/api/admin/subscription-events/",
    "/api/admin/payments/",
    "/api/admin/invoices/",
    "/api/admin/attendance/",
    "/api/admin/notifications/",
    "/api/admin/audit-logs/?page=1&pageSize=8",
    "/api/admin/email-logs/",
    "/api/admin/reports/",
]

MEMBER_GETS = [
    "/api/member/me/",
    "/api/member/subscription/",
    "/api/member/payments/",
    "/api/member/invoices/",
    "/api/member/attendance/",
    "/api/member/notifications/",
]

PUBLIC_GETS = [
    "/api/public/plans/",
]


@pytest.mark.django_db
@pytest.mark.parametrize("path", ADMIN_GETS)
def test_admin_get_ok(admin_client, seeded_db, path):
    response = admin_client.get(path)
    assert response.status_code == 200, f"{path} -> {response.status_code} {response.content[:200]}"


@pytest.mark.django_db
@pytest.mark.parametrize("path", MEMBER_GETS)
def test_member_get_ok(member_client, seeded_db, path):
    response = member_client.get(path)
    assert response.status_code == 200, f"{path} -> {response.status_code} {response.content[:200]}"


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_GETS)
def test_public_get_ok(api, seeded_db, path):
    response = api.get(path)
    assert response.status_code == 200


@pytest.mark.django_db
def test_invoice_payload_shape(admin_client, seeded_db):
    response = admin_client.get("/api/admin/invoices/")
    assert response.status_code == 200
    assert len(response.data) > 0
    row = response.data[0]
    for key in (
        "id",
        "number",
        "memberId",
        "subscriptionId",
        "periodStart",
        "periodEnd",
        "items",
        "total",
        "status",
        "issueDate",
        "kind",
        "paidOn",
    ):
        assert key in row
    if row["items"]:
        item = row["items"][0]
        for key in ("code", "name", "unitPrice", "quantity", "amount"):
            assert key in item


@pytest.mark.django_db
def test_member_payload_shape(admin_client, seeded_db):
    response = admin_client.get("/api/admin/members/")
    row = response.data[0]
    for key in ("id", "fullName", "email", "phone", "spaceType", "accountStatus", "createdAt"):
        assert key in row


@pytest.mark.django_db
def test_subscription_payload_shape(admin_client, seeded_db):
    response = admin_client.get("/api/admin/subscriptions/")
    row = response.data[0]
    for key in ("id", "memberId", "spaceType", "amount", "periodStart", "periodEnd", "billingStatus", "status", "items"):
        assert key in row


@pytest.mark.django_db
def test_public_enquiry_validation(api):
    response = api.post("/api/public/enquiries/", {}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_public_enquiry_ok(api):
    response = api.post(
        "/api/public/enquiries/",
        {
            "fullName": "Test User",
            "phone": "+91 90000 11111",
            "email": "testuser@example.com",
            "spaceType": "Co-working",
            "addOns": ["ac"],
            "message": "hello",
            "estimatedTotal": 1499,
        },
        format="json",
    )
    assert response.status_code == 201
    assert "detail" in response.data


@pytest.mark.django_db
def test_unauthenticated_admin_blocked(api, seeded_db):
    response = api.get("/api/admin/members/")
    assert response.status_code in (401, 403)
