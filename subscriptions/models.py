import uuid

from django.db import models

from accounts.models import MemberProfile, SpaceType
from catalog.models import PricingItem


class BillingStatus(models.TextChoices):
    PAID = "PAID", "Paid"
    DUE = "DUE", "Due"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    CANCELLED = "CANCELLED", "Cancelled"


class SubscriptionAction(models.TextChoices):
    CREATED = "Created", "Created"
    RENEWED = "Renewed", "Renewed"
    UPGRADED = "Upgraded", "Upgraded"
    DOWNGRADED = "Downgraded", "Downgraded"
    SERVICE_ADDED = "Service Added", "Service added"
    SERVICE_REMOVED = "Service Removed", "Service removed"
    PRICE_CHANGED = "Price Changed", "Price changed"
    CANCELLED = "Cancelled", "Cancelled"


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="subscriptions")
    space_type = models.CharField(max_length=20, choices=SpaceType.choices)
    amount = models.IntegerField(help_text="Current recurring monthly amount in INR")
    start_date = models.DateField(help_text="Anniversary anchor date")
    period_start = models.DateField()
    period_end = models.DateField()
    billing_status = models.CharField(max_length=20, choices=BillingStatus.choices, default=BillingStatus.DUE)
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member} · {self.space_type} · ₹{self.amount}"


class SubscriptionItem(models.Model):
    """Current priced components on a subscription. Invoice snapshots live separately."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="items")
    pricing_item = models.ForeignKey(PricingItem, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    unit_price = models.IntegerField()
    quantity = models.PositiveIntegerField(default=1)
    amount = models.IntegerField()

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.name} ₹{self.amount}"


class SubscriptionEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="events")
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="subscription_events")
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=32, choices=SubscriptionAction.choices)
    admin = models.CharField(max_length=160)
    old_value = models.TextField()
    new_value = models.TextField()
    adjustment = models.IntegerField(default=0)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
