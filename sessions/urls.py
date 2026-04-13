from django.urls import path

from sessions.views import (
    AttendanceUpdateView,
    SessionCreateView,
    SessionPlanAssistantView,
    SessionDetailView,
    SessionFeedbackUpsertView,
    SessionListView,
    SessionPlanGenerateView,
    SessionPlanView,
    SessionPlanSaveView,
    SessionUpdateView,
    SyllabusCreateView,
    SyllabusListView,
    SyllabusUpdateView,
)

app_name = "sessions"

urlpatterns = [
    path("", SessionListView.as_view(), name="list"),
    path("syllabus/", SyllabusListView.as_view(), name="syllabus"),
    path("syllabus/create/", SyllabusCreateView.as_view(), name="syllabus_create"),
    path("syllabus/<int:pk>/edit/", SyllabusUpdateView.as_view(), name="syllabus_edit"),
    path("create/", SessionCreateView.as_view(), name="create"),
    path("<int:pk>/", SessionDetailView.as_view(), name="detail"),
    path("<int:pk>/plan/", SessionPlanView.as_view(), name="plan"),
    path("<int:pk>/plan-data/", SessionPlanGenerateView.as_view(), name="plan_data"),
    path("<int:pk>/plan-assistant/", SessionPlanAssistantView.as_view(), name="plan_assistant"),
    path("<int:pk>/plan-save/", SessionPlanSaveView.as_view(), name="plan_save"),
    path("<int:pk>/edit/", SessionUpdateView.as_view(), name="edit"),
    path("<int:pk>/attendance/", AttendanceUpdateView.as_view(), name="attendance"),
    path("<int:session_pk>/feedback/<int:member_pk>/", SessionFeedbackUpsertView.as_view(), name="feedback"),
]
