from django.contrib import admin

from ops.models import AuditLog, ContactMessage, EmailLog, Enquiry, Notification, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "member", "read", "created_at"]
    list_filter = ["kind", "read"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "admin", "action", "target"]
    search_fields = ["action", "target", "details"]


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ["sent_at", "to", "subject", "kind"]
    list_filter = ["kind"]


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "full_name", "email", "space_type", "estimated_total"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["created_at", "name", "email", "phone"]
