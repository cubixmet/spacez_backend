from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AccountStatus, MagicLink, MemberProfile, User, UserRole
from billing.services import generate_invoice, record_payment
from ops.models import EmailKind, SiteSettings
from ops.services import actor_name, log_audit, log_email, magic_link_url, notify
from spacez_backend.periods import parse_iso_date
from subscriptions.services import create_subscription

MAGIC_LINK_TTL = timedelta(days=7)


def issue_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["email"] = user.email
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def authenticate(email: str, password: str, *, expected_roles: set[str]) -> User:
    try:
        user = User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist as exc:
        raise ValidationError("Invalid email or password.") from exc
    if not user.check_password(password) or not user.is_active:
        raise ValidationError("Invalid email or password.")
    if user.role not in expected_roles:
        raise ValidationError("This account cannot sign in here.")
    return user


def assert_member_can_sign_in(user: User) -> MemberProfile:
    try:
        profile = user.member_profile
    except MemberProfile.DoesNotExist as exc:
        raise ValidationError("Member profile not found.") from exc
    if profile.account_status != AccountStatus.ACTIVE:
        raise ValidationError("Your account is not active. Contact Space Z to restore access.")
    return profile


def create_magic_link(member: MemberProfile, admin=None, *, subject: str | None = None, body: str | None = None) -> MagicLink:
    token = secrets.token_urlsafe(24)
    link = MagicLink.objects.create(member=member, token=token)
    url = magic_link_url(token)
    email_body = body or (
        f"Hi {member.user.full_name}, sign in to the Space Z member app with this one-time link: {url}"
    )
    log_email(
        to=member.user.email,
        subject=subject or "Your Space Z magic link",
        body=email_body,
        kind=EmailKind.MAGIC_LINK,
    )
    log_audit("Magic link sent", member.user.email, "Magic link emailed", admin=actor_name(admin))
    return link


def consume_magic_link(token: str) -> User:
    try:
        link = MagicLink.objects.select_related("member__user").get(token=token)
    except MagicLink.DoesNotExist as exc:
        raise ValidationError("This magic link is invalid or has expired.") from exc
    if link.used_at:
        raise ValidationError("This magic link has already been used.")
    if link.created_at < timezone.now() - MAGIC_LINK_TTL:
        raise ValidationError("This magic link is invalid or has expired.")
    if link.member.account_status != AccountStatus.ACTIVE:
        raise ValidationError("Your account is not active. Contact Space Z to restore access.")
    link.used_at = timezone.now()
    link.save(update_fields=["used_at"])
    return link.member.user


def _send_welcome_magic_link(member_id, admin_id):
    member = MemberProfile.objects.select_related("user").get(pk=member_id)
    admin = User.objects.filter(pk=admin_id).first() if admin_id else None
    try:
        create_magic_link(member, admin=admin)
    except Exception:
        log_audit(
            "Magic link failed",
            member.user.email,
            "Member was created but welcome email could not be sent",
            admin=actor_name(admin),
        )


@transaction.atomic
def create_member(*, data: dict, subscription_data: dict, payment_data: dict | None, admin) -> dict:
    email = data["email"].strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError("A member with this email already exists.")
    user = User.objects.create_user(
        email=email,
        password=settings.DEFAULT_MEMBER_PASSWORD,
        full_name=data["fullName"],
        phone=data["phone"],
        role=UserRole.MEMBER,
    )
    member = MemberProfile.objects.create(
        user=user,
        space_type=subscription_data["spaceType"],
        proof_type=data.get("proofType", ""),
        proof_number=data.get("proofNumber", ""),
        notes=data.get("notes", ""),
        onboarding_completed=False,
    )
    if data.get("photo"):
        member.photo = data["photo"]
        member.save(update_fields=["photo"])
    if data.get("proofDocument"):
        member.proof_document = data["proofDocument"]
        member.save(update_fields=["proof_document"])

    subscription = create_subscription(
        member=member,
        start_date=parse_iso_date(subscription_data["startDate"]),
        space_type=subscription_data["spaceType"],
        pricing_item_ids=subscription_data["pricingItemIds"],
        admin=admin,
    )
    MemberProfile.objects.filter(pk=member.pk).update(created_at=parse_iso_date(subscription_data["startDate"]))
    member.refresh_from_db()
    invoice = generate_invoice(subscription, admin=actor_name(admin))
    if payment_data and payment_data.get("amount"):
        record_payment(
            member=member,
            subscription=subscription,
            invoice=invoice,
            amount=int(payment_data["amount"]),
            method=payment_data.get("method", "UPI"),
            reference=payment_data.get("reference", ""),
            notes=payment_data.get("notes", "Collected at registration"),
            paid_on=payment_data.get("paidOn") or timezone.localdate(),
            admin=admin,
        )
        invoice.refresh_from_db()
        subscription.refresh_from_db()

    log_audit(
        "Member created",
        member.user.full_name,
        f"{member.space_type} · {member.user.email}",
        admin=actor_name(admin),
    )
    notify(
        "New member created",
        f"{member.user.full_name} joined on the {member.space_type} plan.",
        "member",
        enabled=SiteSettings.load().notify_new_member,
    )
    # Send email after commit so SMTP failures cannot roll back the member record.
    member_id = member.pk
    admin_id = getattr(admin, "pk", None)
    transaction.on_commit(lambda: _send_welcome_magic_link(member_id, admin_id))
    return {"member": member, "subscription": subscription, "invoice": invoice}


def change_member_status(member: MemberProfile, status: str, reason: str, admin) -> MemberProfile:
    previous = member.account_status
    member.account_status = status
    member.save(update_fields=["account_status"])
    log_audit(
        "Status changed",
        member.user.full_name,
        f"{previous} → {status}{f' · {reason}' if reason else ''}",
        admin=actor_name(admin),
    )
    notify("Account status changed", f"{member.user.full_name} is now {status}.", "member")
    return member
