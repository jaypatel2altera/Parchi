import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.db import models

from .managers import BusinessScopedManager


class Business(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_businesses"
    )
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    # VPA (e.g. "name@bank") for the "Pay online" UPI link/QR shown on bills —
    # money goes straight to this UPI ID, no payment gateway or fees involved.
    upi_id = models.CharField(max_length=100, blank=True, verbose_name="UPI ID")
    # Encoded in this business's QR code as /o/<order_code>/ — a customer-facing
    # identifier, deliberately separate from `slug` so it's not guessable/enumerable.
    order_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "businesses"

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.count()

    @property
    def staff_count(self):
        return self.memberships.filter(role=Membership.STAFF).count()

    @property
    def bill_count(self):
        return self.bills.count()

    def upi_payment_link(self, amount, note=""):
        """Standard UPI 'intent' link (upi://pay?...) recognised by every UPI
        app (GPay, PhonePe, Paytm, ...) — money goes straight to this
        business's UPI ID with no payment gateway or transaction fees.
        Returns None if the business hasn't set a UPI ID."""
        if not self.upi_id:
            return None
        params = {"pa": self.upi_id, "pn": self.name, "am": str(amount), "cu": "INR"}
        if note:
            params["tn"] = note
        return f"upi://pay?{urlencode(params)}"

    @property
    def total_revenue(self):
        from django.db.models import Sum

        return self.bills.aggregate(total=Sum("total_amount"))["total"] or 0

    @property
    def pending_order_count(self):
        return self.orders.filter(status="PENDING").count()


class Membership(models.Model):
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    ROLE_CHOICES = [(ADMIN, "Admin"), (STAFF, "Staff")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership"
    )
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BusinessScopedManager()

    class Meta:
        indexes = [models.Index(fields=["business", "role"])]

    def __str__(self):
        return f"{self.user.username} ({self.role} @ {self.business.name})"

    @property
    def is_admin(self):
        return self.role == self.ADMIN
