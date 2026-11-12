import pytest


@pytest.mark.django_db
def test_pricing_add_deactivates_sibling(admin_client, seeded_db):
    from catalog.models import PricingItem

    active_before = PricingItem.objects.filter(code="locker", space_type="Co-working", active=True).count()
    response = admin_client.post(
        "/api/admin/pricing/",
        {
            "name": "Personal Locker",
            "code": "locker",
            "spaceType": "Co-working",
            "price": 199,
            "effectiveDate": "2026-09-01",
            "active": True,
        },
        format="json",
    )
    assert response.status_code == 201
    active_after = PricingItem.objects.filter(code="locker", space_type="Co-working", active=True)
    assert active_after.count() == 1
    assert active_after.first().price == 199
    assert active_before >= 0


@pytest.mark.django_db
def test_pricing_toggle_unique_active(admin_client, seeded_db):
    from catalog.models import PricingItem

    versions = list(PricingItem.objects.filter(code="space", space_type="Co-working").order_by("version"))
    assert len(versions) >= 1
    inactive = next((v for v in versions if not v.active), None)
    if inactive is None:
        pytest.skip("Need an inactive version to toggle")
    response = admin_client.post(f"/api/admin/pricing/{inactive.id}/toggle/", {}, format="json")
    assert response.status_code == 200
    assert PricingItem.objects.filter(code="space", space_type="Co-working", active=True).count() == 1


@pytest.mark.django_db
def test_cancel_subscription(admin_client, seeded_db):
    from subscriptions.models import Subscription, SubscriptionStatus

    sub = Subscription.objects.filter(status=SubscriptionStatus.ACTIVE).first()
    response = admin_client.post(f"/api/admin/subscriptions/{sub.id}/cancel/", {}, format="json")
    assert response.status_code == 200
    assert response.data["status"] == "CANCELLED"
    renew = admin_client.post(f"/api/admin/subscriptions/{sub.id}/renew/", {}, format="json")
    assert renew.status_code == 400


@pytest.mark.django_db
def test_resolve_pricing_rejects_wrong_space(admin_client, seeded_db):
    from catalog.models import PricingItem
    from accounts.models import MemberProfile

    member = MemberProfile.objects.get(user__email="john@spacez.in")
    # Cancel existing so create is allowed if we used create endpoint; use preview/change instead
    student_item = PricingItem.objects.filter(space_type="Student", active=True).first()
    sub = member.subscriptions.filter(status="ACTIVE").first()
    response = admin_client.post(
        f"/api/admin/subscriptions/{sub.id}/preview/",
        {"pricingItemIds": [str(student_item.id)], "changeDate": str(sub.period_start)},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_bulk_attendance(admin_client, seeded_db):
    from accounts.models import MemberProfile

    ids = list(MemberProfile.objects.values_list("id", flat=True)[:3])
    response = admin_client.post(
        "/api/admin/attendance/bulk/",
        {
            "date": "2026-09-15",
            "entries": [{"memberId": str(i), "status": "Present"} for i in ids],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["saved"] == 3
