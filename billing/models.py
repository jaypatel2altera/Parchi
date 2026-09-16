import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from accounts.managers import BusinessScopedManager
from accounts.models import Business
from inventory.models import Product


class Bill(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="bills")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    customer_name = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=15, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    pdf_file = models.FileField(upload_to="bills/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = BusinessScopedManager()

    class Meta:
        indexes = [models.Index(fields=["business", "created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Bill {self.public_id} ({self.business.name})"


class BillLineItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="line_items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    product_name_snapshot = models.CharField(max_length=150)
    unit_snapshot = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product_name_snapshot}"


class Order(models.Model):
    """A self-service order placed by a customer via the business's QR code.
    Does NOT touch stock on its own — only approving it (which converts it
    into a real Bill via billing.services.approve_order) decrements stock."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="orders")
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    estimated_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    bill = models.OneToOneField(Bill, on_delete=models.SET_NULL, null=True, blank=True, related_name="order")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = BusinessScopedManager()

    class Meta:
        indexes = [models.Index(fields=["business", "status"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.public_id} ({self.status})"


class OrderLineItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="line_items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    product_name_snapshot = models.CharField(max_length=150)
    unit_snapshot = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product_name_snapshot}"
