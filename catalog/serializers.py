from rest_framework import serializers

from catalog.models import PricingItem
from spacez_backend.serialize import fmt_date, iso_id


def pricing_payload(item: PricingItem) -> dict:
    return {
        "id": iso_id(item.id),
        "code": item.code,
        "name": item.name,
        "spaceType": item.space_type,
        "price": item.price,
        "effectiveDate": fmt_date(item.effective_date),
        "active": item.active,
        "version": item.version,
    }


class PricingWriteSerializer(serializers.Serializer):
    name = serializers.CharField()
    code = serializers.CharField()
    spaceType = serializers.CharField()
    price = serializers.IntegerField(min_value=0)
    effectiveDate = serializers.DateField()
    active = serializers.BooleanField(required=False, default=True)


class PriceVersionSerializer(serializers.Serializer):
    price = serializers.IntegerField(min_value=0)
    effectiveDate = serializers.DateField()
