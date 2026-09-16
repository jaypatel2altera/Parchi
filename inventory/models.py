from decimal import Decimal

from django.db import models

from accounts.managers import BusinessScopedManager
from accounts.models import Business


class Unit(models.Model):
    """Global defaults (business=NULL, seeded via data migration) plus
    per-business custom units."""

    name = models.CharField(max_length=30)
    abbreviation = models.CharField(max_length=10)
    business = models.ForeignKey(
        Business, null=True, blank=True, on_delete=models.CASCADE, related_name="custom_units"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "abbreviation"], name="uniq_unit_abbr_per_business"
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.abbreviation


class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=80, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="products")
    stock_qty = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal("0"))
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BusinessScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="uniq_product_name_per_business")
        ]
        indexes = [
            models.Index(fields=["business", "is_active"]),
            models.Index(fields=["business", "category"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock_qty <= Decimal("0")
