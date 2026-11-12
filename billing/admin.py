from django.contrib import admin

from billing.models import Invoice, InvoiceLineItem, Payment


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0
    readonly_fields = ["code", "name", "unit_price", "quantity", "amount", "pricing_item_id"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "member", "total", "status", "kind", "period_start", "period_end"]
    list_filter = ["status", "kind"]
    search_fields = ["number", "member__user__full_name"]
    inlines = [InvoiceLineItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["member", "amount", "method", "paid_on", "status", "invoice", "screenshot"]
    list_filter = ["method", "status"]
    search_fields = ["member__user__full_name", "reference"]
