from collections import Counter
from statistics import mean

from django.db import transaction
from django.utils import timezone

from finance.models import Invoice
from members.models import Member, ProgressReport
from members.services import calculate_report_overall_score
from sessions.models import AttendanceRecord, WeeklySyllabus

DEFAULT_SYLLABUS_BLUEPRINT = {
    WeeklySyllabus.TRACK_BEGINNER: [
        {
            "week_number": 1,
            "title": "Grip, ready stance, and court movement basics",
            "objective": "Build safe racket handling, split-step timing, and confidence moving to the shuttle.",
            "warm_up_plan": "Light jog, line hops, shadow split-step, and racket-grip activation for both forehand and backhand.",
            "technical_focus": "Grip switching, ready position, basic forehand serve, and underhand lift repetitions with coach feeding.",
            "tactical_focus": "Teach where to recover after each shot and how to keep rallies alive instead of chasing winners too early.",
            "coaching_cues": "Stay low, land softly after the split step, and reset the racket in front after every contact.",
            "homework": "Two home blocks of shadow footwork and 20 controlled serve reps.",
        },
        {
            "week_number": 2,
            "title": "Serve consistency and lift control",
            "objective": "Improve the ability to start points cleanly and move the shuttle high to a safe target.",
            "warm_up_plan": "Dynamic ankle and hip mobility, fast-feet ladder, then partner toss-and-catch to build rhythm.",
            "technical_focus": "Short serve mechanics, underhand lift height, and forecourt net pickup with simple multi-shuttle feeds.",
            "tactical_focus": "Introduce the idea of using height and depth to recover time instead of rushing flat exchanges.",
            "coaching_cues": "Relax the grip before contact, send the shuttle high enough, and recover to center after every lift.",
            "homework": "Record 10 short serves and self-check stance width and follow-through.",
        },
        {
            "week_number": 3,
            "title": "Overhead basics and clear rhythm",
            "objective": "Create a repeatable overhead movement pattern for clear and high defensive contact.",
            "warm_up_plan": "Shoulder activation, trunk rotation, shadow chasse steps, and overhead throwing pattern rehearsal.",
            "technical_focus": "Preparation for overhead contact, throwing action, full clear technique, and simple rear-court footwork.",
            "tactical_focus": "Understand when to clear high to escape pressure and reset the rally.",
            "coaching_cues": "Turn early, get behind the shuttle, and finish balanced so the next movement starts immediately.",
            "homework": "Mirror shadow overhead preparation for 5 minutes on two separate days.",
        },
        {
            "week_number": 4,
            "title": "Net touch and rally building",
            "objective": "Help players move smoothly from lift-clear patterns into soft net control and longer rallies.",
            "warm_up_plan": "Reaction tags, front-court lunges, and fingertip control drills with shuttle taps over the net.",
            "technical_focus": "Net brush, simple tumble introduction, forecourt lunge recovery, and front-back transition feeds.",
            "tactical_focus": "Show how net quality can force the opponent to lift and create a safer attacking opportunity later.",
            "coaching_cues": "Arrive early at the net, soften the hand on contact, and push back out after the lunge.",
            "homework": "3 rounds of lunge balance holds plus service-line net taps.",
        },
    ],
    WeeklySyllabus.TRACK_INTERMEDIATE: [
        {
            "week_number": 1,
            "title": "Tempo control and front-back patterns",
            "objective": "Control rally rhythm through front-back movement and cleaner shot selection.",
            "warm_up_plan": "Band activation, split-step reaction calls, and shadow six-point movement with tempo changes.",
            "technical_focus": "Drive lift transition, front-back footwork, and tighter block-to-net control under movement.",
            "tactical_focus": "Teach when to slow the rally with net control and when to speed it up with flat pressure.",
            "coaching_cues": "Read early, keep the base alive, and choose one clear intention before each shot.",
            "homework": "Shadow six-point movement with a metronome or count for 8 minutes.",
        },
        {
            "week_number": 2,
            "title": "Attack preparation and midcourt pressure",
            "objective": "Create better attacking chances by improving setup shots, balance, and first follow-up movement.",
            "warm_up_plan": "Medicine-ball rotation, chasse-to-lunge repeats, and reaction starts from a neutral base.",
            "technical_focus": "Attacking clear, drop-to-net sequence, and midcourt interception drills with coach variation.",
            "tactical_focus": "Use the first attacking shot to move the opponent, then hunt the weaker reply instead of forcing winners instantly.",
            "coaching_cues": "Attack with balance, keep the non-racket arm active, and move through the follow-up step.",
            "homework": "Review one training clip and note two moments where the follow-up step was late.",
        },
        {
            "week_number": 3,
            "title": "Defensive transitions under pressure",
            "objective": "Recover from smashes and flat attacks with better racket position and transition choices.",
            "warm_up_plan": "Elastic-band defense stance work, mirror reactions, and low-center shuffle patterns.",
            "technical_focus": "Smash defense, block lift choice, counter-drive timing, and partner pressure sequences.",
            "tactical_focus": "Recognize when to neutralize, when to counter, and when to lift to safer zones.",
            "coaching_cues": "Stay compact, racket up before the shuttle crosses, and recover immediately after the first defense.",
            "homework": "Do 3 rounds of low defense hold and 20 counter-drive shadow contacts.",
        },
        {
            "week_number": 4,
            "title": "Conditioned matchplay and pattern discipline",
            "objective": "Apply weekly themes inside match conditions without losing movement or tactical discipline.",
            "warm_up_plan": "Competitive footwork relay, shadow pattern rehearsal, and short controlled rally start-ups.",
            "technical_focus": "Pattern-based games: clear-drop-net, serve-third-ball, and defense-to-counter transitions.",
            "tactical_focus": "Link the first three shots into a clear plan and keep the rally pattern intentional under score pressure.",
            "coaching_cues": "Call the pattern before the rally, review decisions after the rally, and protect quality over speed.",
            "homework": "Journal one pattern that worked and one that broke down during conditioned games.",
        },
    ],
    WeeklySyllabus.TRACK_ADVANCED: [
        {
            "week_number": 1,
            "title": "Rear-court quality and first-ball pressure",
            "objective": "Raise the quality of the first attacking sequence from serve return or rear-court setup.",
            "warm_up_plan": "Explosive band prep, jump mechanics, and rear-court shadow with immediate recovery steps.",
            "technical_focus": "Steep smash mechanics, half-smash variation, and first follow-up interception positioning.",
            "tactical_focus": "Build pressure by combining angle, recovery, and the next shot instead of relying on pure power.",
            "coaching_cues": "Create angle with preparation, land ready to move, and hunt the next shuttle with intent.",
            "homework": "Clip review: identify 3 smashes where the recovery step made or broke the point.",
        },
        {
            "week_number": 2,
            "title": "Deception windows and hold-release control",
            "objective": "Add disguise and hold-release timing without sacrificing balance or shuttle quality.",
            "warm_up_plan": "Racket-head sensitivity work, delayed-contact shadow, and reactive lunge recoveries.",
            "technical_focus": "Hold-and-flick net work, slice drop variation, and late-contact decision drills.",
            "tactical_focus": "Use deception only when the body position still allows recovery and the previous shot created enough time.",
            "coaching_cues": "Sell the same preparation, stay loose through the hand, and never trade balance for disguise.",
            "homework": "Shadow 12 deceptive preparations with full recovery after each one.",
        },
        {
            "week_number": 3,
            "title": "Transition speed in doubles or fast exchanges",
            "objective": "Sharpen decision speed and structure during flatter, faster pressure phases.",
            "warm_up_plan": "Partner mirror shuffle, multi-direction reaction starts, and fast racket preparation drills.",
            "technical_focus": "Drive exchanges, midcourt kills, defensive drive resets, and transition shape after interceptions.",
            "tactical_focus": "Identify whether the pair or player should keep the attack, reset, or rotate out of trouble.",
            "coaching_cues": "Compact preparation, hips ready to rotate, and decision made before the shuttle arrives.",
            "homework": "Speed-rally visualization: replay three fast-exchange patterns mentally before the next session.",
        },
        {
            "week_number": 4,
            "title": "Pressure match scenarios and close-out discipline",
            "objective": "Execute under score pressure while protecting structure and reducing unforced errors.",
            "warm_up_plan": "Scoreboard sprints, breathing reset drills, and short pressure-rally activations.",
            "technical_focus": "Serve-return under pressure, late-game rear-court choices, and endgame defense-to-attack transitions.",
            "tactical_focus": "Choose the highest percentage option on key points and stay disciplined through routine.",
            "coaching_cues": "Reset breathing between rallies, trust the first pattern, and finish points with clarity not panic.",
            "homework": "Write one match routine for 18-all or game-point situations.",
        },
    ],
    WeeklySyllabus.TRACK_PRO: [
        {
            "week_number": 1,
            "title": "Scouting-based first three shots",
            "objective": "Train first-three-shot patterns based on opponent habits and serve/return tendencies.",
            "warm_up_plan": "High-speed movement prep, shoulder power activation, and decision-cue reaction starts.",
            "technical_focus": "Serve precision, return variation, and third-ball pattern execution at match pace.",
            "tactical_focus": "Select the opening pattern using a scouting cue and commit to the follow-up with full intent.",
            "coaching_cues": "Own the first decision, disguise without delay, and recover to the next tactical lane instantly.",
            "homework": "Review scouting notes and prepare two pattern options for each return zone.",
        },
        {
            "week_number": 2,
            "title": "Tempo traps and transition steals",
            "objective": "Manipulate rally speed to create interceptions and force predictable replies.",
            "warm_up_plan": "Explosive med-ball release, acceleration ladders, and tempo-change shadow patterns.",
            "technical_focus": "Hold-release from the forecourt, disguised pace changes, and transition steals from midcourt.",
            "tactical_focus": "Use one slower setup ball to create the faster interception window that follows.",
            "coaching_cues": "Control pace intentionally, read shoulder cues early, and step in before the opponent resets.",
            "homework": "Map one tempo trap sequence that fits your strongest attack lane.",
        },
        {
            "week_number": 3,
            "title": "Countering elite pressure and recovery economy",
            "objective": "Preserve quality under elite pace by tightening recovery choices and defensive counter timing.",
            "warm_up_plan": "Reactive chaos feeds, low-base defense prep, and aggressive recovery strides.",
            "technical_focus": "Compact defense, counter-blocks, delayed lifts, and recovery economy after full-stretch rallies.",
            "tactical_focus": "Absorb pressure with compact options until the opponent over-commits, then counter through the open lane.",
            "coaching_cues": "Do less but do it earlier, trust the compact racket path, and recover before admiring the shot.",
            "homework": "Clip review: log three moments where early recovery created a counter opportunity.",
        },
        {
            "week_number": 4,
            "title": "Competition simulation and tactical adaptation",
            "objective": "Simulate tournament pressure and adapt the plan inside the session when patterns fail.",
            "warm_up_plan": "Tournament-style activation, serve routine rehearsal, and short pressure sparring.",
            "technical_focus": "Match-speed sequences with coaching interruptions for tactical resets and adaptation calls.",
            "tactical_focus": "Read the match trend quickly, pivot to a backup pattern, and protect discipline point by point.",
            "coaching_cues": "Name the trend, call the adjustment, and execute the next rally with total clarity.",
            "homework": "Prepare a post-match debrief with one winning pattern and one adjustment pattern.",
        },
    ],
}


