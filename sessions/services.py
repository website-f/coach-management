import calendar as _calendar
from collections import Counter
from datetime import date, timedelta
from statistics import mean

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from finance.models import Invoice
from members.models import Member
from members.services import calculate_report_overall_score
from sessions.models import (
    AttendanceRecord,
    CoachAvailability,
    SyllabusRoot,
    SyllabusStandard,
    SyllabusTemplate,
    TrainingSession,
    WeeklySyllabus,
)


DEFAULT_BASIC_TEMPLATE = {
    "name": "RSBE Basic Class Curriculum",
    "source_document_name": "Silibus Basic Coaching Badminton.pdf",
    "curriculum_year_label": "Year 1",
    "annual_goal": (
        "Develop players with strong movement basics, racket control, game understanding, "
        "and training discipline as preparation for more structured badminton learning in Year 2."
    ),
    "year_end_outcomes": "\n".join(
        [
            "- Master controlled basic movement skills including footwork, swing, striking, and body balance.",
            "- Handle the racket and shuttle with better coordination and fewer missed contacts.",
            "- Sustain simple cooperative rallies of at least three shots.",
            "- Understand basic badminton rules such as scoring, in or out, and singles or doubles service areas.",
            "- Show discipline, safety awareness, sportsmanship, confidence, and enjoyment during training.",
        ]
    ),
    "assessment_approach": "Formative and continuous assessment throughout the season.",
    "assessment_methods": "\n".join(
        [
            "- Weekly observation",
            "- Practical activity checks",
            "- Mini games",
            "- Individual progress records",
        ]
    ),
    "curriculum_values": "\n".join(
        [
            "- Respect teammates and coaches",
            "- Accept winning and losing well",
            "- Wait for turns",
            "- Take responsibility for equipment",
            "- Play fairly",
        ]
    ),
    "annual_phase_notes": (
        "Annual phase structure follows the PDF headings: Months 1-3 Adaptation, Months 4-6 Control "
        "(with Month 6 mid-year assessment), Months 7-9 Application, and Months 10-12 Readiness "
        "(with Month 12 final assessment). Some phase ranges are inferred from the visible monthly headings."
    ),
    "ai_planner_instructions": (
        "Keep the coaching output playful, highly structured, and beginner-safe. Prioritize movement, "
        "shuttle contact quality, discipline, and simple game understanding before advanced techniques."
    ),
}

DEFAULT_SYLLABUS_ROOT = {
    "name": "Core Academy Syllabus",
    "description": "Default academy-wide syllabus root used when a class-specific syllabus has not been assigned yet.",
    "is_active": True,
    "is_default": True,
}


DEFAULT_TEMPLATE_BY_TRACK = {
    WeeklySyllabus.TRACK_BEGINNER: DEFAULT_BASIC_TEMPLATE,
    WeeklySyllabus.TRACK_INTERMEDIATE: {
        "name": "NYO Intermediate Development Framework",
        "source_document_name": "Internal NYO coaching progression",
        "curriculum_year_label": "Year 2",
        "annual_goal": "Turn stable fundamentals into consistent rally control, cleaner transitions, and smarter tactical choices.",
        "year_end_outcomes": "\n".join(
            [
                "- Move efficiently through six-point court patterns with reliable recovery.",
                "- Produce more consistent clears, drops, drives, and defensive choices under pressure.",
                "- Link the first three shots with a clear intention in training games.",
                "- Follow training routines, recovery habits, and tactical instructions with less prompting.",
            ]
        ),
        "assessment_approach": "Blend weekly observation with drill quality and conditioned matchplay review.",
        "assessment_methods": "\n".join(
            [
                "- Coach observation in technical stations",
                "- Conditioned matchplay scoring",
                "- Reflection review after sessions",
                "- Progress report snapshots",
            ]
        ),
        "curriculum_values": "\n".join(
            [
                "- Discipline in repetition quality",
                "- Respect for structure and feedback",
                "- Communication during drills and games",
                "- Accountability for effort",
            ]
        ),
        "annual_phase_notes": "Use progressive blocks of tempo control, attack preparation, defense-to-attack transitions, and match discipline.",
        "ai_planner_instructions": "Keep sessions structured, measurable, and pattern-based. Push consistency before complexity.",
    },
    WeeklySyllabus.TRACK_ADVANCED: {
        "name": "NYO Advanced Performance Framework",
        "source_document_name": "Internal NYO performance pathway",
        "curriculum_year_label": "Year 3",
        "annual_goal": "Sharpen advanced players into tactically disciplined performers with faster transitions and stronger pressure management.",
        "year_end_outcomes": "\n".join(
            [
                "- Maintain high-quality rear-court and forecourt sequences at training pace.",
                "- Recover faster after attacking or defending under pressure.",
                "- Use tactical patterns intentionally instead of reacting late in rallies.",
                "- Handle score pressure with routine, clarity, and self-control.",
            ]
        ),
        "assessment_approach": "Review performance in high-intensity drills, tactical scenarios, and competition-style sessions.",
        "assessment_methods": "\n".join(
            [
                "- Matchplay trend review",
                "- Drill quality scoring",
                "- Coach tactical observation",
                "- Progress report comparison",
            ]
        ),
        "curriculum_values": "\n".join(
            [
                "- Competitive discipline",
                "- Intentional decision-making",
                "- Efficient recovery habits",
                "- Respect for process under pressure",
            ]
        ),
        "annual_phase_notes": "Move players from quality build-up into pressure execution, adaptation, and disciplined close-out habits.",
        "ai_planner_instructions": "Keep output compact, specific, and performance-oriented. Use tactical clarity and recovery quality as recurring anchors.",
    },
    WeeklySyllabus.TRACK_PRO: {
        "name": "NYO Pro Competition Framework",
        "source_document_name": "Internal NYO high-performance pathway",
        "curriculum_year_label": "Elite Cycle",
        "annual_goal": "Prepare competition players to execute scouting-based plans, absorb elite pressure, and adapt quickly inside match conditions.",
        "year_end_outcomes": "\n".join(
            [
                "- Execute first-three-shot plans linked to opponent patterns.",
                "- Control rally tempo and disguise without losing recovery quality.",
                "- Counter elite pace with compact defense and fast transitions.",
                "- Adapt tactical plans quickly when the original pattern fails.",
            ]
        ),
        "assessment_approach": "Assess through competition simulations, pressure sets, scouting adaptation, and post-session debriefs.",
        "assessment_methods": "\n".join(
            [
                "- Pressure match simulation",
                "- Tactical adaptation review",
                "- Video debrief",
                "- Competitive trend tracking",
            ]
        ),
        "curriculum_values": "\n".join(
            [
                "- Competitive ownership",
                "- Tactical discipline",
                "- Emotional control",
                "- Respect for scouting and review process",
            ]
        ),
        "annual_phase_notes": "Cycle players through scouting preparation, tempo traps, pressure resistance, and tournament-readiness simulation.",
        "ai_planner_instructions": "Answer like a high-performance assistant: brief, exact, and aligned to competitive intent.",
    },
}


