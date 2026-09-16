import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import models, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView

from .forms import SignupForm, StaffCreationForm
from .mixins import AdminRequiredMixin, SuperuserRequiredMixin
from .models import Business, Membership


class SignupView(CreateView):
    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("inventory:product-list")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Business created. Welcome to Parchi!")
        return response


class ParchiLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_superuser:
            return reverse_lazy("accounts:superadmin-dashboard")
        return super().get_success_url()


class StaffListView(AdminRequiredMixin, ListView):
    template_name = "accounts/staff_list.html"
    context_object_name = "memberships"

    def get_queryset(self):
        return Membership.objects.filter(
            business=self.request.business, role=Membership.STAFF
        ).select_related("user")


class StaffCreateView(AdminRequiredMixin, View):
    template_name = "accounts/staff_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": StaffCreationForm()})

    def post(self, request):
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                Membership.objects.create(
                    user=user, business=request.business, role=Membership.STAFF
                )
            messages.success(request, f"Staff login '{user.username}' created.")
            return redirect("accounts:staff-list")
        return render(request, self.template_name, {"form": form})


class SuperAdminDashboardView(SuperuserRequiredMixin, ListView):
    """In-app platform dashboard: every business on Parchi, with an
    'Impersonate owner' button per row (posts straight to django-hijack's
    own acquire view). Raw Django admin at /admin/ remains as a fallback."""

    template_name = "accounts/superadmin_dashboard.html"
    context_object_name = "businesses"

    def get_queryset(self):
        qs = Business.objects.select_related("owner").order_by("-created_at")
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                models.Q(name__icontains=query) | models.Q(owner__username__icontains=query)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["platform_totals"] = {
            "business_count": Business.objects.count(),
            "total_revenue": sum(b.total_revenue for b in context["businesses"]),
        }
        return context


class BusinessQRCodeView(AdminRequiredMixin, View):
    """Lets an Admin view/print/download the QR code customers scan to
    reach their business's self-service ordering page."""

    template_name = "accounts/qr_code.html"

    def get(self, request):
        order_url = request.build_absolute_uri(
            reverse("billing:public-order", kwargs={"order_code": request.business.order_code})
        )
        return render(request, self.template_name, {"order_url": order_url})


class BusinessQRCodeSVGView(AdminRequiredMixin, View):
    def get(self, request):
        order_url = request.build_absolute_uri(
            reverse("billing:public-order", kwargs={"order_code": request.business.order_code})
        )
        img = qrcode.make(order_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
        response = HttpResponse(content_type="image/svg+xml")
        img.save(response)
        return response


class StaffToggleActiveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        membership = get_object_or_404(
            Membership, pk=pk, business=request.business, role=Membership.STAFF
        )
        membership.is_active = not membership.is_active
        membership.save(update_fields=["is_active"])
        state = "enabled" if membership.is_active else "disabled"
        messages.success(request, f"Staff login '{membership.user.username}' {state}.")
        return redirect("accounts:staff-list")
