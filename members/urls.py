from django.urls import path

from members.views import (
    AdmissionApplicationCreateView,
    LeadCommunicationCreateView,
    AdmissionApplicationListView,
    AdmissionApplicationReviewView,
    CRMWorkspaceView,
    MemberCommunicationCreateView,
    MemberCreateView,
    MemberDeleteView,
    MemberDetailView,
    MemberLevelUpdateView,
    MemberListView,
    MemberUpdateView,
    ProgressReportCreateView,
    ProgressReportDetailView,
    ProgressReportListView,
    ProgressReportUpdateView,
    export_members_csv,
)

app_name = "members"

urlpatterns = [
    path("", MemberListView.as_view(), name="list"),
    path("crm/", CRMWorkspaceView.as_view(), name="crm"),
    path("apply/", AdmissionApplicationCreateView.as_view(), name="apply"),
    path("applications/", AdmissionApplicationListView.as_view(), name="application_list"),
    path("applications/<int:pk>/communications/create/", LeadCommunicationCreateView.as_view(), name="application_communication_create"),
    path("applications/<int:pk>/", AdmissionApplicationReviewView.as_view(), name="application_review"),
    path("reports/", ProgressReportListView.as_view(), name="report_list"),
    path("reports/create/", ProgressReportCreateView.as_view(), name="report_create"),
    path("reports/<int:pk>/", ProgressReportDetailView.as_view(), name="report_detail"),
    path("reports/<int:pk>/edit/", ProgressReportUpdateView.as_view(), name="report_edit"),
    path("create/", MemberCreateView.as_view(), name="create"),
    path("<int:pk>/communications/create/", MemberCommunicationCreateView.as_view(), name="communication_create"),
    path("<int:pk>/level/", MemberLevelUpdateView.as_view(), name="level_update"),
    path("<int:pk>/", MemberDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", MemberUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", MemberDeleteView.as_view(), name="delete"),
    path("export/csv/", export_members_csv, name="export"),
]