DEFAULT_STANDARDS_BY_TRACK = {
    WeeklySyllabus.TRACK_BEGINNER: [
        {
            "sort_order": 1,
            "code": "SK1",
            "title": "Kecekapan Pergerakan Asas",
            "focus": "Membina asas koordinasi, imbangan, dan kawalan badan.",
            "learning_standard_items": "\n".join(
                [
                    "1.1 Mengawal imbangan badan semasa bergerak dan berhenti",
                    "1.2 Bergerak dalam pelbagai arah dengan koordinasi",
                    "1.3 Menukar arah pergerakan dengan stabil",
                    "1.4 Mengawal kelajuan dan ruang pergerakan",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Pergerakan tidak terkawal",
                    "2 - Bergerak dengan banyak bantuan",
                    "3 - Pergerakan asas memuaskan",
                    "4 - Pergerakan terkawal dan seimbang",
                    "5 - Pergerakan lancar dan yakin",
                ]
            ),
            "coach_hints": "Stay low, balance before speed, and recover to a stable base after each movement pattern.",
            "assessment_focus": "Observe balance, directional control, and stable stopping mechanics.",
        },
        {
            "sort_order": 2,
            "code": "SK2",
            "title": "Kawalan Raket dan Shuttle",
            "focus": "Membina sentuhan, rasa, dan kawalan sebelum teknik formal.",
            "learning_standard_items": "\n".join(
                [
                    "2.1 Memegang raket menggunakan pegangan asas",
                    "2.2 Membuat sentuhan shuttle secara terkawal",
                    "2.3 Mengawal arah pukulan pada jarak dekat",
                    "2.4 Mengekalkan rally mudah secara berpasangan",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Tidak dapat mengawal shuttle",
                    "2 - Sentuhan tidak konsisten",
                    "3 - Kawalan minimum",
                    "4 - Kawalan asas stabil",
                    "5 - Rally pendek konsisten",
                ]
            ),
            "coach_hints": "Prioritize clean contact and relaxed grip pressure before power or speed.",
            "assessment_focus": "Check grip basics, control at close range, and short cooperative rallies.",
        },
        {
            "sort_order": 3,
            "code": "SK3",
            "title": "Pembentukan Disiplin dan Struktur Latihan",
            "focus": "Membina tingkah laku atlet sejak awal.",
            "learning_standard_items": "\n".join(
                [
                    "3.1 Mengamalkan posisi bersedia",
                    "3.2 Kembali ke posisi asas selepas pukulan",
                    "3.3 Mengikut arahan latihan dengan tertib",
                    "3.4 Mengamalkan keselamatan semasa aktiviti",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Tidak memahami rutin",
                    "2 - Perlu diingatkan selalu",
                    "3 - Mengikut arahan asas",
                    "4 - Mengamalkan rutin latihan",
                    "5 - Menunjukkan disiplin baik",
                ]
            ),
            "coach_hints": "Reinforce ready position, recovery habits, listening, and safe spacing every session.",
            "assessment_focus": "Track routine discipline, recovery position, and safety habits.",
        },
        {
            "sort_order": 4,
            "code": "SK4",
            "title": "Pengetahuan Asas Permainan",
            "focus": "Membina kefahaman struktur permainan secara berperingkat.",
            "learning_standard_items": "\n".join(
                [
                    "4.1 Mengenal kawasan gelanggang",
                    "4.2 Membezakan shuttle masuk dan keluar",
                    "4.3 Memahami kiraan mata asas",
                    "4.4 Mengetahui kedudukan servis perseorangan",
                    "4.5 Mengenal perbezaan permainan single dan double",
                    "4.6 Mengamalkan giliran servis dalam permainan mudah",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Tidak memahami permainan",
                    "2 - Mengenal sebahagian elemen",
                    "3 - Faham konsep asas",
                    "4 - Mengaplikasi dengan betul",
                    "5 - Memahami aliran permainan sepenuhnya",
                ]
            ),
            "coach_hints": "Explain one simple game rule at a time and connect it immediately to a mini game or live example.",
            "assessment_focus": "Assess simple game understanding, court awareness, and service rotation basics.",
        },
    ],
    WeeklySyllabus.TRACK_INTERMEDIATE: [
        {
            "sort_order": 1,
            "code": "SK1",
            "title": "Movement Efficiency",
            "focus": "Build quicker recovery, stronger court coverage, and better change of direction.",
            "learning_standard_items": "\n".join(
                [
                    "Move through six-point patterns with consistent balance",
                    "Recover to base with better timing after each shot",
                    "Link front-back and side-to-side movement efficiently",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Movement breaks down quickly under pressure",
                    "2 - Needs frequent reminders to recover correctly",
                    "3 - Can complete patterns with moderate consistency",
                    "4 - Recovers and rebalances well in most drills",
                    "5 - Moves with efficient rhythm and match-ready recovery",
                ]
            ),
            "coach_hints": "Train recovery quality and decision speed together instead of separately.",
            "assessment_focus": "Evaluate movement economy and how quickly the player resets for the next shot.",
        },
        {
            "sort_order": 2,
            "code": "SK2",
            "title": "Shot Consistency and Setup Quality",
            "focus": "Create more stable attacking and defensive setups through cleaner shot execution.",
            "learning_standard_items": "\n".join(
                [
                    "Maintain clearer shot intention on clears, drops, drives, and blocks",
                    "Prepare attacks with better setup quality",
                    "Defend with more compact racket preparation",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Shot quality breaks under simple movement",
                    "2 - Execution is unstable without coach-fed rhythm",
                    "3 - Can maintain quality in short controlled drills",
                    "4 - Applies stable shot quality under moderate pressure",
                    "5 - Produces reliable setup shots across varied drills",
                ]
            ),
            "coach_hints": "Use intent language: build, pressure, neutralize, or reset.",
            "assessment_focus": "Check quality of the setup shot, not just the finishing shot.",
        },
        {
            "sort_order": 3,
            "code": "SK3",
            "title": "Training Discipline and Tactical Habits",
            "focus": "Strengthen drill focus, listening, and tactical discipline inside routines.",
            "learning_standard_items": "\n".join(
                [
                    "Follow drill rules and tactical constraints consistently",
                    "Recover to the correct shape after each exchange",
                    "Respond to coach adjustments without losing structure",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Loses structure and focus quickly",
                    "2 - Needs repeated intervention to keep drill discipline",
                    "3 - Follows most routines with occasional lapses",
                    "4 - Maintains discipline and applies tactical instructions well",
                    "5 - Shows strong ownership of routine and structure",
                ]
            ),
            "coach_hints": "Name the tactical rule before the rally and review it immediately after.",
            "assessment_focus": "Observe routine discipline and responsiveness to tactical corrections.",
        },
        {
            "sort_order": 4,
            "code": "SK4",
            "title": "Game Application",
            "focus": "Apply patterns intentionally in conditioned matchplay.",
            "learning_standard_items": "\n".join(
                [
                    "Link first-three-shot ideas with clear intention",
                    "Use tempo changes more intentionally",
                    "Make simpler decisions under score pressure",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Cannot apply the drill concept in games",
                    "2 - Applies the idea only with heavy prompting",
                    "3 - Shows partial transfer into games",
                    "4 - Applies the pattern in most conditioned points",
                    "5 - Transfers the concept clearly into matchplay",
                ]
            ),
            "coach_hints": "Keep games constrained enough for the intended pattern to appear repeatedly.",
            "assessment_focus": "Check whether the session theme survives under scoring pressure.",
        },
    ],
    WeeklySyllabus.TRACK_ADVANCED: [
        {
            "sort_order": 1,
            "code": "SK1",
            "title": "Explosive Movement and Recovery",
            "focus": "Sharpen explosive starts, rear-court recovery, and transition speed.",
            "learning_standard_items": "\n".join(
                [
                    "Explode into the first movement with balance",
                    "Recover quickly after full overhead actions",
                    "Maintain lower-body structure under pressure",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Movement quality fades quickly at pace",
                    "2 - Recovery is late or unstable",
                    "3 - Can sustain advanced movement in short blocks",
                    "4 - Maintains quality through most high-speed drills",
                    "5 - Recovers explosively and consistently at advanced pace",
                ]
            ),
            "coach_hints": "The recovery step matters as much as the attacking step.",
            "assessment_focus": "Observe recovery timing after high-intensity actions.",
        },
        {
            "sort_order": 2,
            "code": "SK2",
            "title": "Shot Quality Under Pressure",
            "focus": "Protect angle, disguise, and control when the pace rises.",
            "learning_standard_items": "\n".join(
                [
                    "Maintain steep attack quality with balance",
                    "Use controlled deception without sacrificing recovery",
                    "Defend and counter with compact mechanics",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Shot quality collapses under pressure",
                    "2 - Quality appears only in isolated reps",
                    "3 - Can hold quality in controlled sequences",
                    "4 - Delivers strong quality in most advanced drills",
                    "5 - Maintains high-quality execution under pressure and variation",
                ]
            ),
            "coach_hints": "Do not trade structure for flash.",
            "assessment_focus": "Evaluate whether the player keeps quality when the rally accelerates.",
        },
        {
            "sort_order": 3,
            "code": "SK3",
            "title": "Tactical Pattern Discipline",
            "focus": "Use tactical patterns intentionally through the middle of the rally.",
            "learning_standard_items": "\n".join(
                [
                    "Follow the planned attacking or defensive pattern",
                    "Recognize when to change pace or reset",
                    "Transition between phases of the rally with intent",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Tactical choices are unclear or reactive",
                    "2 - Understands the pattern but loses it quickly",
                    "3 - Applies the pattern in shorter exchanges",
                    "4 - Keeps the pattern through most constrained games",
                    "5 - Executes patterns clearly even in pressure sequences",
                ]
            ),
            "coach_hints": "Call the tactical lane before the rally begins.",
            "assessment_focus": "Check pattern retention and tactical intent under score constraints.",
        },
        {
            "sort_order": 4,
            "code": "SK4",
            "title": "Pressure Execution",
            "focus": "Stay disciplined at the end of games and during score pressure.",
            "learning_standard_items": "\n".join(
                [
                    "Reset quickly between pressure rallies",
                    "Choose high-percentage options in close scores",
                    "Stay emotionally stable after mistakes",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Pressure causes rushed or unclear choices",
                    "2 - Needs frequent intervention to reset",
                    "3 - Handles pressure inconsistently",
                    "4 - Maintains reasonable clarity in most pressure games",
                    "5 - Shows calm, disciplined execution in close-score play",
                ]
            ),
            "coach_hints": "Protect routine and breathing between rallies.",
            "assessment_focus": "Observe choices and emotional control in pressure games.",
        },
    ],
    WeeklySyllabus.TRACK_PRO: [
        {
            "sort_order": 1,
            "code": "SK1",
            "title": "Scouting-Led Preparation",
            "focus": "Build session plans from opponent patterns and opening-shot priorities.",
            "learning_standard_items": "\n".join(
                [
                    "Identify likely return lanes and opening patterns",
                    "Prepare multiple first-three-shot options",
                    "Use scouting notes during competitive rehearsal",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Cannot connect scouting to training choices",
                    "2 - Uses scouting ideas only with prompting",
                    "3 - Applies one clear plan in training sets",
                    "4 - Adapts scouting ideas across multiple scenarios",
                    "5 - Uses scouting details naturally in competitive rehearsal",
                ]
            ),
            "coach_hints": "Link every opening pattern to a clear opponent cue.",
            "assessment_focus": "Evaluate how clearly the player uses scouting information.",
        },
        {
            "sort_order": 2,
            "code": "SK2",
            "title": "Tempo Control and Transition Steals",
            "focus": "Manipulate pace and hunt transition opportunities at elite speed.",
            "learning_standard_items": "\n".join(
                [
                    "Use deliberate pace changes to create openings",
                    "Intercept earlier after setup shots",
                    "Reset quickly after fast exchanges",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Tempo changes are late or ineffective",
                    "2 - Can create openings only in simple patterns",
                    "3 - Shows partial control in advanced drills",
                    "4 - Uses tempo with strong intent in most scenarios",
                    "5 - Creates and converts transition chances consistently",
                ]
            ),
            "coach_hints": "One slower setup ball should lead into one faster interception window.",
            "assessment_focus": "Look for intentional tempo shifts and fast follow-up movement.",
        },
        {
            "sort_order": 3,
            "code": "SK3",
            "title": "Elite Pressure Resistance",
            "focus": "Absorb pressure with compact mechanics and efficient recovery.",
            "learning_standard_items": "\n".join(
                [
                    "Keep compact defensive shape under elite pace",
                    "Recover before admiring the shot",
                    "Counter through the open lane when pressure breaks",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Breaks structure under sustained pace",
                    "2 - Counters too late or recovers too slowly",
                    "3 - Can resist in shorter bursts",
                    "4 - Holds shape and recovery through most pressure blocks",
                    "5 - Absorbs pressure and counters with elite discipline",
                ]
            ),
            "coach_hints": "Do less, earlier, and with better timing.",
            "assessment_focus": "Judge compactness, recovery economy, and timing of the counter response.",
        },
        {
            "sort_order": 4,
            "code": "SK4",
            "title": "Competition Adaptation",
            "focus": "Recognize match trends and pivot quickly when the original plan stalls.",
            "learning_standard_items": "\n".join(
                [
                    "Identify match trends early",
                    "Switch to backup patterns with clarity",
                    "Protect discipline point by point after tactical changes",
                ]
            ),
            "performance_band_items": "\n".join(
                [
                    "1 - Cannot adjust when the plan breaks down",
                    "2 - Needs heavy coach direction to adapt",
                    "3 - Can make one useful adaptation",
                    "4 - Adjusts well in most competition simulations",
                    "5 - Adapts quickly and keeps discipline through the change",
                ]
            ),
            "coach_hints": "Name the trend, call the adjustment, then execute the next rally cleanly.",
            "assessment_focus": "Track the speed and quality of tactical adaptation.",
        },
    ],
}


