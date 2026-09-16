from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.ParchiLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("staff/", views.StaffListView.as_view(), name="staff-list"),
    path("staff/new/", views.StaffCreateView.as_view(), name="staff-create"),
    path("staff/<int:pk>/toggle/", views.StaffToggleActiveView.as_view(), name="staff-toggle"),
    path("superadmin/", views.SuperAdminDashboardView.as_view(), name="superadmin-dashboard"),
    path("qr-code/", views.BusinessQRCodeView.as_view(), name="qr-code"),
    path("qr-code.svg", views.BusinessQRCodeSVGView.as_view(), name="qr-code-svg"),
]
