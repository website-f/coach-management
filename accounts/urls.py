from django.urls import path

from accounts.views import (
    BranchCreateView,
    BranchDeleteView,
    BranchListView,
    BranchUpdateView,
    CoachDeleteView,
    CoachDetailView,
    CoachLevelUpdateView,
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
    path("coaches/<int:pk>/class-level/", CoachLevelUpdateView.as_view(), name="coach_class_level"),
    path("branches/", BranchListView.as_view(), name="branches"),
    path("branches/create/", BranchCreateView.as_view(), name="branch_create"),
    path("branches/<int:pk>/edit/", BranchUpdateView.as_view(), name="branch_edit"),
    path("branches/<int:pk>/delete/", BranchDeleteView.as_view(), name="branch_delete"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification_read"),
    path("website/", LandingContentUpdateView.as_view(), name="website"),
]
