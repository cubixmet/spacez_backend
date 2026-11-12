from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import MemberProfile
from accounts.permissions import IsAdminRole, IsMemberRole
from attendance.models import AttendanceRecord
from attendance.serializers import (
    BulkAttendanceSerializer,
    EditAttendanceSerializer,
    MarkAttendanceSerializer,
    attendance_payload,
    member_attendance_payload,
)
from attendance.services import bulk_mark, clock_in, clock_out, edit_attendance, mark_attendance
from spacez_backend.serialize import parse_hhmm


@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
def attendance_collection(request):
    if request.method == "GET":
        qs = AttendanceRecord.objects.select_related("member__user").prefetch_related("edits")
        on_date = request.query_params.get("date")
        member_id = request.query_params.get("memberId")
        status_filter = request.query_params.get("status")
        source = request.query_params.get("source")
        q = request.query_params.get("q")
        if on_date:
            qs = qs.filter(date=on_date)
        if member_id:
            qs = qs.filter(member_id=member_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if source:
            qs = qs.filter(source=source)
        if q:
            qs = qs.filter(member__user__full_name__icontains=q)
        return Response([attendance_payload(row) for row in qs])
    serializer = MarkAttendanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    member = MemberProfile.objects.get(pk=data["memberId"])
    record = mark_attendance(
        member=member,
        on_date=data["date"],
        clock_in_t=parse_hhmm(data.get("clockIn")),
        clock_out_t=parse_hhmm(data.get("clockOut")),
        status=data["status"],
        note=data.get("note", ""),
        admin=request.user,
    )
    return Response(attendance_payload(record), status=201)


@api_view(["PATCH"])
@permission_classes([IsAdminRole])
def attendance_edit(request, record_id):
    record = AttendanceRecord.objects.prefetch_related("edits").get(pk=record_id)
    serializer = EditAttendanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    record = edit_attendance(
        record,
        clock_in_t=parse_hhmm(data.get("clockIn")),
        clock_out_t=parse_hhmm(data.get("clockOut")),
        status=data["status"],
        reason=data.get("reason", ""),
        admin=request.user,
    )
    return Response(attendance_payload(record))


@api_view(["POST"])
@permission_classes([IsAdminRole])
def attendance_bulk(request):
    from uuid import UUID

    from rest_framework.exceptions import ValidationError

    serializer = BulkAttendanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    entries_data = serializer.validated_data["entries"]
    member_ids = []
    for entry in entries_data:
        raw = entry.get("memberId")
        try:
            member_ids.append(raw if isinstance(raw, UUID) else UUID(str(raw)))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid memberId: {raw}") from exc
    by_id = MemberProfile.objects.in_bulk(member_ids)
    missing = [str(mid) for mid in member_ids if mid not in by_id]
    if missing:
        raise ValidationError(f"Unknown member ids: {', '.join(missing)}")
    entries = [
        {"member": by_id[mid], "status": entry["status"]}
        for mid, entry in zip(member_ids, entries_data)
    ]
    count = bulk_mark(on_date=serializer.validated_data["date"], entries=entries, admin=request.user)
    return Response({"saved": count})


@api_view(["GET"])
@permission_classes([IsMemberRole])
def member_attendance(request):
    profile = request.user.member_profile
    qs = AttendanceRecord.objects.filter(member=profile)
    date_from = request.query_params.get("from")
    date_to = request.query_params.get("to")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return Response([member_attendance_payload(row) for row in qs])


@api_view(["POST"])
@permission_classes([IsMemberRole])
def member_clock_in(request):
    record = clock_in(request.user.member_profile)
    return Response(member_attendance_payload(record))


@api_view(["POST"])
@permission_classes([IsMemberRole])
def member_clock_out(request):
    record = clock_out(request.user.member_profile)
    return Response(member_attendance_payload(record))
