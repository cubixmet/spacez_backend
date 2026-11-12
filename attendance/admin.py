from django.contrib import admin

from attendance.models import AttendanceEdit, AttendanceRecord


class AttendanceEditInline(admin.TabularInline):
    model = AttendanceEdit
    extra = 0
    readonly_fields = ["at", "admin", "field", "from_value", "to_value", "reason"]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["member", "date", "clock_in", "clock_out", "status", "source", "marked_by"]
    list_filter = ["status", "source", "date"]
    search_fields = ["member__user__full_name"]
    inlines = [AttendanceEditInline]
