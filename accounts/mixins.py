from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class SuperuserRequiredMixin(LoginRequiredMixin):
    """Requires a Django superuser (the Parchi platform operator, not a
    business's Admin). Checked before the view runs."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            raise PermissionDenied("Platform admin only.")
        return super().dispatch(request, *args, **kwargs)


class BusinessRequiredMixin(LoginRequiredMixin):
    """Requires login and an active business membership (request.business)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.business is None:
            raise PermissionDenied("No active business membership.")
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(BusinessRequiredMixin):
    """Requires the logged-in user to be the ADMIN of their business.
    Checked before the view runs, so a non-admin POST never executes."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.business is not None:
            if not request.membership.is_admin:
                raise PermissionDenied("Admin only.")
        return super().dispatch(request, *args, **kwargs)


class BusinessQuerysetMixin:
    """Mix into ListView/DetailView/UpdateView/DeleteView. Ensures get_queryset()
    can never return another business's rows, even if a URL pk is guessed."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.for_business(self.request.business)
