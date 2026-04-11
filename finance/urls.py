from django.urls import path

from finance.views import (
    FinanceOverviewView,
    InvoiceCreateView,
    InvoiceListView,
    InvoiceUpdateView,
    export_finance_csv,
)

app_name = "finance"

urlpatterns = [
    path("", FinanceOverviewView.as_view(), name="overview"),
    path("invoices/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/create/", InvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/<int:pk>/edit/", InvoiceUpdateView.as_view(), name="invoice_edit"),
    path("export/csv/", export_finance_csv, name="export"),
]
