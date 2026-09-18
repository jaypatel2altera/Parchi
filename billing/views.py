import re
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from accounts.models import Business
from accounts.mixins import BusinessRequiredMixin
from inventory.models import Product

from .models import Bill, Order
from .pdf import render_bill_pdf
from .services import CartError, approve_order, create_bill, create_order, parse_cart, reject_order

PHONE_RE = re.compile(r"^\d{10}$")


def is_valid_phone(phone):
    return bool(PHONE_RE.fullmatch(phone))


def whatsapp_number(phone):
    """Customer phone numbers are stored as a plain 10-digit number; wa.me
    links need the country code in front. Assume India (91) — numbers from
    older data that already carry a country code are left as-is."""
    digits = re.sub(r"\D", "", phone)
    return f"91{digits}" if len(digits) == 10 else digits


def upi_reference(short_code, customer_name):
    """Builds the UPI 'tr' value: the order/bill's short code plus the
    first few letters of the customer's name, so it's recognisable but
    still short and free of spaces/punctuation some UPI apps reject."""
    name_part = re.sub(r"[^A-Za-z0-9]", "", customer_name or "")[:8].upper()
    return f"{short_code}{name_part}" if name_part else short_code


class BillCreateView(BusinessRequiredMixin, View):
    template_name = "billing/bill_create.html"

    def get(self, request):
        products = Product.objects.for_business(request.business).filter(is_active=True).select_related(
            "unit"
        )
        return render(request, self.template_name, {"products": products})

    def post(self, request):
        products = Product.objects.for_business(request.business).filter(is_active=True).select_related(
            "unit"
        )
        payment_method = request.POST.get("payment_method", Bill.CASH)
        if payment_method not in dict(Bill.PAYMENT_METHOD_CHOICES):
            payment_method = Bill.CASH
        customer_phone = request.POST.get("customer_phone", "").strip()
        if customer_phone and not is_valid_phone(customer_phone):
            return render(
                request,
                self.template_name,
                {"products": products, "error": "WhatsApp number must be exactly 10 digits."},
            )
        try:
            cart_items = parse_cart(request.business, request.POST)
            bill = create_bill(
                business=request.business,
                user=request.user,
                customer_name=request.POST.get("customer_name", "").strip(),
                customer_phone=customer_phone,
                cart_items=cart_items,
                payment_method=payment_method,
            )
        except CartError as exc:
            return render(
                request,
                self.template_name,
                {"products": products, "error": exc.message if hasattr(exc, "message") else str(exc)},
            )

        pdf_bytes = render_bill_pdf(bill)
        bill.pdf_file.save(f"{bill.public_id}.pdf", ContentFile(pdf_bytes), save=True)

        return redirect("billing:bill-whatsapp", pk=bill.pk)


class BillWhatsAppView(BusinessRequiredMixin, View):
    """Renders the 'tap to send on WhatsApp' confirmation page for a bill —
    used both right after creating a bill, and when revisiting an older bill
    from Order history. No server-side WhatsApp API involved."""

    def get(self, request, pk):
        bill = get_object_or_404(Bill.objects.for_business(request.business), pk=pk)
        public_url = request.build_absolute_uri(
            reverse("billing:public-bill", kwargs={"public_id": bill.public_id})
        )
        message = f"Your bill from {bill.business.name}: {public_url}"
        phone = bill.customer_phone.strip()
        whatsapp_url = (
            f"https://wa.me/{whatsapp_number(phone)}?text={quote(message)}"
            if phone
            else f"https://wa.me/?text={quote(message)}"
        )
        return render(
            request,
            "billing/bill_success.html",
            {"bill": bill, "whatsapp_url": whatsapp_url, "public_url": public_url},
        )


class BillRegeneratePDFView(BusinessRequiredMixin, View):
    """Re-renders a bill's PDF from its stored line items — useful if the
    original file went missing, or bill design/business contact info changed
    since it was first created."""

    def post(self, request, pk):
        bill = get_object_or_404(Bill.objects.for_business(request.business), pk=pk)
        pdf_bytes = render_bill_pdf(bill)
        bill.pdf_file.save(f"{bill.public_id}.pdf", ContentFile(pdf_bytes), save=True)
        messages.success(request, "Bill PDF regenerated.")
        return redirect("billing:bill-whatsapp", pk=bill.pk)


