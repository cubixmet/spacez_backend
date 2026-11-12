from __future__ import annotations

from datetime import datetime, time


def iso_id(value) -> str:
    return str(value)


def fmt_date(value) -> str | None:
    return value.isoformat() if value else None


def fmt_dt(value) -> str | None:
    return value.isoformat() if value else None


def fmt_time(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


def media_url(request, field) -> str | None:
    if not field:
        return None
    url = field.url
    if request:
        return request.build_absolute_uri(url)
    return url


def line_item_payload(item) -> dict:
    pricing_id = ""
    if getattr(item, "pricing_item_id", None):
        pricing_id = str(item.pricing_item_id)
    elif getattr(item, "pricing_item", None):
        pricing_id = str(item.pricing_item_id)
    return {
        "code": item.code,
        "name": item.name,
        "unitPrice": item.unit_price,
        "quantity": item.quantity,
        "amount": item.amount,
        "pricingItemId": pricing_id or "—",
    }
