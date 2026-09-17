from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.ParchiLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("settings/", views.BusinessSettingsView.as_view(), name="business-settings"),
    path("force-password-change/", views.ForcedPasswordChangeView.as_view(), name="force-password-change"),
    path("staff/", views.StaffListView.as_view(), name="staff-list"),
    path("staff/new/", views.StaffCreateView.as_view(), name="staff-create"),
    path("staff/<int:pk>/edit/", views.StaffUpdateView.as_view(), name="staff-update"),
    path("staff/<int:pk>/toggle/", views.StaffToggleActiveView.as_view(), name="staff-toggle"),
    path(
        "staff/<int:pk>/reset-password/",
        views.StaffResetPasswordView.as_view(),
        name="staff-reset-password",
    ),
    path(
        "staff/<int:pk>/force-password-change/",
        views.StaffForcePasswordChangeView.as_view(),
        name="staff-force-password-change",
    ),
    path("superadmin/", views.SuperAdminDashboardView.as_view(), name="superadmin-dashboard"),
    path("qr-code/", views.BusinessQRCodeView.as_view(), name="qr-code"),
    path("qr-code.svg", views.BusinessQRCodeSVGView.as_view(), name="qr-code-svg"),
]
