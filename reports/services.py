from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce

from billing.models import BillLineItem
from inventory.models import Product


def top_selling_products(business, start, end, limit=10):
    return (
        BillLineItem.objects.filter(bill__business=business, bill__created_at__range=(start, end))
        .values("product_id", "product_name_snapshot")
        .annotate(total_qty=Sum("quantity"), total_revenue=Sum("line_total"))
        .order_by("-total_revenue")[:limit]
    )


def revenue_and_margin(business, start, end):
    return BillLineItem.objects.filter(
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


def margin_by_product(business, start, end, limit=10):
    return (
        BillLineItem.objects.filter(bill__business=business, bill__created_at__range=(start, end))
        .values("product_id", "product_name_snapshot")
        .annotate(
            qty_sold=Sum("quantity"),
            revenue=Sum("line_total"),
            margin=Sum((F("unit_price") - F("cost_price_snapshot")) * F("quantity")),
        )
        .order_by("-margin")[:limit]
    )


def current_stock_value(business):
    return Product.objects.for_business(business).filter(is_active=True).aggregate(
        stock_value_at_cost=Coalesce(
            Sum(F("stock_qty") * F("cost_price")), 0, output_field=DecimalField()
        ),
        stock_value_at_selling=Coalesce(
            Sum(F("stock_qty") * F("selling_price")), 0, output_field=DecimalField()
        ),
    )
