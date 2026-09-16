class BusinessMiddleware:
    """Attaches request.business and request.membership from the logged-in
    user's Membership, once per request. Must sit after AuthenticationMiddleware."""

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
        return self.get_response(request)
