from __future__ import annotations

from datetime import date

from django.db.models import Max
from rest_framework.exceptions import ValidationError

from catalog.models import PricingItem


def active_pricing(space_type: str | None = None):
    qs = PricingItem.objects.filter(active=True)
    if space_type:
        qs = qs.filter(space_type=space_type)
    return qs


def line_payload(item: PricingItem, quantity: int = 1) -> dict:
    return {
        "pricing_item": item,
        "code": item.code,
        "name": item.name,
        "unit_price": item.price,
        "quantity": quantity,
        "amount": item.price * quantity,
    }


def next_price_version(code: str, space_type: str) -> int:
    current = PricingItem.objects.filter(code=code, space_type=space_type).aggregate(Max("version"))["version__max"]
    return (current or 0) + 1


def add_pricing_item(*, name: str, code: str, space_type: str, price: int, effective_date: date, active: bool = True):
    if active:
        PricingItem.objects.filter(code=code, space_type=space_type, active=True).update(active=False)
    return PricingItem.objects.create(
        name=name,
        code=code,
        space_type=space_type,
        price=price,
        effective_date=effective_date,
        active=active,
        version=next_price_version(code, space_type),
    )


def create_price_version(item: PricingItem, price: int, effective_date: date) -> PricingItem:
    PricingItem.objects.filter(code=item.code, space_type=item.space_type, active=True).update(active=False)
    return PricingItem.objects.create(
        code=item.code,
        name=item.name,
        space_type=item.space_type,
        price=price,
        effective_date=effective_date,
        active=True,
        version=next_price_version(item.code, item.space_type),
    )


def resolve_pricing_items(ids: list, *, space_type: str | None = None) -> list[PricingItem]:
    items = list(PricingItem.objects.filter(id__in=ids, active=True))
    if len(items) != len(set(str(i) for i in ids)):
        raise ValidationError("One or more pricing items were not found or are inactive.")
    if space_type and any(item.space_type != space_type for item in items):
        raise ValidationError("Pricing items must match the selected space type.")
    today = date.today()
    if any(item.effective_date > today for item in items):
        raise ValidationError("One or more pricing items are not effective yet.")
    order = {str(i): idx for idx, i in enumerate(ids)}
    items.sort(key=lambda item: order.get(str(item.id), 0))
    return items