LEVEL_TRACK_MAP = {
    Member.LEVEL_BASIC: WeeklySyllabus.TRACK_BEGINNER,
    Member.LEVEL_INTERMEDIATE: WeeklySyllabus.TRACK_INTERMEDIATE,
    Member.LEVEL_ADVANCED: WeeklySyllabus.TRACK_ADVANCED,
}


@transaction.atomic
def ensure_default_syllabus():
    for track, rows in DEFAULT_SYLLABUS_BLUEPRINT.items():
        for row in rows:
            WeeklySyllabus.objects.get_or_create(
                track=track,
                week_number=row["week_number"],
                defaults=row,
            )


def determine_session_track(training_session):
    roster = list(
        Member.objects.filter(attendance_records__training_session=training_session)
        .select_related("assigned_coach", "parent_user")
        .distinct()
    )
    if not roster:
        return WeeklySyllabus.TRACK_BEGINNER, roster, 0

    level_counts = Counter(member.skill_level for member in roster)
    dominant_level = level_counts.most_common(1)[0][0]
    latest_reports = []
    for member in roster:
        report = member.progress_reports.order_by("-period_end", "-created_at").first()
        if report:
            latest_reports.append(calculate_report_overall_score(report))
    average_score = round(mean(latest_reports)) if latest_reports else 0

    track = LEVEL_TRACK_MAP.get(dominant_level, WeeklySyllabus.TRACK_BEGINNER)
    if track == WeeklySyllabus.TRACK_ADVANCED and average_score >= 85:
        track = WeeklySyllabus.TRACK_PRO
    return track, roster, average_score