@transaction.atomic
def ensure_default_syllabus():
    default_root, _ = SyllabusRoot.objects.get_or_create(code="core_academy_syllabus", defaults=DEFAULT_SYLLABUS_ROOT)
    if not default_root.is_default:
        default_root.is_default = True
        default_root.save(update_fields=["is_default", "updated_at"])
    template_map = {}
    for track, template_defaults in DEFAULT_TEMPLATE_BY_TRACK.items():
        template, _ = SyllabusTemplate.objects.get_or_create(root=default_root, track=track, defaults=template_defaults)
        template_map[track] = template

        standard_map = {item.code: item for item in template.standards.all()}
        for standard_row in DEFAULT_STANDARDS_BY_TRACK.get(track, []):
            standard, _ = SyllabusStandard.objects.get_or_create(
                template=template,
                code=standard_row["code"],
                defaults=standard_row,
            )
            standard_map[standard.code] = standard

        for row in DEFAULT_SYLLABUS_BLUEPRINT.get(track, []):
            defaults = row.copy()
            standard_code = defaults.pop("standard_code", "")
            defaults["root"] = default_root
            defaults["template"] = template
            defaults["standard"] = standard_map.get(standard_code)
            syllabus_week, created = WeeklySyllabus.objects.get_or_create(
                root=default_root,
                track=track,
                week_number=row["week_number"],
                defaults=defaults,
            )
            if not created:
                updated_fields = []
                if not syllabus_week.root_id:
                    syllabus_week.root = default_root
                    updated_fields.append("root")
                if not syllabus_week.template_id:
                    syllabus_week.template = template
                    updated_fields.append("template")
                if standard_code and not syllabus_week.standard_id and standard_map.get(standard_code):
                    syllabus_week.standard = standard_map[standard_code]
                    updated_fields.append("standard")
                for field_name in ["month_number", "phase_name", "assessment_focus", "success_criteria", "coach_notes"]:
                    if not getattr(syllabus_week, field_name) and defaults.get(field_name):
                        setattr(syllabus_week, field_name, defaults[field_name])
                        updated_fields.append(field_name)
                if updated_fields:
                    syllabus_week.save(update_fields=updated_fields)


