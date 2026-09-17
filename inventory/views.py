from decimal import Decimal

from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from accounts.mixins import AdminRequiredMixin, BusinessQuerysetMixin

from .forms import ProductForm, RestockForm, UnitForm
from .imports import build_sample_workbook, import_products_from_workbook
from .models import Product, Unit


class ProductListView(AdminRequiredMixin, BusinessQuerysetMixin, ListView):
    model = Product
    template_name = "inventory/product_list.html"
    context_object_name = "products"

    def get_queryset(self):
        qs = super().get_queryset().select_related("unit")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(category__icontains=query))
        show_removed = self.request.GET.get("show") == "removed"
        qs = qs.filter(is_active=not show_removed)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_removed"] = self.request.GET.get("show") == "removed"
        context["removed_count"] = Product.objects.for_business(self.request.business).filter(
            is_active=False
        ).count()
        return context


class ProductCreateView(AdminRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "inventory/product_form.html"
    success_url = reverse_lazy("inventory:product-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        form.instance.business = self.request.business
        messages.success(self.request, f"Added '{form.instance.name}' to your catalog.")
        return super().form_valid(form)


class ProductUpdateView(AdminRequiredMixin, BusinessQuerysetMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "inventory/product_form.html"
    success_url = reverse_lazy("inventory:product-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["business"] = self.request.business
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Updated '{form.instance.name}'.")
        return super().form_valid(form)


class ProductDeactivateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product.objects.for_business(request.business), pk=pk)
        product.is_active = False
        product.save(update_fields=["is_active"])
        messages.success(
            request,
            f"'{product.name}' removed from the active catalog. Its past bills/reports are unaffected — "
            f"find it under “Show removed” to restore or permanently delete it.",
        )
        return redirect("inventory:product-list")


class ProductRestoreView(AdminRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product.objects.for_business(request.business), pk=pk)
        product.is_active = True
        product.save(update_fields=["is_active"])
        messages.success(request, f"'{product.name}' restored to your active catalog.")
        return redirect(f"{reverse_lazy('inventory:product-list')}?show=removed")


class ProductDeleteView(AdminRequiredMixin, View):
    """Permanently deletes a product — only possible if it has never been
    part of a bill or order. Products with sales history are protected at
    the database level (Product FK is on_delete=PROTECT from BillLineItem/
    OrderLineItem) specifically so past reports can never go inaccurate or
    reference a vanished product; deactivating is the only option for those."""

    def post(self, request, pk):
        product = get_object_or_404(Product.objects.for_business(request.business), pk=pk)
        name = product.name
        try:
            product.delete()
        except ProtectedError:
            messages.error(
                request,
                f"Can't permanently delete '{name}' — it appears in past bills or orders, "
                f"and deleting it would break those records and reports. It stays deactivated instead.",
            )
        else:
            messages.success(request, f"'{name}' permanently deleted.")
        return redirect(f"{reverse_lazy('inventory:product-list')}?show=removed")


class ProductRestockView(AdminRequiredMixin, View):
    """Adds newly-purchased stock to a product. New cost is blended into the
    existing cost_price as a running weighted average (old stock's original
    cost is never re-priced), while the selling price is simply replaced —
    this business sells everything on hand at the current price, not the
    price it happened to be bought at."""

    template_name = "inventory/restock_form.html"

    def get(self, request, pk):
        product = get_object_or_404(Product.objects.for_business(request.business), pk=pk)
        form = RestockForm(initial={
            "new_cost_price": product.cost_price,
            "new_selling_price": product.selling_price,
        })
        return render(request, self.template_name, {"form": form, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product.objects.for_business(request.business), pk=pk)
        form = RestockForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "product": product})

        added_qty = form.cleaned_data["quantity_added"]
        new_cost_price = form.cleaned_data["new_cost_price"]
        new_selling_price = form.cleaned_data["new_selling_price"]

        old_qty = product.stock_qty
        total_qty = old_qty + added_qty
        weighted_cost = (
            (old_qty * product.cost_price) + (added_qty * new_cost_price)
        ) / total_qty

        product.stock_qty = total_qty
        product.cost_price = weighted_cost.quantize(Decimal("0.01"))
        product.selling_price = new_selling_price
        product.save(update_fields=["stock_qty", "cost_price", "selling_price"])

        messages.success(
            request,
            f"Added {added_qty} {product.unit} to '{product.name}'. "
            f"Now {product.stock_qty} {product.unit} in stock at ₹{product.cost_price} avg. cost.",
        )
        return redirect("inventory:product-list")


class UnitCreateView(AdminRequiredMixin, View):
    template_name = "inventory/unit_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": UnitForm()})

    def post(self, request):
        form = UnitForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.business = request.business
            unit.save()
            messages.success(request, f"Added unit '{unit.name}'.")
            return redirect("inventory:product-create")
        return render(request, self.template_name, {"form": form})


class ProductImportView(AdminRequiredMixin, View):
    template_name = "inventory/product_import.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            messages.error(request, "Choose an .xlsx file to import.")
            return render(request, self.template_name, {})

        result = import_products_from_workbook(request.business, upload)
        return render(request, self.template_name, {"result": result})


class ProductSampleTemplateView(AdminRequiredMixin, View):
    def get(self, request):
        content = build_sample_workbook(request.business)
        response = HttpResponse(
            content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="parchi-product-template.xlsx"'
        return response


def stock_snapshot(request):
    """Business-scoped JSON endpoint polled by the billing screen for live stock."""
    if request.business is None:
        return JsonResponse({}, status=403)
    products = Product.objects.for_business(request.business).filter(is_active=True).only(
        "id", "stock_qty"
    )
    return JsonResponse({str(p.id): str(p.stock_qty) for p in products})
