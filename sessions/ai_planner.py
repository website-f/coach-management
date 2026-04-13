import json
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from members.services import build_recent_progress_items
from members.models import ProgressReport
from sessions.models import SessionFeedback, SessionPlannerEntry
from sessions.services import build_session_plan


class PlannerAssistantError(Exception):
    pass


def recent_report_rows(training_session, limit=6):
    rows = []
    member_ids = list(
        training_session.attendance_records.values_list("member_id", flat=True)
    )
    if not member_ids:
        return rows

    reports = (
        ProgressReport.objects.filter(member_id__in=member_ids)
        .select_related("member")
        .order_by("member__full_name", "-period_end", "-created_at")
    )
    seen_members = set()
    for report in reports:
        if report.member_id in seen_members:
            continue
        seen_members.add(report.member_id)
        rows.append(
            {
                "member": report.member.full_name,
                "period": report.period_label,
                "status": report.get_overall_status_display(),
                "attendance_rate": report.attendance_rate,
                "coach_reflection": report.coach_reflection[:220].strip(),
                "skill_notes": report.skill_notes,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def report_trend_rows(training_session, limit=4):
    rows = []
    member_ids = list(training_session.attendance_records.values_list("member_id", flat=True))
    if not member_ids:
        return rows

    grouped_reports = {}
    reports = (
        ProgressReport.objects.filter(member_id__in=member_ids)
        .select_related("member")
        .order_by("member_id", "-period_end", "-created_at")
    )
    for report in reports:
        bucket = grouped_reports.setdefault(report.member_id, [])
        if len(bucket) < 2:
            bucket.append(report)

    for member_id in member_ids[:limit]:
        reports = grouped_reports.get(member_id, [])
        if not reports:
            continue
        latest_report = reports[0]
        previous_report = reports[1] if len(reports) > 1 else None
        progress_items = build_recent_progress_items(latest_report, previous_report, limit=2)
        rows.append(
            {
                "member": latest_report.member.full_name,
                "status": latest_report.get_overall_status_display(),
                "priority_skills": [
                    {
                        "label": item["label"],
                        "delta_label": item["delta_label"],
                        "value": item["value"],
                    }
                    for item in progress_items
                ],
            }
        )
    return rows


def recent_feedback_rows(training_session, limit=6):
    feedback_rows = []
    member_ids = list(training_session.attendance_records.values_list("member_id", flat=True))
    entries = (
        SessionFeedback.objects.filter(member_id__in=member_ids)
        .select_related("member", "coach", "training_session")
        .order_by("-training_session__session_date", "-updated_at")
    )
    seen_members = set()
    for entry in entries:
        if entry.member_id in seen_members:
            continue
        seen_members.add(entry.member_id)
        feedback_rows.append(
            {
                "member": entry.member.full_name,
                "session": entry.training_session.title,
                "session_date": entry.training_session.session_date.isoformat(),
                "coach": entry.coach.get_full_name() if entry.coach else "Coach",
                "feedback_excerpt": entry.feedback_text[:240].strip(),
                "has_video": bool(entry.video_proof),
            }
        )
        if len(feedback_rows) >= limit:
            break
    return feedback_rows


def recent_saved_rows(training_session, limit=3):
    return [
        {
            "title": item.title,
            "prompt": item.user_prompt[:180].strip(),
            "saved_at": timezone.localtime(item.created_at).strftime("%d %b %Y %H:%M"),
            "source": item.get_source_display(),
        }
        for item in training_session.planner_entries.all()[:limit]
    ]


def normalize_prompt(value):
    return " ".join((value or "").strip().lower().split())


def find_cached_plan(training_session, user_prompt):
    normalized_prompt = normalize_prompt(user_prompt)
    if not normalized_prompt:
        return None

    for item in training_session.planner_entries.all()[:12]:
        if normalize_prompt(item.user_prompt) == normalized_prompt:
            return item
    return None


def build_planner_context(training_session):
    blueprint = build_session_plan(training_session)
    roster_rows = []
    attendance_rows = training_session.attendance_records.select_related("member").order_by("member__full_name")
    for row in attendance_rows:
        roster_rows.append(
            {
                "name": row.member.full_name,
                "skill_level": row.member.get_skill_level_display(),
                "membership_type": row.member.get_membership_type_display(),
                "attendance_status": row.get_status_display(),
            }
        )

    return {
        "session": {
            "title": training_session.title,
            "date": training_session.session_date.isoformat(),
            "start_time": training_session.start_time.strftime("%H:%M"),
            "end_time": training_session.end_time.strftime("%H:%M"),
            "court": training_session.court,
            "coach": training_session.coach.get_full_name() if training_session.coach else "Unassigned",
        },
        "blueprint": blueprint,
        "roster": roster_rows,
        "recent_reports": recent_report_rows(training_session),
        "report_trends": report_trend_rows(training_session),
        "recent_feedback": recent_feedback_rows(training_session),
        "saved_plans": recent_saved_rows(training_session),
    }


def build_assistant_messages(training_session, user_prompt):
    context = build_planner_context(training_session)
    system_prompt = """
You are NYO Coach Planner, a badminton session-planning assistant for coaches and admins.
Your job is to produce practical, session-ready badminton plans grounded in the admin syllabus and live session context.

Rules:
- Stay aligned to the syllabus and the actual session roster.
- Be concrete, structured, and coach-friendly.
- Do not invent players, progress reports, payment facts, or schedule details.
- When fees are unpaid, mention them only as a coordination note, not the main coaching focus.
- Prefer actionable badminton drills, time blocks, coaching cues, match scenarios, and adaptations.
- Use recent feedback and report trends to personalize the answer when they are available.
- Answer in clean markdown.
- Start with a short title line.
- Then include sections:
  1. Session Goal
  2. Today's Flow
  3. Coaching Cues
  4. Adaptations
  5. Follow-up
""".strip()

    user_message = (
        "Coach request:\n"
        f"{user_prompt.strip()}\n\n"
        "Live session context JSON:\n"
        f"{json.dumps(context, indent=2, default=str)}"
    )
    return context, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]


def derive_title(user_prompt, fallback_title):
    prompt = (user_prompt or "").strip()
    if not prompt:
        return fallback_title
    compact = " ".join(prompt.split())
    if len(compact) > 80:
        compact = f"{compact[:77]}..."
    return compact


def render_fallback_response(training_session, user_prompt, context):
    blueprint = context["blueprint"]
    timeline = "\n".join(
        f"- {item['duration']}: {item['title']} - {item['detail']}"
        for item in blueprint["blocks"]
    )
    cues = "\n".join(f"- {item}" for item in blueprint["coach_prompts"])
    adaptations = [
        f"- Adjust drill density for a {blueprint['roster_size']}-player roster.",
        f"- Re-emphasize the {blueprint['track_label']} syllabus objective if attention drops.",
    ]
    if blueprint["payment_count"]:
        adaptations.append(
            f"- Quietly remind staff that {blueprint['payment_count']} player(s) still show unpaid this month."
        )
    follow_up = blueprint["syllabus_reference"]["homework"] or "Review one key coaching cue with the group."

    response = (
        f"# {blueprint['plan_title']}\n\n"
        f"## Session Goal\n"
        f"{blueprint['summary']}\n\n"
        f"Coach ask: {user_prompt.strip() or 'Plan for today'}\n\n"
        f"## Today's Flow\n"
        f"{timeline}\n\n"
        f"## Coaching Cues\n"
        f"{cues}\n\n"
        f"## Adaptations\n"
        f"{chr(10).join(adaptations)}\n\n"
        f"## Follow-up\n"
        f"{follow_up}\n"
    )
    return {
        "title": derive_title(user_prompt, blueprint["plan_title"]),
        "response": response,
        "source": SessionPlannerEntry.SOURCE_FALLBACK,
        "model_name": "rule-based",
        "context": context,
        "used_fallback": True,
        "warning": "Ollama was unavailable, so the system used the built-in planner.",
    }


def call_ollama(messages):
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.4,
            "top_p": 0.9,
            "repeat_penalty": 1.05,
        },
    }
    req = request.Request(
        f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=settings.OLLAMA_TIMEOUT) as response:
            raw_body = response.read().decode("utf-8")
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        raise PlannerAssistantError(str(exc)) from exc

    try:
        parsed = json.loads(raw_body)
        return parsed["message"]["content"].strip()
    except (KeyError, json.JSONDecodeError) as exc:
        raise PlannerAssistantError("Invalid response returned by Ollama.") from exc


