from django.urls import path

from finance.views import (
    BillingSettingsView,
    FinanceOverviewView,
    InvoiceCreateView,
    InvoiceListView,
    InvoiceUpdateView,
    PaymentPlanCreateView,
    PaymentPlanUpdateView,
    ProductCreateView,
    ProductDeleteView,
    ProductDetailView,
    ProductListView,
    ProductUpdateView,
    export_finance_csv,
)

app_name = "finance"

urlpatterns = [
    path("", FinanceOverviewView.as_view(), name="overview"),
    path("billing/", BillingSettingsView.as_view(), name="billing_settings"),
    path("billing/plans/create/", PaymentPlanCreateView.as_view(), name="payment_plan_create"),
    path("billing/plans/<int:pk>/edit/", PaymentPlanUpdateView.as_view(), name="payment_plan_edit"),
    path("invoices/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/create/", InvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/<int:pk>/edit/", InvoiceUpdateView.as_view(), name="invoice_edit"),
    path("store/", ProductListView.as_view(), name="product_list"),
    path("store/create/", ProductCreateView.as_view(), name="product_create"),
    path("store/<int:pk>/", ProductDetailView.as_view(), name="product_detail"),
    path("store/<int:pk>/edit/", ProductUpdateView.as_view(), name="product_edit"),
    path("store/<int:pk>/delete/", ProductDeleteView.as_view(), name="product_delete"),
    path("export/csv/", export_finance_csv, name="export"),
]
