from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.views import (
    CoachManagementView,
    DashboardView,
    LandingContentUpdateView,
    NotificationListView,
    NotificationReadView,
    RoleAwareLoginView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", RoleAwareLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("coaches/", CoachManagementView.as_view(), name="coaches"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification_read"),
    path("website/", LandingContentUpdateView.as_view(), name="website"),
]