def resolve_syllabus_week(training_session, roster, track):
    ensure_default_syllabus()
    weeks = list(WeeklySyllabus.objects.filter(track=track, is_active=True).order_by("week_number"))
    if not weeks:
        return None, 1

    joined_dates = [member.joined_at for member in roster if member.joined_at]
    reference_date = min(joined_dates) if joined_dates else training_session.session_date.replace(day=1)
    elapsed_days = max(0, (training_session.session_date - reference_date).days)
    program_week = (elapsed_days // 7) + 1
    resolved_week = ((program_week - 1) % len(weeks)) + 1
    syllabus_week = next((item for item in weeks if item.week_number == resolved_week), weeks[0])
    return syllabus_week, resolved_week


def build_session_plan(training_session):
    track, roster, average_score = determine_session_track(training_session)
    syllabus_week, resolved_week = resolve_syllabus_week(training_session, roster, track)

    roster_size = len(roster)
    recent_records = AttendanceRecord.objects.filter(
        member__in=roster,
        training_session__session_date__lt=training_session.session_date,
    ).exclude(status=AttendanceRecord.STATUS_SCHEDULED)
    total_recent_records = recent_records.count()
    attended_recent_records = recent_records.filter(
        status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
    ).count()
    attendance_rate = round((attended_recent_records / total_recent_records) * 100, 1) if total_recent_records else 0

    unpaid_this_month = list(
        Invoice.objects.filter(
            member__in=roster,
            period__year=training_session.session_date.year,
            period__month=training_session.session_date.month,
        )
        .exclude(status=Invoice.STATUS_PAID)
        .select_related("member")
        .order_by("member__full_name")
    )

    group_profile = "small group" if roster_size <= 4 else "mid-sized group" if roster_size <= 8 else "large group"
    recap_note = (
        "Add an extra recap demo before the first main drill because the recent attendance rhythm is uneven."
        if attendance_rate and attendance_rate < 70
        else "Keep transitions tight and let the main drill start quickly because the group attendance rhythm is stable."
    )
    organization_note = {
        "small group": "Use more coach-fed reps and individual correction windows.",
        "mid-sized group": "Run paired stations so both repetition count and observation quality stay balanced.",
        "large group": "Split the roster into lanes and assign clear rotation rules before the first shuttle starts.",
    }[group_profile]

    roster_levels = Counter(member.get_skill_level_display() for member in roster)
    roster_level_summary = ", ".join(f"{label} x{count}" for label, count in roster_levels.items()) if roster_levels else "No roster linked yet"
    payment_summary = (
        ", ".join(invoice.member.full_name for invoice in unpaid_this_month[:4])
        + (f", +{len(unpaid_this_month) - 4} more" if len(unpaid_this_month) > 4 else "")
        if unpaid_this_month
        else "All linked students are clear for this month."
    )

    if syllabus_week:
        plan_title = f"{syllabus_week.get_track_display()} Week {resolved_week}: {syllabus_week.title}"
        summary = (
            f"This session should lean into {syllabus_week.title.lower()} for a {group_profile} roster. "
            f"The syllabus target is to {syllabus_week.objective.lower()}"
        )
        warm_up = syllabus_week.warm_up_plan
        technical = syllabus_week.technical_focus
        tactical = syllabus_week.tactical_focus
        cues = syllabus_week.coaching_cues
        homework = syllabus_week.homework or "Ask players to review one coaching cue and carry it into the next session."
    else:
        plan_title = "Adaptive session plan"
        summary = "No syllabus week is active yet, so use a balanced session with footwork, technique, and controlled matchplay."
        warm_up = "Mobility, reaction starts, and split-step activation."
        technical = "Foundational shot quality and movement discipline."
        tactical = "Simple point-construction with strong recovery habits."
        cues = "Stay early to the shuttle and keep the racket prepared."
        homework = "Review the strongest and weakest pattern from today's session."

    blocks = [
        {
            "title": "Opening Brief",
            "duration": "5 min",
            "detail": f"Frame the session around {plan_title.lower()} and set one measurable standard for the group.",
        },
        {
            "title": "Warm-Up Activation",
            "duration": "12 min",
            "detail": warm_up,
        },
        {
            "title": "Technical Block",
            "duration": "22 min",
            "detail": f"{technical} {organization_note}",
        },
        {
            "title": "Tactical Block",
            "duration": "18 min",
            "detail": f"{tactical} {recap_note}",
        },
        {
            "title": "Conditioned Games",
            "duration": "15 min",
            "detail": "Finish with score-based games that force the same tactical theme to appear under pressure.",
        },
        {
            "title": "Debrief And Homework",
            "duration": "8 min",
            "detail": homework,
        },
    ]

    coach_prompts = [
        f"Roster profile: {roster_level_summary}.",
        f"Average recent attendance across the group: {attendance_rate}%.",
        f"Primary coaching cues: {cues}",
    ]
    if unpaid_this_month:
        coach_prompts.append(
            f"Admin/parent finance note: {len(unpaid_this_month)} student(s) still show unpaid this month: {payment_summary}."
        )

    return {
        "plan_title": plan_title,
        "summary": summary,
        "track": track,
        "track_label": dict(WeeklySyllabus.TRACK_CHOICES).get(track, track.title()),
        "resolved_week": resolved_week,
        "roster_size": roster_size,
        "roster_level_summary": roster_level_summary,
        "attendance_rate": attendance_rate,
        "average_score": average_score,
        "payment_summary": payment_summary,
        "payment_count": len(unpaid_this_month),
        "blocks": blocks,
        "coach_prompts": coach_prompts,
        "syllabus_reference": {
            "title": plan_title,
            "objective": syllabus_week.objective if syllabus_week else "",
            "homework": homework,
        },
        "generated_at": timezone.now().strftime("%d %b %Y %H:%M"),
    }
