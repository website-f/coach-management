from django.urls import path

from accounts.views import (
    CoachDeleteView,
    CoachDetailView,
    CoachManagementView,
    CoachPasswordChangeView,
    CoachPasswordResetView,
    DashboardView,
    FastLogoutView,
    LandingContentUpdateView,
    NotificationListView,
    NotificationReadView,
    RoleAwareLoginView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", RoleAwareLoginView.as_view(), name="login"),
    path("logout/", FastLogoutView.as_view(), name="logout"),
    path("password/change/", CoachPasswordChangeView.as_view(), name="password_change"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("coaches/", CoachManagementView.as_view(), name="coaches"),
    path("coaches/<int:pk>/", CoachDetailView.as_view(), name="coach_detail"),
    path("coaches/<int:pk>/reset-password/", CoachPasswordResetView.as_view(), name="coach_reset_password"),
    path("coaches/<int:pk>/delete/", CoachDeleteView.as_view(), name="coach_delete"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification_read"),
    path("website/", LandingContentUpdateView.as_view(), name="website"),
]
