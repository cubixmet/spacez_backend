from rest_framework import serializers

from attendance.models import AttendanceRecord
from spacez_backend.serialize import fmt_date, fmt_dt, fmt_time, iso_id


def attendance_payload(record: AttendanceRecord) -> dict:
    return {
        "id": iso_id(record.id),
        "memberId": iso_id(record.member_id),
        "date": fmt_date(record.date),
        "clockIn": fmt_time(record.clock_in),
        "clockOut": fmt_time(record.clock_out),
        "status": record.status,
        "source": record.source,
        "markedBy": record.marked_by,
        "note": record.note,
        "edits": [
            {
                "at": fmt_dt(edit.at),
                "admin": edit.admin,
                "field": edit.field,
                "from": edit.from_value,
                "to": edit.to_value,
                "reason": edit.reason,
            }
            for edit in record.edits.all()
        ],
    }


def member_attendance_payload(record: AttendanceRecord) -> dict:
    return {
        "id": iso_id(record.id),
        "date": fmt_date(record.date),
        "clockIn": fmt_time(record.clock_in),
        "clockOut": fmt_time(record.clock_out),
        "source": record.source,
        "status": record.status,
        "markedBy": record.marked_by,
    }


class MarkAttendanceSerializer(serializers.Serializer):
    memberId = serializers.UUIDField()
    date = serializers.DateField()
    clockIn = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    clockOut = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(choices=["Present", "Absent", "Partial"])
    note = serializers.CharField(required=False, allow_blank=True, default="")


class EditAttendanceSerializer(serializers.Serializer):
    clockIn = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    clockOut = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(choices=["Present", "Absent", "Partial"])
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class BulkAttendanceSerializer(serializers.Serializer):
    date = serializers.DateField()
    entries = serializers.ListField(child=serializers.DictField(), min_length=1)
