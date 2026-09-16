from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Business, Membership


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    """Superadmin ('platform operator') view of every business on Parchi.
    The in-app dashboard at /superadmin/ is the primary tool for this now;
    this stays as a raw-data fallback/escape hatch."""

    list_display = (
        "name",
        "owner_link",
        "phone",
        "email",
        "product_count",
        "staff_count",
        "bill_count",
        "total_revenue",
        "created_at",
    )
    search_fields = ("name", "owner__username", "email")
    readonly_fields = ("created_at",)

    def owner_link(self, obj):
        url = reverse("admin:auth_user_change", args=[obj.owner_id])
        return format_html('<a href="{}">{} (Hijack from here)</a>', url, obj.owner.username)

    owner_link.short_description = "Owner"

    def total_revenue(self, obj):
        return f"₹{obj.total_revenue}"

    total_revenue.short_description = "Revenue"


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "business", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "business")
    search_fields = ("user__username", "business__name")