def generate_ai_planner_reply(training_session, user_prompt):
    cached_plan = find_cached_plan(training_session, user_prompt)
    if cached_plan:
        return {
            "title": cached_plan.title,
            "response": cached_plan.assistant_response,
            "source": cached_plan.source,
            "model_name": cached_plan.model_name or ("rule-based" if cached_plan.source == SessionPlannerEntry.SOURCE_FALLBACK else settings.OLLAMA_MODEL),
            "context": {},
            "used_fallback": cached_plan.source == SessionPlannerEntry.SOURCE_FALLBACK,
            "warning": "Loaded from the saved session planner history to respond faster.",
            "from_cache": True,
            "cached_entry_id": cached_plan.pk,
        }

    context, messages = build_assistant_messages(training_session, user_prompt)
    fallback_title = context["blueprint"]["plan_title"]

    if settings.AI_PLANNER_ENABLED and settings.AI_PLANNER_BACKEND == "ollama":
        try:
            content = call_ollama(messages)
            return {
                "title": derive_title(user_prompt, fallback_title),
                "response": content,
                "source": SessionPlannerEntry.SOURCE_OLLAMA,
                "model_name": settings.OLLAMA_MODEL,
                "context": context,
                "used_fallback": False,
                "warning": "",
                "from_cache": False,
            }
        except PlannerAssistantError as exc:
            if not settings.AI_PLANNER_FALLBACK_ENABLED:
                raise
            fallback_payload = render_fallback_response(training_session, user_prompt, context)
            fallback_payload["warning"] = f"Ollama is unavailable right now: {exc}"
            fallback_payload["from_cache"] = False
            return fallback_payload

    fallback_payload = render_fallback_response(training_session, user_prompt, context)
    fallback_payload["from_cache"] = False
    return fallback_payload
