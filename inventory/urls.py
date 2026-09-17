from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product-list"),
    path("new/", views.ProductCreateView.as_view(), name="product-create"),
    path("<int:pk>/edit/", views.ProductUpdateView.as_view(), name="product-update"),
    path("<int:pk>/restock/", views.ProductRestockView.as_view(), name="product-restock"),
    path("<int:pk>/deactivate/", views.ProductDeactivateView.as_view(), name="product-deactivate"),
    path("<int:pk>/restore/", views.ProductRestoreView.as_view(), name="product-restore"),
    path("<int:pk>/delete/", views.ProductDeleteView.as_view(), name="product-delete"),
    path("units/new/", views.UnitCreateView.as_view(), name="unit-create"),
    path("import/", views.ProductImportView.as_view(), name="product-import"),
    path("import/sample.xlsx", views.ProductSampleTemplateView.as_view(), name="product-import-sample"),
    path("api/stock/", views.stock_snapshot, name="stock-snapshot"),
]
