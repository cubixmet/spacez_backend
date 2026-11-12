#!/usr/bin/env python
"""Measure SQL query counts for key GET endpoints (admin + member)."""

import os
import sys
import time

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spacez_backend.settings")
django.setup()

from django.db import connection, reset_queries
from django.test.utils import override_settings
from rest_framework.test import APIClient


ENDPOINTS = [
    ("admin", "GET", "/api/admin/dashboard/"),
    ("admin", "GET", "/api/admin/members/"),
    ("admin", "GET", "/api/admin/subscriptions/"),
    ("admin", "GET", "/api/admin/invoices/"),
    ("admin", "GET", "/api/admin/payments/"),
    ("admin", "GET", "/api/admin/attendance/"),
    ("admin", "GET", "/api/admin/subscription-events/"),
    ("admin", "GET", "/api/admin/reports/"),
    ("admin", "GET", "/api/admin/pricing/"),
    ("member", "GET", "/api/member/invoices/"),
    ("member", "GET", "/api/member/payments/"),
    ("member", "GET", "/api/member/subscription/"),
    ("member", "GET", "/api/member/attendance/"),
    ("public", "GET", "/api/public/plans/"),
]


def login(role: str) -> APIClient:
    client = APIClient()
    if role == "admin":
        r = client.post(
            "/api/auth/admin/login/",
            {"email": "admin@spacez.in", "password": "spacez@admin"},
            format="json",
        )
    elif role == "member":
        r = client.post(
            "/api/auth/member/login/",
            {"email": "john@spacez.in", "password": "spacez123"},
            format="json",
        )
    else:
        return client
    assert r.status_code == 200, r.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


def main():
    with override_settings(DEBUG=True):
        clients = {
            "admin": login("admin"),
            "member": login("member"),
            "public": APIClient(),
        }
        print(f"{'endpoint':55} {'queries':>8} {'ms':>8}")
        for role, method, path in ENDPOINTS:
            client = clients[role]
            # warm
            getattr(client, method.lower())(path)
            reset_queries()
            start = time.perf_counter()
            response = getattr(client, method.lower())(path)
            elapsed = (time.perf_counter() - start) * 1000
            assert response.status_code == 200, f"{path} {response.status_code}"
            print(f"{path:55} {len(connection.queries):8d} {elapsed:8.1f}")


if __name__ == "__main__":
    main()
