from __future__ import annotations

from datetime import date, time

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import AccountStatus, MemberProfile
from attendance.models import AttendanceEdit, AttendanceRecord, AttendanceSource, AttendanceStatus
from ops.models import SiteSettings
from ops.services import actor_name, log_audit, notify
from subscriptions.models import SubscriptionStatus


def _now_time() -> time:
    return timezone.localtime().time().replace(second=0, microsecond=0)


def _today():
    return timezone.localdate()


def _hhmm(value: time | None) -> str:
    return value.strftime("%H:%M") if value else "—"


def _require_active_membership(member: MemberProfile):
    if member.account_status != AccountStatus.ACTIVE:
        raise ValidationError("Your account is not active. Contact Space Z to restore access.")
    has_active_sub = member.subscriptions.filter(status=SubscriptionStatus.ACTIVE).exists()
    if not has_active_sub:
        raise ValidationError("You do not have an active subscription. Contact Space Z to restore access.")


def clock_in(member: MemberProfile) -> AttendanceRecord:
    _require_active_membership(member)
    today = _today()
    existing = AttendanceRecord.objects.filter(member=member, date=today).first()
    if existing and existing.clock_in:
        raise ValidationError("You have already clocked in today.")
    now = _now_time()
    if existing:
        existing.clock_in = now
        existing.status = AttendanceStatus.PARTIAL
        existing.source = AttendanceSource.MEMBER
        existing.marked_by = member.user.full_name
        existing.save()
        return existing
    return AttendanceRecord.objects.create(
        member=member,
        date=today,
        clock_in=now,
        clock_out=None,
        status=AttendanceStatus.PARTIAL,
        source=AttendanceSource.MEMBER,
        marked_by=member.user.full_name,
    )


def clock_out(member: MemberProfile) -> AttendanceRecord:
    today = _today()
    record = AttendanceRecord.objects.filter(member=member, date=today).first()
    if not record or not record.clock_in:
        raise ValidationError("Clock in first.")
    if record.clock_out:
        raise ValidationError("You have already clocked out today.")
    record.clock_out = _now_time()
    record.status = AttendanceStatus.PRESENT
    record.save()
    return record


def mark_attendance(*, member: MemberProfile, on_date: date, clock_in_t, clock_out_t, status: str, note: str, admin) -> AttendanceRecord:
    existing = AttendanceRecord.objects.filter(member=member, date=on_date).first()
    name = actor_name(admin)
    if existing:
        existing.clock_in = clock_in_t
        existing.clock_out = clock_out_t
        existing.status = status
        existing.source = AttendanceSource.ADMIN
        existing.marked_by = name
        existing.note = note
        existing.save()
        log_audit("Attendance edited", member.user.full_name, f"{on_date} · {status}", admin=name)
        return existing
    record = AttendanceRecord.objects.create(
        member=member,
        date=on_date,
        clock_in=clock_in_t,
        clock_out=clock_out_t,
        status=status,
        source=AttendanceSource.ADMIN,
        marked_by=name,
        note=note,
    )
    log_audit("Attendance created", member.user.full_name, f"{on_date} · {status}", admin=name)
    return record


def bulk_mark(*, on_date: date, entries: list[dict], admin) -> int:
    settings = SiteSettings.load()
    default_in = time(9, 30) if settings.default_attendance_status == AttendanceStatus.PRESENT else None
    default_out = time(18, 0)
    count = 0
    for entry in entries:
        status = entry["status"]
        mark_attendance(
            member=entry["member"],
            on_date=on_date,
            clock_in_t=None if status == AttendanceStatus.ABSENT else default_in,
            clock_out_t=None if status == AttendanceStatus.ABSENT else default_out,
            status=status,
            note="Bulk marked",
            admin=admin,
        )
        count += 1
    log_audit("Attendance created", f"{count} members", f"Bulk marked for {on_date}", admin=actor_name(admin))
    return count


def edit_attendance(record: AttendanceRecord, *, clock_in_t, clock_out_t, status: str, reason: str, admin) -> AttendanceRecord:
    name = actor_name(admin)
    patches = {
        "clockIn": (_hhmm(record.clock_in), _hhmm(clock_in_t)),
        "clockOut": (_hhmm(record.clock_out), _hhmm(clock_out_t)),
        "status": (record.status, status),
    }
    for field, (frm, to) in patches.items():
        if frm != to:
            AttendanceEdit.objects.create(
                record=record,
                admin=name,
                field=field,
                from_value=frm,
                to_value=to,
                reason=reason or "No reason provided",
            )
    record.clock_in = clock_in_t
    record.clock_out = clock_out_t
    record.status = status
    record.marked_by = name
    record.save()
    log_audit("Attendance edited", record.member.user.full_name, f"{record.date} · {reason}", admin=name)
    notify(
        "Attendance modified",
        f"{record.member.user.full_name} · {record.date}",
        "attendance",
        enabled=SiteSettings.load().notify_attendance,
    )
    return record
