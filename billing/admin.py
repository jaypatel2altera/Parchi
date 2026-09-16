from django.contrib import admin

from .models import Bill, BillLineItem, Order, OrderLineItem


class BillLineItemInline(admin.TabularInline):
    model = BillLineItem
    extra = 0
    readonly_fields = ("product", "product_name_snapshot", "quantity", "unit_price", "line_total")


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("public_id", "business", "customer_name", "total_amount", "created_at")
    list_filter = ("business",)
    search_fields = ("customer_name", "customer_phone")
    inlines = [BillLineItemInline]


class OrderLineItemInline(admin.TabularInline):
    model = OrderLineItem
    extra = 0
    readonly_fields = ("product", "product_name_snapshot", "quantity", "unit_price_snapshot")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("public_id", "business", "customer_name", "status", "estimated_total", "created_at")
    list_filter = ("business", "status")
    search_fields = ("customer_name", "customer_phone")
    inlines = [OrderLineItemInline]
