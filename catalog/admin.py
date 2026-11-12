from django.contrib import admin

from catalog.models import PricingItem


@admin.register(PricingItem)
class PricingItemAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "space_type", "price", "version", "active", "effective_date"]
    list_filter = ["space_type", "active", "code"]
    search_fields = ["name", "code"]
