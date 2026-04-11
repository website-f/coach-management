import csv

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.decorators import role_required
from accounts.mixins import AdminOrCoachRequiredMixin, AdminRequiredMixin
from accounts.utils import ROLE_ADMIN, ROLE_COACH, ROLE_PARENT, has_role
from accounts.models import UserProfile
from finance.models import Invoice
from members.forms import MemberForm
from members.models import Member
from sessions.models import AttendanceRecord

User = get_user_model()


def visible_members_for_user(user):
    queryset = Member.objects.select_related("assigned_coach", "parent_user", "created_by")
    if has_role(user, ROLE_PARENT):
        return queryset.filter(parent_user=user)
    return queryset


class MemberListView(LoginRequiredMixin, ListView):
    model = Member
    template_name = "members/member_list.html"
    context_object_name = "members"
    paginate_by = 10

    def get_queryset(self):
        queryset = visible_members_for_user(self.request.user)
        search = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        coach = self.request.GET.get("coach", "").strip()
        if search:
            queryset = queryset.filter(full_name__icontains=search)
        if status:
            queryset = queryset.filter(status=status)
        if coach:
            queryset = queryset.filter(assigned_coach_id=coach)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN, ROLE_COACH)
        context["is_admin"] = has_role(self.request.user, ROLE_ADMIN)
        context["statuses"] = Member.STATUS_CHOICES
        context["coaches"] = User.objects.filter(profile__role=UserProfile.ROLE_COACH).order_by("first_name", "username")
        return context


class MemberDetailView(LoginRequiredMixin, DetailView):
    model = Member
    template_name = "members/member_detail.html"
    context_object_name = "member"

    def get_queryset(self):
        return visible_members_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = self.object
        context["attendance_history"] = AttendanceRecord.objects.filter(member=member).select_related(
            "training_session"
        )[:10]
        context["invoices"] = Invoice.objects.filter(member=member)[:10]
        context["can_manage"] = has_role(self.request.user, ROLE_ADMIN, ROLE_COACH)
        return context


class MemberCreateView(AdminOrCoachRequiredMixin, CreateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_url = reverse_lazy("members:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Member profile created successfully.")
        return response


class MemberUpdateView(AdminOrCoachRequiredMixin, UpdateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_url = reverse_lazy("members:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Member profile updated successfully.")
        return response


class MemberDeleteView(AdminRequiredMixin, DeleteView):
    model = Member
    template_name = "members/member_confirm_delete.html"
    success_url = reverse_lazy("members:list")

    def form_valid(self, form):
        messages.success(self.request, "Member profile deleted.")
        return super().form_valid(form)


@role_required(ROLE_ADMIN)
def export_members_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="members.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Full Name",
            "DOB",
            "Contact",
            "Membership",
            "Coach",
            "Status",
            "Parent Username",
        ]
    )
    for member in Member.objects.select_related("assigned_coach", "parent_user").order_by("full_name"):
        writer.writerow(
            [
                member.full_name,
                member.date_of_birth,
                member.contact_number,
                member.membership_type,
                member.assigned_coach.username if member.assigned_coach else "",
                member.status,
                member.parent_user.username if member.parent_user else "",
            ]
        )
    return response

# Create your views here.
