from rest_framework import serializers

from ops.models import SiteSettings
from spacez_backend.serialize import fmt_dt, iso_id


def settings_payload(obj: SiteSettings) -> dict:
    return {
        "spaceName": obj.space_name,
        "poweredBy": obj.powered_by,
        "address": obj.address,
        "supportEmail": obj.support_email,
        "supportPhone": obj.support_phone,
        "currency": obj.currency,
        "invoicePrefix": obj.invoice_prefix,
        "billingRule": obj.billing_rule,
        "gracePeriodDays": obj.grace_period_days,
        "allowAdminAttendanceEdit": obj.allow_admin_attendance_edit,
        "allowMemberClockOutEdit": obj.allow_member_clock_out_edit,
        "defaultAttendanceStatus": obj.default_attendance_status,
        "notifyNewMember": obj.notify_new_member,
        "notifyPayment": obj.notify_payment,
        "notifyBillingDue": obj.notify_billing_due,
        "notifyAttendance": obj.notify_attendance,
    }


class SettingsSerializer(serializers.Serializer):
    spaceName = serializers.CharField(required=False)
    poweredBy = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
    supportEmail = serializers.EmailField(required=False)
    supportPhone = serializers.CharField(required=False)
    currency = serializers.CharField(required=False)
    invoicePrefix = serializers.CharField(required=False)
    billingRule = serializers.CharField(required=False)
    gracePeriodDays = serializers.IntegerField(required=False)
    allowAdminAttendanceEdit = serializers.BooleanField(required=False)
    allowMemberClockOutEdit = serializers.BooleanField(required=False)
    defaultAttendanceStatus = serializers.CharField(required=False)
    notifyNewMember = serializers.BooleanField(required=False)
    notifyPayment = serializers.BooleanField(required=False)
    notifyBillingDue = serializers.BooleanField(required=False)
    notifyAttendance = serializers.BooleanField(required=False)


def notification_payload(n) -> dict:
    return {
        "id": iso_id(n.id),
        "title": n.title,
        "body": n.body,
        "createdAt": fmt_dt(n.created_at),
        "kind": n.kind,
        "read": n.read,
    }


def audit_payload(log) -> dict:
    return {
        "id": iso_id(log.id),
        "createdAt": fmt_dt(log.created_at),
        "admin": log.admin,
        "action": log.action,
        "target": log.target,
        "details": log.details,
    }


def email_payload(log) -> dict:
    return {
        "id": iso_id(log.id),
        "to": log.to,
        "subject": log.subject,
        "body": log.body,
        "sentAt": fmt_dt(log.sent_at),
        "kind": log.kind,
    }


class EnquirySerializer(serializers.Serializer):
    fullName = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.EmailField()
    spaceType = serializers.CharField()
    addOns = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    message = serializers.CharField(required=False, allow_blank=True, default="")
    estimatedTotal = serializers.IntegerField(required=False, default=0)


class ContactSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    message = serializers.CharField()
