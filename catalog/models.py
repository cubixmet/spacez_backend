import uuid

from django.db import models

from accounts.models import SpaceType


class PricingItem(models.Model):
    """Component-based pricing. New versions never rewrite historical invoices."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    space_type = models.CharField(max_length=20, choices=SpaceType.choices)
    price = models.PositiveIntegerField(help_text="Amount in INR rupees")
    effective_date = models.DateField()
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["space_type", "code", "-version"]
        unique_together = [("code", "space_type", "version")]

    def __str__(self):
        return f"{self.name} ({self.space_type}) v{self.version} ₹{self.price}"
