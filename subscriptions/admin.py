from django.contrib import admin

from subscriptions.models import Subscription, SubscriptionEvent, SubscriptionItem


class SubscriptionItemInline(admin.TabularInline):
    model = SubscriptionItem
    extra = 0


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["member", "space_type", "amount", "billing_status", "status", "period_start", "period_end"]
    list_filter = ["space_type", "billing_status", "status"]
    search_fields = ["member__user__full_name", "member__user__email"]
    inlines = [SubscriptionItemInline]


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "member", "action", "admin", "adjustment"]
    list_filter = ["action"]
    search_fields = ["member__user__full_name"]
