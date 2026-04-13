from datetime import datetime, date as date_cls

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import UserProfile

User = get_user_model()


def pick_best_available_coach(reference_date=None, preferred_level=None):
    from members.models import Member

    today = reference_date or timezone.localdate()
    matching_level_filter = Q(assigned_members__status=Member.STATUS_ACTIVE)
    if preferred_level:
        matching_level_filter &= Q(assigned_members__skill_level=preferred_level)
    coaches = (
        User.objects.filter(profile__role=UserProfile.ROLE_COACH, is_active=True)
        .annotate(
            matching_level_member_count=Count(
                "assigned_members",
                filter=matching_level_filter,
                distinct=True,
            ),
            active_member_count=Count(
                "assigned_members",
                filter=Q(assigned_members__status=Member.STATUS_ACTIVE),
                distinct=True,
            ),
            total_member_count=Count("assigned_members", distinct=True),
            upcoming_session_count=Count(
                "training_sessions",
                filter=Q(training_sessions__session_date__gte=today),
                distinct=True,
            ),
        )
        .order_by(
            "matching_level_member_count",
            "active_member_count",
            "upcoming_session_count",
            "total_member_count",
            "first_name",
            "username",
        )
    )
    return coaches.first()


def calculate_report_overall_score(report):
    skills = list((report.skill_snapshot or {}).values())
    if not skills:
        return 0
    return round((sum(skills) / len(skills)) * 20)


def report_grade_label(report, overall_score=None):
    if not report:
        return "N/A"
    status_grade_map = {
        "elite": "A",
        "advanced": "A-",
        "developing": "B+",
        "foundation": "B",
    }
    if report.overall_status in status_grade_map:
        return status_grade_map[report.overall_status]
    score = overall_score if overall_score is not None else calculate_report_overall_score(report)
    if score >= 90:
        return "A"
    if score >= 80:
        return "A-"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    return "C"


def report_goal_percentage(report, overall_score=None):
    if not report:
        return 0
    score = overall_score if overall_score is not None else calculate_report_overall_score(report)
    if report.total_sessions:
        return round(min(100, (report.attendance_rate * 0.65) + (score * 0.35)))
    return score


def report_score_delta(report, previous_report=None):
    if not report or not previous_report:
        return 0
    return calculate_report_overall_score(report) - calculate_report_overall_score(previous_report)


def build_recent_progress_items(report, previous_report=None, limit=2):
    if not report:
        return []
    skills = report.skill_snapshot or {}
    previous_skills = previous_report.skill_snapshot if previous_report else {}
    items = []
    for skill, rating in skills.items():
        previous_rating = previous_skills.get(skill, rating)
        delta = round((rating - previous_rating) * 20)
        items.append(
            {
                "label": skill,
                "value": round(rating * 20),
                "delta": delta,
                "delta_label": f"{delta:+d}%" if previous_report else "Stable",
                "tone": "positive" if delta >= 0 else "neutral",
            }
        )
    items.sort(key=lambda row: (row["delta"], row["value"]), reverse=True)
    return items[:limit] if limit else items


def build_training_plan_items(report, limit=3):
    if not report:
        return []
    skills = report.skill_snapshot or {}
    notes = report.skill_notes or {}
    sorted_skills = sorted(skills.items(), key=lambda item: (item[1], item[0]))
    plan_items = []
    for index, (skill, rating) in enumerate(sorted_skills[:limit], start=1):
        note = notes.get(skill) or f"Focus on {skill.lower()} with structured repetitions in the next training cycle."
        plan_items.append(
            {
                "step": index,
                "title": f"{skill} Focus",
                "detail": note,
                "rating": rating,
            }
        )
    return plan_items


def attendance_streak(records):
    streak = 0
    for record in records.exclude(status="scheduled").order_by("-training_session__session_date", "-training_session__start_time"):
        if record.status in {"present", "late"}:
            streak += 1
        else:
            break
    return streak


def format_session_duration(training_session):
    if not training_session:
        return ""
    start = datetime.combine(date_cls.today(), training_session.start_time)
    end = datetime.combine(date_cls.today(), training_session.end_time)
    total_minutes = int((end - start).total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} min"
