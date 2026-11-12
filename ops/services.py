from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from ops.models import AuditLog, EmailKind, EmailLog, Notification, NotificationKind, SiteSettings


def actor_name(user) -> str:
    if user is None:
        return "System"
    return getattr(user, "full_name", None) or str(user)


def log_audit(action: str, target: str, details: str, admin: str = "System"):
    return AuditLog.objects.create(admin=admin, action=action, target=target, details=details)


def notify(title: str, body: str, kind: str, member=None, enabled: bool = True):
    if not enabled:
        return None
    return Notification.objects.create(title=title, body=body, kind=kind, member=member)


def log_email(*, to: str, subject: str, body: str, kind: str = EmailKind.GENERAL):
    entry = EmailLog.objects.create(to=to, subject=subject, body=body, kind=kind)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        fail_silently=False,
    )
    return entry


def next_invoice_number() -> str:
    site = SiteSettings.load()
    site.invoice_sequence += 1
    site.save(update_fields=["invoice_sequence"])
    prefix = site.invoice_prefix
    if not prefix.endswith("-"):
        prefix = f"{prefix}-"
    return f"{prefix}{site.invoice_sequence:05d}"


def magic_link_url(token: str) -> str:
    return f"{settings.FRONTEND_URL}/app/onboarding?token={token}"


def now():
    return timezone.now()
