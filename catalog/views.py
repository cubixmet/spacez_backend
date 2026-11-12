from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from catalog.models import PricingItem
from catalog.serializers import PriceVersionSerializer, PricingWriteSerializer, pricing_payload
from catalog.services import add_pricing_item, create_price_version
from ops.services import log_audit, notify


@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
def pricing_collection(request):
    if request.method == "GET":
        qs = PricingItem.objects.all()
        space = request.query_params.get("spaceType")
        active = request.query_params.get("active")
        if space:
            qs = qs.filter(space_type=space)
        if active == "true":
            qs = qs.filter(active=True)
        return Response([pricing_payload(item) for item in qs])
    serializer = PricingWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    item = add_pricing_item(
        name=data["name"],
        code=data["code"],
        space_type=data["spaceType"],
        price=data["price"],
        effective_date=data["effectiveDate"],
        active=data.get("active", True),
    )
    log_audit("Pricing changed", item.name, f"Added {item.space_type} item at ₹{item.price}", admin=request.user.full_name)
    return Response(pricing_payload(item), status=201)


@api_view(["POST"])
@permission_classes([IsAdminRole])
def pricing_toggle(request, item_id):
    item = PricingItem.objects.get(pk=item_id)
    item.active = not item.active
    if item.active:
        PricingItem.objects.filter(code=item.code, space_type=item.space_type, active=True).exclude(pk=item.pk).update(
            active=False
        )
    item.save(update_fields=["active"])
    log_audit("Pricing changed", item.name, "Reactivated" if item.active else "Deactivated", admin=request.user.full_name)
    return Response(pricing_payload(item))


@api_view(["POST"])
@permission_classes([IsAdminRole])
def pricing_new_version(request, item_id):
    item = PricingItem.objects.get(pk=item_id)
    serializer = PriceVersionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    version = create_price_version(item, serializer.validated_data["price"], serializer.validated_data["effectiveDate"])
    log_audit(
        "Pricing changed",
        version.name,
        f"New version v{version.version}: ₹{item.price} → ₹{version.price} effective {version.effective_date}",
        admin=request.user.full_name,
    )
    notify("Pricing updated", f"{version.name} is now ₹{version.price}", "subscription")
    return Response(pricing_payload(version), status=201)
