import pytest
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("migrate", verbosity=0, interactive=False)


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def seeded_db(db):
    """Reset operational data and recreate admin + sample members."""
    call_command("seed_dev", "--reset", verbosity=0)
    return True


@pytest.fixture
def admin_user(seeded_db):
    from accounts.models import User

    return User.objects.get(email="admin@spacez.in")


@pytest.fixture
def admin_client(seeded_db):
    client = APIClient()
    response = client.post(
        "/api/auth/admin/login/",
        {"email": "admin@spacez.in", "password": "spacez@admin", "remember": True},
        format="json",
    )
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


@pytest.fixture
def member_client(seeded_db):
    client = APIClient()
    response = client.post(
        "/api/auth/member/login/",
        {"email": "john@spacez.in", "password": "spacez123", "remember": True},
        format="json",
    )
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client
