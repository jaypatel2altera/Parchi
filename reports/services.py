from decimal import Decimal

from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce

from billing.models import BillLineItem
from inventory.models import Product

TWO_PLACES = Decimal("0.01")


def _money(value) -> Decimal:
    """SQLite has no fixed-point decimal type: any *computed* expression
    (a Sum, or arithmetic like qty * cost_price) comes back from the DB as a
    float and Django's sqlite backend only re-quantizes plain column reads,
    not expressions — so aggregates land as things like
    Decimal('1600.05000000000'). Round here in Python instead of trusting
    the DB to have kept it at 2 decimal places."""
    return Decimal(value).quantize(TWO_PLACES)


def top_selling_products(business, start, end, limit=10):
    rows = list(
        BillLineItem.objects.filter(bill__business=business, bill__created_at__range=(start, end))
        .values("product_id", "product_name_snapshot")
        .annotate(total_qty=Sum("quantity"), total_revenue=Sum("line_total"))
        .order_by("-total_revenue")[:limit]
    )
    for row in rows:
        row["total_revenue"] = _money(row["total_revenue"])
    return rows


def revenue_and_margin(business, start, end):
    result = BillLineItem.objects.filter(
        bill__business=business, bill__created_at__range=(start, end)
    ).aggregate(
        total_revenue=Coalesce(Sum("line_total"), 0, output_field=DecimalField()),
        total_margin=Coalesce(
            Sum((F("unit_price") - F("cost_price_snapshot")) * F("quantity")),
            0,
            output_field=DecimalField(),
        ),
        bill_count=Count("bill_id", distinct=True),
    )
    result["total_revenue"] = _money(result["total_revenue"])
    result["total_margin"] = _money(result["total_margin"])
    return result


def margin_by_product(business, start, end, limit=10):
    rows = list(
        BillLineItem.objects.filter(bill__business=business, bill__created_at__range=(start, end))
        .values("product_id", "product_name_snapshot")
        .annotate(
            qty_sold=Sum("quantity"),
            revenue=Sum("line_total"),
            margin=Sum((F("unit_price") - F("cost_price_snapshot")) * F("quantity")),
        )
        .order_by("-margin")[:limit]
    )
    for row in rows:
        row["revenue"] = _money(row["revenue"])
        row["margin"] = _money(row["margin"])
    return rows


def current_stock_value(business):
    result = Product.objects.for_business(business).filter(is_active=True).aggregate(
        stock_value_at_cost=Coalesce(
            Sum(F("stock_qty") * F("cost_price")), 0, output_field=DecimalField()
        ),
        stock_value_at_selling=Coalesce(
            Sum(F("stock_qty") * F("selling_price")), 0, output_field=DecimalField()
        ),
    )
    result["stock_value_at_cost"] = _money(result["stock_value_at_cost"])
    result["stock_value_at_selling"] = _money(result["stock_value_at_selling"])
    return result
