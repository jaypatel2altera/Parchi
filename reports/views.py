from django.views.generic import TemplateView

from accounts.mixins import AdminRequiredMixin

from . import services
from .forms import DateRangeForm


class DashboardView(AdminRequiredMixin, TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = DateRangeForm(self.request.GET or None)
        start, end = form.range()
        business = self.request.business

        context["form"] = form
        context["start"] = start
        context["end"] = end
        context["top_products"] = services.top_selling_products(business, start, end)
        context["margin_products"] = services.margin_by_product(business, start, end)
        context["summary"] = services.revenue_and_margin(business, start, end)
        context["stock_value"] = services.current_stock_value(business)
        return context