class PublicBillView(View):
    """Intentionally unscoped by business/login — this is the public link a
    customer opens from WhatsApp. Safe because public_id is a non-enumerable
    UUID. Do NOT add business/auth filtering here; add a *new* view instead
    if an authenticated variant is ever needed."""

    def get(self, request, public_id):
        bill = get_object_or_404(Bill, public_id=public_id)
        pay_link = bill.business.upi_payment_link(
            bill.total_amount, reference=upi_reference(bill.short_code, bill.customer_name)
        )
        return render(request, "billing/public_bill.html", {"bill": bill, "pay_link": pay_link})


class PublicBillPDFView(View):
    """Same intentional public-by-UUID exception as PublicBillView."""

    def get(self, request, public_id):
        bill = get_object_or_404(Bill, public_id=public_id)
        if not bill.pdf_file:
            raise Http404("PDF not available.")
        return FileResponse(bill.pdf_file.open("rb"), filename=f"bill-{bill.public_id}.pdf")


class PublicBillUPIQRView(View):
    """QR code of this bill's UPI pay link, embedded on the public bill page
    for anyone viewing it on a desktop/second device. Same intentional
    public-by-UUID exception as PublicBillView. Money paid this way goes
    straight to the business's UPI ID — no gateway, no fees."""

    def get(self, request, public_id):
        bill = get_object_or_404(Bill, public_id=public_id)
        pay_link = bill.business.upi_payment_link(
            bill.total_amount, reference=upi_reference(bill.short_code, bill.customer_name)
        )
        if not pay_link:
            raise Http404("This business hasn't set up UPI payments.")
        img = qrcode.make(pay_link, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
        response = HttpResponse(content_type="image/svg+xml")
        img.save(response)
        return response


class PublicOrderView(View):
    """The QR-code landing page: a customer picks products and submits their
    name + phone. Intentionally unscoped by login — resolved only by the
    business's non-enumerable order_code. Branded as the business, not Parchi
    (see templates/public_base.html)."""

    template_name = "billing/public_order.html"

    def get(self, request, order_code):
        business = get_object_or_404(Business, order_code=order_code)
        products = Product.objects.for_business(business).filter(is_active=True).select_related("unit")
        return render(request, self.template_name, {"business": business, "products": products})

    def post(self, request, order_code):
        business = get_object_or_404(Business, order_code=order_code)
        products = Product.objects.for_business(business).filter(is_active=True).select_related("unit")
        customer_name = request.POST.get("customer_name", "").strip()
        customer_phone = request.POST.get("customer_phone", "").strip()
        error = None

        if not customer_name or not customer_phone:
            error = "Please enter your name and mobile number."
        elif not is_valid_phone(customer_phone):
            error = "Mobile number must be exactly 10 digits."
        else:
            try:
                cart_items = parse_cart(business, request.POST)
                order = create_order(
                    business=business,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    cart_items=cart_items,
                )
            except CartError as exc:
                error = exc.message if hasattr(exc, "message") else str(exc)
            else:
                return redirect("billing:order-confirmation", public_id=order.public_id)

        return render(
            request,
            self.template_name,
            {"business": business, "products": products, "error": error},
        )


class OrderConfirmationView(View):
    """Public, unscoped by design — same reasoning as PublicBillView."""

    def get(self, request, public_id):
        order = get_object_or_404(Order, public_id=public_id)
        pay_link = order.business.upi_payment_link(
            order.estimated_total, reference=upi_reference(order.short_code, order.customer_name)
        )
        return render(request, "billing/order_confirmation.html", {"order": order, "pay_link": pay_link})


class OrderUPIQRView(View):
    """QR code of a pending order's estimated UPI pay link — lets an eager
    customer pay up front, before the shop confirms the order. Same
    intentional public-by-UUID exception as OrderConfirmationView."""

    def get(self, request, public_id):
        order = get_object_or_404(Order, public_id=public_id)
        pay_link = order.business.upi_payment_link(
            order.estimated_total, reference=upi_reference(order.short_code, order.customer_name)
        )
        if not pay_link:
            raise Http404("This business hasn't set up UPI payments.")
        img = qrcode.make(pay_link, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
        response = HttpResponse(content_type="image/svg+xml")
        img.save(response)
        return response


class OrderListView(BusinessRequiredMixin, View):
    """Visible to Admin and Staff alike — either can approve/reject orders."""

    template_name = "billing/order_list.html"

    def get(self, request):
        orders = Order.objects.for_business(request.business).prefetch_related("line_items")
        pending = orders.filter(status=Order.PENDING)
        recent_decided = orders.exclude(status=Order.PENDING)[:10]
        return render(
            request, self.template_name, {"pending_orders": pending, "recent_orders": recent_decided}
        )


WALKIN = "WALKIN"


class OrderHistoryView(BusinessRequiredMixin, View):
    """Full, paginated activity history for the business: every self-service
    QR order (any status) AND every walk-in bill a staff member typed up
    directly via 'New Bill' — merged into one timeline, newest first. Bills
    created by approving an order aren't listed twice; they appear as that
    order's 'Approved' entry (with a link straight to the bill), exactly like
    before. The main Orders page (OrderListView) stays focused on what needs
    a decision right now; this is the 'look back at everything' view."""

    template_name = "billing/order_history.html"
    paginate_by = 20
    STATUS_LABELS = {
        Order.PENDING: "Pending",
        Order.APPROVED: "Approved",
        Order.REJECTED: "Rejected",
        WALKIN: "Walk-in sale",
    }

    def get(self, request):
        status = request.GET.get("status", "").upper()

        orders = Order.objects.for_business(request.business).prefetch_related("line_items").select_related(
            "bill"
        )
        # Walk-in sales: bills with no linked order at all (i.e. typed up
        # directly via New Bill, not born from a customer's QR order).
        walkin_bills = Bill.objects.for_business(request.business).filter(order__isnull=True).prefetch_related(
            "line_items"
        )

        entries = [
            {
                "created_at": order.created_at,
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "status": order.status,
                "status_label": self.STATUS_LABELS[order.status],
                "total": order.estimated_total,
                "items": order.line_items.all(),
                "bill_id": order.bill_id,
                "payment_method_label": order.bill.get_payment_method_display() if order.bill_id else None,
            }
            for order in orders
        ] + [
            {
                "created_at": bill.created_at,
                "customer_name": bill.customer_name,
                "customer_phone": bill.customer_phone,
                "status": WALKIN,
                "status_label": self.STATUS_LABELS[WALKIN],
                "total": bill.total_amount,
                "items": bill.line_items.all(),
                "bill_id": bill.id,
                "payment_method_label": bill.get_payment_method_display(),
            }
            for bill in walkin_bills
        ]

        if status in self.STATUS_LABELS:
            entries = [e for e in entries if e["status"] == status]
        entries.sort(key=lambda e: e["created_at"], reverse=True)

        paginator = Paginator(entries, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "entries": page_obj.object_list,
                "status": status,
                "status_filters": [("", "All")] + list(self.STATUS_LABELS.items()),
            },
        )


class OrderApproveView(BusinessRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(Order.objects.for_business(request.business), pk=pk)
        payment_method = request.POST.get("payment_method", Bill.CASH)
        if payment_method not in dict(Bill.PAYMENT_METHOD_CHOICES):
            payment_method = Bill.CASH
        try:
            bill = approve_order(order, request.user, payment_method)
        except CartError as exc:
            messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
            return redirect("billing:order-list")

        pdf_bytes = render_bill_pdf(bill)
        bill.pdf_file.save(f"{bill.public_id}.pdf", ContentFile(pdf_bytes), save=True)
        messages.success(request, f"Order approved — bill created for {order.customer_name}.")
        return redirect("billing:bill-whatsapp", pk=bill.pk)


class OrderRejectView(BusinessRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(Order.objects.for_business(request.business), pk=pk)
        try:
            reject_order(order, request.user)
        except CartError as exc:
            messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
        else:
            messages.success(request, f"Order from {order.customer_name} rejected. Stock unchanged.")
        return redirect("billing:order-list")


def pending_order_count(request):
    """Business-scoped JSON endpoint polled by the nav badge."""
    if request.business is None:
        return JsonResponse({}, status=403)
    return JsonResponse({"count": request.business.pending_order_count})
