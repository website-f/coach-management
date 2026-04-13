from django.urls import path

from payments.views import (
    MyPaymentsView,
    PaymentHistoryView,
    PaymentReviewView,
    PendingPaymentListView,
    QRCodeCreateView,
    QRCodeListView,
    SubmitPaymentView,
)

app_name = "payments"

urlpatterns = [
    path("qr-codes/", QRCodeListView.as_view(), name="qrcode_list"),
    path("qr-codes/upload/", QRCodeCreateView.as_view(), name="qrcode_create"),
    path("my-payments/", MyPaymentsView.as_view(), name="my_payments"),
    path("invoice/<int:pk>/submit/", SubmitPaymentView.as_view(), name="submit_payment"),
    path("history/", PaymentHistoryView.as_view(), name="payment_history"),
    path("pending-reviews/", PendingPaymentListView.as_view(), name="pending_reviews"),
    path("review/<int:pk>/", PaymentReviewView.as_view(), name="review"),
]
