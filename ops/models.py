import uuid

from django.db import models

from attendance.models import AttendanceStatus


class NotificationKind(models.TextChoices):
    MEMBER = "member", "Member"
    PAYMENT = "payment", "Payment"
    SUBSCRIPTION = "subscription", "Subscription"
    ATTENDANCE = "attendance", "Attendance"
    BILLING = "billing", "Billing"


class EmailKind(models.TextChoices):
    MAGIC_LINK = "MAGIC_LINK", "Magic link"
    INVOICE = "INVOICE", "Invoice"
    GENERAL = "GENERAL", "General"


class SiteSettings(models.Model):
    space_name = models.CharField(max_length=80, default="Space Z")
    powered_by = models.CharField(max_length=80, default="Powered by Cubixmet")
    address = models.CharField(max_length=255, default="Space Z Workspace, Cubixmet Technologies")
    support_email = models.EmailField(default="hello@cubixmet.com")
    support_phone = models.CharField(max_length=32, default="+91 98470 11223")
    currency = models.CharField(max_length=32, default="INR (₹)")
    invoice_prefix = models.CharField(max_length=24, default="SZ-")
    billing_rule = models.CharField(max_length=120, default="Anniversary based (calendar month)")
    grace_period_days = models.PositiveIntegerField(default=5)
    allow_admin_attendance_edit = models.BooleanField(default=True)
    allow_member_clock_out_edit = models.BooleanField(default=False)
    default_attendance_status = models.CharField(
        max_length=16,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )
    notify_new_member = models.BooleanField(default=True)
    notify_payment = models.BooleanField(default=True)
    notify_billing_due = models.BooleanField(default=True)
    notify_attendance = models.BooleanField(default=False)
    invoice_sequence = models.PositiveIntegerField(default=100)

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return self.space_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=160)
    body = models.TextField()
    kind = models.CharField(max_length=20, choices=NotificationKind.choices)
    read = models.BooleanField(default=False)
    member = models.ForeignKey(
        "accounts.MemberProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Null = admin-wide notification",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    admin = models.CharField(max_length=160)
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=160)
    details = models.TextField()

    class Meta:
        ordering = ["-created_at"]


class EmailLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    to = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=20, choices=EmailKind.choices, default=EmailKind.GENERAL)

    class Meta:
        ordering = ["-sent_at"]


class Enquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=32)
    email = models.EmailField()
    space_type = models.CharField(max_length=20)
    add_ons = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True)
    estimated_total = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Enquiries"


class ContactMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
