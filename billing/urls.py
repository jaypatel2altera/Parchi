from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("new/", views.BillCreateView.as_view(), name="bill-create"),
    path("<int:pk>/whatsapp/", views.BillWhatsAppView.as_view(), name="bill-whatsapp"),
    path("<int:pk>/regenerate-pdf/", views.BillRegeneratePDFView.as_view(), name="bill-regenerate-pdf"),
    path("b/<uuid:public_id>/", views.PublicBillView.as_view(), name="public-bill"),
    path("b/<uuid:public_id>/pdf/", views.PublicBillPDFView.as_view(), name="public-bill-pdf"),
    path("b/<uuid:public_id>/upi-qr.svg", views.PublicBillUPIQRView.as_view(), name="public-bill-upi-qr"),
    path("o/<uuid:order_code>/", views.PublicOrderView.as_view(), name="public-order"),
    path("o/confirmation/<uuid:public_id>/", views.OrderConfirmationView.as_view(), name="order-confirmation"),
    path("o/confirmation/<uuid:public_id>/upi-qr.svg", views.OrderUPIQRView.as_view(), name="order-upi-qr"),
    path("orders/", views.OrderListView.as_view(), name="order-list"),
    path("orders/history/", views.OrderHistoryView.as_view(), name="order-history"),
    path("orders/<int:pk>/approve/", views.OrderApproveView.as_view(), name="order-approve"),
    path("orders/<int:pk>/reject/", views.OrderRejectView.as_view(), name="order-reject"),
    path("orders/api/pending-count/", views.pending_order_count, name="pending-order-count"),
]
