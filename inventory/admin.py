from django.contrib import admin

from .models import Product, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "abbreviation", "business")
    list_filter = ("business",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "unit", "stock_qty", "cost_price", "selling_price", "is_active")
    list_filter = ("business", "is_active", "category")
    search_fields = ("name",)
