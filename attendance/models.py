import uuid

from django.db import models

from accounts.models import MemberProfile


class AttendanceSource(models.TextChoices):
    MEMBER = "MEMBER", "Member"
    ADMIN = "ADMIN", "Admin"


class AttendanceStatus(models.TextChoices):
    PRESENT = "Present", "Present"
    ABSENT = "Absent", "Absent"
    PARTIAL = "Partial", "Partial"


class AttendanceRecord(models.Model):
    """No location, GPS, maps, or geofencing — time + member only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    clock_in = models.TimeField(blank=True, null=True)
    clock_out = models.TimeField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=AttendanceStatus.choices, default=AttendanceStatus.PRESENT)
    source = models.CharField(max_length=16, choices=AttendanceSource.choices, default=AttendanceSource.MEMBER)
    marked_by = models.CharField(max_length=160)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = [("member", "date")]

    def __str__(self):
        return f"{self.member} {self.date}"


class AttendanceEdit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="edits")
    at = models.DateTimeField(auto_now_add=True)
    admin = models.CharField(max_length=160)
    field = models.CharField(max_length=32)
    from_value = models.CharField(max_length=64)
    to_value = models.CharField(max_length=64)
    reason = models.CharField(max_length=255)

    class Meta:
        ordering = ["-at"]