def get_active_syllabus_template(track, syllabus_root=None):
    ensure_default_syllabus()
    syllabus_root = syllabus_root or SyllabusRoot.get_default()
    queryset = SyllabusTemplate.objects.filter(track=track)
    if syllabus_root:
        queryset = queryset.filter(Q(root=syllabus_root) | Q(root__isnull=True))
    return queryset.filter(is_active=True).first() or queryset.first()


def resolve_syllabus_root(training_session, roster):
    ensure_default_syllabus()
    if training_session.syllabus_root_id:
        return training_session.syllabus_root
    root_ids = [member.syllabus_root_id for member in roster if member.syllabus_root_id]
    if root_ids:
        dominant_root_id = Counter(root_ids).most_common(1)[0][0]
        return SyllabusRoot.objects.filter(pk=dominant_root_id).first() or SyllabusRoot.get_default()
    return SyllabusRoot.get_default()


def determine_session_track(training_session):
    roster = list(
        Member.objects.filter(attendance_records__training_session=training_session)
        .select_related("assigned_coach", "assigned_staff", "parent_user", "payment_plan", "syllabus_root")
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


def resolve_syllabus_week(training_session, roster, track, syllabus_root=None):
    ensure_default_syllabus()
    syllabus_root = syllabus_root or resolve_syllabus_root(training_session, roster)
    weeks = list(
        WeeklySyllabus.objects.filter(track=track, is_active=True)
        .filter(Q(root=syllabus_root) | Q(root__isnull=True))
        .select_related("template", "standard")
        .order_by("week_number")
    )
    if not weeks:
        return None, 1

    joined_dates = [member.joined_at for member in roster if member.joined_at]
    reference_date = min(joined_dates) if joined_dates else training_session.session_date.replace(day=1)
    elapsed_days = max(0, (training_session.session_date - reference_date).days)
    program_week = (elapsed_days // 7) + 1
    resolved_week = ((program_week - 1) % len(weeks)) + 1
    syllabus_week = next((item for item in weeks if item.week_number == resolved_week), weeks[0])
    return syllabus_week, resolved_week


def build_template_reference(template):
    if not template:
        return {
            "name": "",
            "curriculum_year_label": "",
            "source_document_name": "",
            "annual_goal": "",
            "year_end_outcomes": [],
            "assessment_approach": "",
            "assessment_methods": [],
            "curriculum_values": [],
            "annual_phase_notes": "",
            "ai_planner_instructions": "",
        }
    return {
        "name": template.name,
        "curriculum_year_label": template.curriculum_year_label,
        "source_document_name": template.source_document_name,
        "annual_goal": template.annual_goal,
        "year_end_outcomes": template.year_end_outcome_list,
        "assessment_approach": template.assessment_approach,
        "assessment_methods": template.assessment_method_list,
        "curriculum_values": [item.strip("- ").strip() for item in (template.curriculum_values or "").splitlines() if item.strip()],
        "annual_phase_notes": template.annual_phase_notes,
        "ai_planner_instructions": template.ai_planner_instructions,
    }


def build_standard_reference(standard):
    if not standard:
        return {
            "code": "",
            "title": "",
            "focus": "",
            "learning_standards": [],
            "performance_bands": [],
            "coach_hints": "",
            "assessment_focus": "",
        }
    return {
        "code": standard.code,
        "title": standard.title,
        "focus": standard.focus,
        "learning_standards": standard.learning_standard_list,
        "performance_bands": standard.performance_band_list,
        "coach_hints": standard.coach_hints,
        "assessment_focus": standard.assessment_focus,
    }


def build_session_plan(training_session):
    track, roster, average_score = determine_session_track(training_session)
    syllabus_root = resolve_syllabus_root(training_session, roster)
    syllabus_week, resolved_week = resolve_syllabus_week(training_session, roster, track, syllabus_root=syllabus_root)
    template = (
        syllabus_week.template
        if syllabus_week and syllabus_week.template_id
        else get_active_syllabus_template(track, syllabus_root=syllabus_root)
    )
    standard = syllabus_week.standard if syllabus_week and syllabus_week.standard_id else None

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

    template_reference = build_template_reference(template)
    standard_reference = build_standard_reference(standard)

    if syllabus_week:
        phase_detail = syllabus_week.phase_label or "Current syllabus phase"
        plan_title = f"{syllabus_week.get_track_display()} Week {resolved_week}: {syllabus_week.title}"
        standard_text = f"{standard_reference['code']} {standard_reference['title']}".strip()
        summary = (
            f"This session should lean into {syllabus_week.title.lower()} for a {group_profile} roster. "
            f"The syllabus target is to {syllabus_week.objective.lower()}"
        )
        if standard_text:
            summary += f" while staying aligned to curriculum standard {standard_text}."
        warm_up = syllabus_week.warm_up_plan
        technical = syllabus_week.technical_focus
        tactical = syllabus_week.tactical_focus
        cues = syllabus_week.coaching_cues
        assessment_focus = syllabus_week.assessment_focus or standard_reference["assessment_focus"]
        success_criteria = syllabus_week.success_criteria or "Players should show visible progress against the session objective."
        coach_notes = syllabus_week.coach_notes
        homework = syllabus_week.homework or "Ask players to review one coaching cue and carry it into the next session."
    else:
        phase_detail = ""
        plan_title = "Adaptive session plan"
        summary = "No syllabus week is active yet, so use a balanced session with footwork, technique, and controlled matchplay."
        warm_up = "Mobility, reaction starts, and split-step activation."
        technical = "Foundational shot quality and movement discipline."
        tactical = "Simple point-construction with strong recovery habits."
        cues = "Stay early to the shuttle and keep the racket prepared."
        assessment_focus = "Observe technical quality, structure, and movement discipline."
        success_criteria = "Players should finish the session with a clearer repeatable pattern than they started with."
        coach_notes = ""
        homework = "Review the strongest and weakest pattern from today's session."

    blocks = [
        {
            "title": "Opening Brief",
            "duration": "5 min",
            "detail": f"Frame the session around {plan_title.lower()}, the {phase_detail.lower() if phase_detail else 'current syllabus'} direction, and one measurable standard for the group.",
        },
        {"title": "Warm-Up Activation", "duration": "12 min", "detail": warm_up},
        {"title": "Technical Block", "duration": "22 min", "detail": f"{technical} {organization_note}"},
        {"title": "Tactical Block", "duration": "18 min", "detail": f"{tactical} {recap_note}"},
        {
            "title": "Conditioned Games",
            "duration": "15 min",
            "detail": "Finish with score-based games that force the same tactical theme to appear under pressure.",
        },
        {
            "title": "Debrief, Assessment, And Homework",
            "duration": "8 min",
            "detail": f"Assessment focus: {assessment_focus} Success criteria: {success_criteria} Homework: {homework}",
        },
    ]

    coach_prompts = [
        f"Roster profile: {roster_level_summary}.",
        f"Average recent attendance across the group: {attendance_rate}%.",
        f"Primary coaching cues: {cues}",
    ]
    if phase_detail:
        coach_prompts.append(f"Current phase anchor: {phase_detail}.")
    if standard_reference["code"]:
        coach_prompts.append(f"Curriculum standard: {standard_reference['code']} - {standard_reference['title']}.")
    if coach_notes:
        coach_prompts.append(f"Admin coach note: {coach_notes}")
    if unpaid_this_month:
        coach_prompts.append(
            f"Admin/parent finance note: {len(unpaid_this_month)} student(s) still show unpaid this month: {payment_summary}."
        )

    return {
        "plan_title": plan_title,
        "summary": summary,
        "track": track,
        "track_label": dict(WeeklySyllabus.TRACK_CHOICES).get(track, track.title()),
        "syllabus_root_name": syllabus_root.name if syllabus_root else "",
        "resolved_week": resolved_week,
        "phase_label": phase_detail,
        "roster_size": roster_size,
        "roster_level_summary": roster_level_summary,
        "attendance_rate": attendance_rate,
        "average_score": average_score,
        "payment_summary": payment_summary,
        "payment_count": len(unpaid_this_month),
        "blocks": blocks,
        "coach_prompts": coach_prompts,
        "template_reference": template_reference,
        "standard_reference": standard_reference,
        "syllabus_reference": {
            "title": plan_title,
            "objective": syllabus_week.objective if syllabus_week else "",
            "phase_label": phase_detail,
            "assessment_focus": assessment_focus,
            "success_criteria": success_criteria,
            "homework": homework,
        },
        "generated_at": timezone.now().strftime("%d %b %Y %H:%M"),
    }


LEVEL_TRACK_MAP = {
    Member.LEVEL_BASIC: WeeklySyllabus.TRACK_BEGINNER,
    Member.LEVEL_INTERMEDIATE: WeeklySyllabus.TRACK_INTERMEDIATE,
    Member.LEVEL_ADVANCED: WeeklySyllabus.TRACK_ADVANCED,
}


DEFAULT_SYLLABUS_BLUEPRINT = {
    WeeklySyllabus.TRACK_BEGINNER: [
        {
            "month_number": 1,
            "phase_name": "Fasa Adaptasi",
            "week_number": 1,
            "standard_code": "SK1",
            "title": "Grip, ready stance, and court movement basics",
            "objective": "Build safe racket handling, split-step timing, and confidence moving to the shuttle.",
            "warm_up_plan": "Light jog, line hops, shadow split-step, and racket-grip activation for both forehand and backhand.",
            "technical_focus": "Grip switching, ready position, basic forehand serve, and underhand lift repetitions with coach feeding.",
            "tactical_focus": "Teach where to recover after each shot and how to keep rallies alive instead of chasing winners too early.",
            "coaching_cues": "Stay low, land softly after the split step, and reset the racket in front after every contact.",
            "assessment_focus": "Observe balance, ready stance discipline, and basic movement control.",
            "success_criteria": "Players can recover to base and move into simple forecourt or midcourt feeds with less imbalance.",
            "coach_notes": "Keep the language simple and fun because this sits in the adaptation phase of the PDF structure.",
            "homework": "Two home blocks of shadow footwork and 20 controlled serve reps.",
        },
        {
            "month_number": 1,
            "phase_name": "Fasa Adaptasi",
            "week_number": 2,
            "standard_code": "SK2",
            "title": "Serve consistency and lift control",
            "objective": "Improve the ability to start points cleanly and move the shuttle high to a safe target.",
            "warm_up_plan": "Dynamic ankle and hip mobility, fast-feet ladder, then partner toss-and-catch to build rhythm.",
            "technical_focus": "Short serve mechanics, underhand lift height, and forecourt net pickup with simple multi-shuttle feeds.",
            "tactical_focus": "Introduce the idea of using height and depth to recover time instead of rushing flat exchanges.",
            "coaching_cues": "Relax the grip before contact, send the shuttle high enough, and recover to center after every lift.",
            "assessment_focus": "Check grip basics, contact consistency, and shuttle direction at close range.",
            "success_criteria": "Players can produce cleaner serves and lifts with fewer mishits in simple feeding drills.",
            "coach_notes": "Keep feeds cooperative and avoid overloading the group with too many rules at once.",
            "homework": "Record 10 short serves and self-check stance width and follow-through.",
        },
        {
            "month_number": 2,
            "phase_name": "Fasa Adaptasi",
            "week_number": 3,
            "standard_code": "SK2",
            "title": "Overhead basics and clear rhythm",
            "objective": "Create a repeatable overhead movement pattern for clear and high defensive contact.",
            "warm_up_plan": "Shoulder activation, trunk rotation, shadow chasse steps, and overhead throwing pattern rehearsal.",
            "technical_focus": "Preparation for overhead contact, throwing action, full clear technique, and simple rear-court footwork.",
            "tactical_focus": "Understand when to clear high to escape pressure and reset the rally.",
            "coaching_cues": "Turn early, get behind the shuttle, and finish balanced so the next movement starts immediately.",
            "assessment_focus": "Watch preparation timing, contact height, and balance after the overhead action.",
            "success_criteria": "Players can reach better overhead preparation positions and send more shuttles high and deep.",
            "coach_notes": "Use lots of shadow rehearsal before asking for full live clears.",
            "homework": "Mirror shadow overhead preparation for 5 minutes on two separate days.",
        },
        {
            "month_number": 2,
            "phase_name": "Fasa Adaptasi",
            "week_number": 4,
            "standard_code": "SK4",
            "title": "Net touch and rally building",
            "objective": "Help players move smoothly from lift-clear patterns into soft net control and longer rallies.",
            "warm_up_plan": "Reaction tags, front-court lunges, and fingertip control drills with shuttle taps over the net.",
            "technical_focus": "Net brush, simple tumble introduction, forecourt lunge recovery, and front-back transition feeds.",
            "tactical_focus": "Show how net quality can force the opponent to lift and create a safer attacking opportunity later.",
            "coaching_cues": "Arrive early at the net, soften the hand on contact, and push back out after the lunge.",
            "assessment_focus": "Look for rally cooperation, simple rule understanding, and front-court control.",
            "success_criteria": "Players can sustain short rallies more often and understand why a good net shot creates the next chance.",
            "coach_notes": "Blend in mini-games so the game-understanding standard from the PDF stays visible.",
            "homework": "3 rounds of lunge balance holds plus service-line net taps.",
        },
    ],
    WeeklySyllabus.TRACK_INTERMEDIATE: [
        {
            "month_number": 1,
            "phase_name": "Development Block 1",
            "week_number": 1,
            "standard_code": "SK1",
            "title": "Tempo control and front-back patterns",
            "objective": "Control rally rhythm through front-back movement and cleaner shot selection.",
            "warm_up_plan": "Band activation, split-step reaction calls, and shadow six-point movement with tempo changes.",
            "technical_focus": "Drive lift transition, front-back footwork, and tighter block-to-net control under movement.",
            "tactical_focus": "Teach when to slow the rally with net control and when to speed it up with flat pressure.",
            "coaching_cues": "Read early, keep the base alive, and choose one clear intention before each shot.",
            "assessment_focus": "Check movement economy and whether players recover with clearer rhythm.",
            "success_criteria": "Players manage tempo better and link front-back movement with more control.",
            "coach_notes": "Keep rallies structured enough for tempo decisions to be visible.",
            "homework": "Shadow six-point movement with a metronome or count for 8 minutes.",
        },
        {
            "month_number": 1,
            "phase_name": "Development Block 1",
            "week_number": 2,
            "standard_code": "SK2",
            "title": "Attack preparation and midcourt pressure",
            "objective": "Create better attacking chances by improving setup shots, balance, and first follow-up movement.",
            "warm_up_plan": "Medicine-ball rotation, chasse-to-lunge repeats, and reaction starts from a neutral base.",
            "technical_focus": "Attacking clear, drop-to-net sequence, and midcourt interception drills with coach variation.",
            "tactical_focus": "Use the first attacking shot to move the opponent, then hunt the weaker reply instead of forcing winners instantly.",
            "coaching_cues": "Attack with balance, keep the non-racket arm active, and move through the follow-up step.",
            "assessment_focus": "Look at the quality of the setup shot and first follow-up step.",
            "success_criteria": "Players build attacks with more balance and better midcourt anticipation.",
            "coach_notes": "Coach the follow-up movement as strongly as the attacking shot itself.",
            "homework": "Review one training clip and note two moments where the follow-up step was late.",
        },
        {
            "month_number": 2,
            "phase_name": "Development Block 2",
            "week_number": 3,
            "standard_code": "SK3",
            "title": "Defensive transitions under pressure",
            "objective": "Recover from smashes and flat attacks with better racket position and transition choices.",
            "warm_up_plan": "Elastic-band defense stance work, mirror reactions, and low-center shuffle patterns.",
            "technical_focus": "Smash defense, block lift choice, counter-drive timing, and partner pressure sequences.",
            "tactical_focus": "Recognize when to neutralize, when to counter, and when to lift to safer zones.",
            "coaching_cues": "Stay compact, racket up before the shuttle crosses, and recover immediately after the first defense.",
            "assessment_focus": "Assess routine discipline inside defense drills and whether choices stay controlled.",
            "success_criteria": "Players defend with less panic and move into better second actions.",
            "coach_notes": "Use repeated short sequences so the group can feel the transition rhythm.",
            "homework": "Do 3 rounds of low defense hold and 20 counter-drive shadow contacts.",
        },
        {
            "month_number": 2,
            "phase_name": "Development Block 2",
            "week_number": 4,
            "standard_code": "SK4",
            "title": "Conditioned matchplay and pattern discipline",
            "objective": "Apply weekly themes inside match conditions without losing movement or tactical discipline.",
            "warm_up_plan": "Competitive footwork relay, shadow pattern rehearsal, and short controlled rally start-ups.",
            "technical_focus": "Pattern-based games: clear-drop-net, serve-third-ball, and defense-to-counter transitions.",
            "tactical_focus": "Link the first three shots into a clear plan and keep the rally pattern intentional under score pressure.",
            "coaching_cues": "Call the pattern before the rally, review decisions after the rally, and protect quality over speed.",
            "assessment_focus": "Judge whether the training idea transfers into constrained games.",
            "success_criteria": "Players apply the intended pattern more often during scored exchanges.",
            "coach_notes": "Keep game rules tight enough that the target pattern appears repeatedly.",
            "homework": "Journal one pattern that worked and one that broke down during conditioned games.",
        },
    ],
}


LEVEL_ORDER = [
    Member.LEVEL_BASIC,
    Member.LEVEL_INTERMEDIATE,
    Member.LEVEL_ADVANCED,
]


def _month_bounds(anchor: date):
    start = anchor.replace(day=1)
    _, days = _calendar.monthrange(start.year, start.month)
    return start, start.replace(day=days)


def _eligible_availabilities(member):
    queryset = CoachAvailability.objects.filter(is_active=True).select_related("coach")
    if member.assigned_coach_id:
        queryset = queryset.filter(coach=member.assigned_coach)
    return list(
        queryset.filter(Q(level=member.skill_level) | Q(level="any")).order_by(
            "weekday", "start_time"
        )
    )


def _slot_has_conflict(existing_sessions_by_date, candidate_date, slot):
    for existing in existing_sessions_by_date.get(candidate_date, []):
        if existing.court and slot.court and existing.court != slot.court:
            if existing.start_time < slot.end_time and slot.start_time < existing.end_time:
                if existing.coach_id == slot.coach_id:
                    return True
                continue
            continue
        if existing.coach_id != slot.coach_id:
            continue
        if existing.start_time < slot.end_time and slot.start_time < existing.end_time:
            return True
    return False


def _member_has_clash(member_schedule, candidate_date, slot):
    for existing in member_schedule.get(candidate_date, []):
        if existing.start_time < slot.end_time and slot.start_time < existing.end_time:
            return True
    return False


@transaction.atomic
def expire_trial_if_needed(member):
    """If a trial member has hit the lifetime trial_session_limit on
    counted attendance, flip them to INACTIVE. Returns True if flipped.
    """
    from finance.models import BillingConfiguration

    if member.status != Member.STATUS_TRIAL:
        return False
    limit = BillingConfiguration.get_solo().trial_session_limit or 1
    counted = member.attendance_records.exclude(
        status=AttendanceRecord.STATUS_SCHEDULED
    ).count()
    if counted < limit:
        return False
    member.status = Member.STATUS_INACTIVE
    member.save(update_fields=["status"])
    return True


def auto_assign_monthly_sessions(month_anchor: date, *, members=None, dry_run: bool = False):
    """Auto-assign sessions for the given month for every active member.

    Distributes each member's package sessions across the month using their
    assigned coach's availability (matched on skill level). Skips slots that
    already clash with the coach's calendar or the member's own schedule.
    Returns a summary dict with counts and any skipped members.
    """

    start, end = _month_bounds(month_anchor)
    if members is None:
        # Trial members are NOT auto-assigned — their one lifetime trial session
        # is manually scheduled. Inactive/churned members are also excluded.
        members = Member.objects.filter(status=Member.STATUS_ACTIVE)
    members = list(members.select_related("assigned_coach", "payment_plan"))

    existing_sessions = list(
        TrainingSession.objects.filter(session_date__range=(start, end)).select_related("coach")
    )
    sessions_by_date = {}
    for session in existing_sessions:
        sessions_by_date.setdefault(session.session_date, []).append(session)

    member_schedule = {}
    for record in AttendanceRecord.objects.filter(
        training_session__session_date__range=(start, end)
    ).select_related("training_session"):
        member_schedule.setdefault(record.member_id, {}).setdefault(
            record.training_session.session_date, []
        ).append(record.training_session)

    created_sessions = 0
    created_attendances = 0
    skipped = []

    for member in members:
        target = member.package_sessions or 4
        already_scheduled = sum(
            len(entries) for entries in member_schedule.get(member.pk, {}).values()
        )
        remaining = max(target - already_scheduled, 0)
        if not remaining:
            continue

        availabilities = _eligible_availabilities(member)
        if not availabilities:
            skipped.append({"member": member.full_name, "reason": "no coach availability"})
            continue

        # Walk through each date in the month; for each, try the member's
        # available slots in weekday order. Balances across the month.
        current = start
        assigned_for_member = 0
        while current <= end and assigned_for_member < remaining:
            weekday_slots = [slot for slot in availabilities if slot.weekday == current.weekday()]
            for slot in weekday_slots:
                if assigned_for_member >= remaining:
                    break
                if _slot_has_conflict(sessions_by_date, current, slot):
                    continue
                if _member_has_clash(member_schedule.setdefault(member.pk, {}), current, slot):
                    continue
                if dry_run:
                    assigned_for_member += 1
                    continue

                title = f"{member.get_skill_level_display()} Training"
                session, _ = TrainingSession.objects.get_or_create(
                    session_date=current,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    coach=slot.coach,
                    court=slot.court or "Main Court",
                    defaults={
                        "title": title,
                        "syllabus_root": SyllabusRoot.get_default(),
                    },
                )
                created_on_this_date = session.pk not in {s.pk for s in sessions_by_date.get(current, [])}
                if created_on_this_date:
                    sessions_by_date.setdefault(current, []).append(session)
                    created_sessions += 1

                _, att_created = AttendanceRecord.objects.get_or_create(
                    training_session=session, member=member
                )
                if att_created:
                    created_attendances += 1
                    member_schedule[member.pk].setdefault(current, []).append(session)
                    assigned_for_member += 1
            current += timedelta(days=1)

        if assigned_for_member < remaining:
            skipped.append(
                {
                    "member": member.full_name,
                    "reason": f"only placed {assigned_for_member}/{remaining} needed sessions (coach availability too narrow)",
                }
            )

    return {
        "month": start.strftime("%B %Y"),
        "created_sessions": created_sessions,
        "created_attendances": created_attendances,
        "members_processed": len(members),
        "skipped": skipped,
    }
