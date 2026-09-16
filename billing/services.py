from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from inventory.models import Product

from .models import Bill, BillLineItem, Order, OrderLineItem


class CartError(ValidationError):
    pass


def parse_cart(business, post_data):
    """Reads posted qty_<product_id> fields, scoped to this business, and
    returns a list of {"product": Product, "quantity": Decimal} for qty > 0."""
    product_ids = [
        key.split("qty_", 1)[1] for key in post_data if key.startswith("qty_") and post_data[key]
    ]
    products = {
        str(p.id): p for p in Product.objects.for_business(business).filter(id__in=product_ids)
    }
    items = []
    for pid in product_ids:
        product = products.get(pid)
        if product is None:
            continue
        raw_qty = post_data.get(f"qty_{pid}", "").strip()
        if not raw_qty:
            continue
        try:
            qty = Decimal(raw_qty)
        except InvalidOperation:
            raise CartError(f"Invalid quantity for {product.name}.")
        if qty <= 0:
            continue
        items.append({"product": product, "quantity": qty})
    return items


@transaction.atomic
def create_bill(business, user, customer_name, customer_phone, cart_items):
    if not cart_items:
        raise CartError("Add at least one product to the bill.")

    bill = Bill.objects.create(
        business=business, created_by=user, customer_name=customer_name, customer_phone=customer_phone
    )
    total = Decimal("0")

    product_ids = sorted({item["product"].id for item in cart_items})
    locked_products = {
        p.id: p
        for p in Product.objects.for_business(business).select_for_update().filter(id__in=product_ids)
    }

    for item in cart_items:
        product = locked_products[item["product"].id]
        qty = item["quantity"]

        if product.stock_qty < qty:
            raise CartError(f"Only {product.stock_qty} {product.unit} of {product.name} left.")

        updated = Product.objects.filter(id=product.id, stock_qty__gte=qty).update(
            stock_qty=F("stock_qty") - qty
        )
        if updated == 0:
            raise CartError(f"{product.name} stock just changed, please retry.")

        line_total = (product.selling_price * qty).quantize(Decimal("0.01"))
        BillLineItem.objects.create(
            bill=bill,
            product=product,
            product_name_snapshot=product.name,
            unit_snapshot=str(product.unit),
            quantity=qty,
            unit_price=product.selling_price,
            cost_price_snapshot=product.cost_price,
            line_total=line_total,
        )
        total += line_total

    bill.total_amount = total
    bill.save(update_fields=["total_amount"])
    return bill


@transaction.atomic
def create_order(business, customer_name, customer_phone, cart_items):
    """Customer self-service order via QR code. Only validates stock for a
    good UX — does NOT decrement it. Stock is only touched at approval time
    (see approve_order), since a pending order may sit for a while and stock
    can move in the meantime."""
    if not cart_items:
        raise CartError("Add at least one product to your order.")

    for item in cart_items:
        if item["product"].stock_qty < item["quantity"]:
            raise CartError(
                f"Only {item['product'].stock_qty} {item['product'].unit} of "
                f"{item['product'].name} available right now."
            )

    order = Order.objects.create(
        business=business, customer_name=customer_name, customer_phone=customer_phone
    )
    total = Decimal("0")
    for item in cart_items:
        product = item["product"]
        qty = item["quantity"]
        line_total = (product.selling_price * qty).quantize(Decimal("0.01"))
        OrderLineItem.objects.create(
            order=order,
            product=product,
            product_name_snapshot=product.name,
            unit_snapshot=str(product.unit),
            quantity=qty,
            unit_price_snapshot=product.selling_price,
        )
        total += line_total

    order.estimated_total = total
    order.save(update_fields=["estimated_total"])
    return order


@transaction.atomic
def approve_order(order, user):
    if order.status != Order.PENDING:
        raise CartError("This order has already been decided.")

    cart_items = [
        {"product": item.product, "quantity": item.quantity} for item in order.line_items.all()
    ]
    bill = create_bill(
        business=order.business,
        user=user,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        cart_items=cart_items,
    )
    order.status = Order.APPROVED
    order.bill = bill
    order.decided_by = user
    order.decided_at = timezone.now()
    order.save(update_fields=["status", "bill", "decided_by", "decided_at"])
    return bill


def reject_order(order, user):
    if order.status != Order.PENDING:
        raise CartError("This order has already been decided.")

    order.status = Order.REJECTED
    order.decided_by = user
    order.decided_at = timezone.now()
    order.save(update_fields=["status", "decided_by", "decided_at"])
    return order
