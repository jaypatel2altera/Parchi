from django.shortcuts import redirect
from django.urls import reverse

# Paths a user with a pending forced password change must still be able to
# reach — otherwise they could never actually change it, or log out.
FORCE_PASSWORD_CHANGE_EXEMPT_URL_NAMES = {"accounts:force-password-change", "accounts:logout"}


class BusinessMiddleware:
    """Attaches request.business and request.membership from the logged-in
    user's Membership, once per request. Must sit after AuthenticationMiddleware.

    Also gates every page behind a forced password change: an Admin resetting
    or flagging a staff login sets Membership.must_change_password, and this
    is the one place that check can't be forgotten on a new view."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.business = None
        request.membership = None
        if request.user.is_authenticated:
            membership = getattr(request.user, "membership", None)
            if membership is not None and membership.is_active:
                request.business = membership.business
                request.membership = membership
                if membership.must_change_password:
                    exempt_paths = {reverse(name) for name in FORCE_PASSWORD_CHANGE_EXEMPT_URL_NAMES}
                    if request.path not in exempt_paths:
                        return redirect("accounts:force-password-change")
        return self.get_response(request)
