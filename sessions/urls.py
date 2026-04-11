from django.urls import path

from sessions.views import (
    AttendanceUpdateView,
    SessionCreateView,
    SessionDetailView,
    SessionListView,
    SessionUpdateView,
)

app_name = "sessions"

urlpatterns = [
    path("", SessionListView.as_view(), name="list"),
    path("create/", SessionCreateView.as_view(), name="create"),
    path("<int:pk>/", SessionDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", SessionUpdateView.as_view(), name="edit"),
    path("<int:pk>/attendance/", AttendanceUpdateView.as_view(), name="attendance"),
]
