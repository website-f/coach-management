from django.urls import path

from members.views import (
    MemberCreateView,
    MemberDeleteView,
    MemberDetailView,
    MemberListView,
    MemberUpdateView,
    export_members_csv,
)

app_name = "members"

urlpatterns = [
    path("", MemberListView.as_view(), name="list"),
    path("create/", MemberCreateView.as_view(), name="create"),
    path("<int:pk>/", MemberDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", MemberUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", MemberDeleteView.as_view(), name="delete"),
    path("export/csv/", export_members_csv, name="export"),
]
