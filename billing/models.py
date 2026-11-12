import uuid

from django.db import models

from accounts.models import MemberProfile
from subscriptions.models import BillingStatus, Subscription


class InvoiceKind(models.TextChoices):
    SUBSCRIPTION = "SUBSCRIPTION", "Subscription"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"
    CREDIT = "CREDIT", "Credit"


class InvoiceStatus(models.TextChoices):
    PAID = "PAID", "Paid"
    DUE = "DUE", "Due"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    CREDIT = "CREDIT", "Credit"


class PaymentMethod(models.TextChoices):
    CASH = "Cash", "Cash"
    UPI = "UPI", "UPI"
    BANK = "Bank Transfer", "Bank Transfer"
    CARD = "Card", "Card"
    OTHER = "Other", "Other"


class PaymentStatus(models.TextChoices):
    PAID = "PAID", "Paid"
    PENDING = "PENDING", "Pending"
    FAILED = "FAILED", "Failed"


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=40, unique=True)
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="invoices")
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="invoices")
    period_start = models.DateField()
    period_end = models.DateField()
    total = models.IntegerField()
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DUE)
    issue_date = models.DateField()
    kind = models.CharField(max_length=20, choices=InvoiceKind.choices, default=InvoiceKind.SUBSCRIPTION)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]

    def __str__(self):
        return self.number


class InvoiceLineItem(models.Model):
    """Frozen price snapshot. Never re-read live catalog pricing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    unit_price = models.IntegerField()
    quantity = models.PositiveIntegerField(default=1)
    amount = models.IntegerField()
    pricing_item_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["code"]


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="payments")
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    amount = models.PositiveIntegerField()
    paid_on = models.DateField()
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    screenshot = models.ImageField(upload_to="payments/screenshots/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PAID)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def screenshot_name(self):
        if not self.screenshot:
            return None
        return self.screenshot.name.rsplit("/", 1)[-1]

    class Meta:
        ordering = ["-paid_on", "-created_at"]
