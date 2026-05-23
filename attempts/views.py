from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from quizzes.models import Choice, Question, Quiz

from .models import Answer, Attempt
from .services import (
    auto_submit_if_expired,
    can_user_take_quiz,
    get_or_create_in_progress,
    score_attempt,
    start_attempt,
)


def _format_mm_ss(seconds):
    """Format an integer second count as 'Xm YYs'. Returns None if seconds is None/0."""
    if not seconds:
        return None
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def _get_own_attempt(user, attempt_id):
    return get_object_or_404(
        Attempt.objects.select_related("quiz"),
        id=attempt_id,
        user=user,
    )


@login_required
def quiz_start(request, slug):
    """Pre-attempt screen — confirm rules, then start."""
    quiz = get_object_or_404(Quiz, slug=slug, is_published=True)
    ok, reason = can_user_take_quiz(request.user, quiz)
    if not ok:
        messages.error(request, reason)
        return redirect("quizzes:public_detail", slug=quiz.slug)

    # Resume an existing in-progress attempt instead of starting fresh.
    in_progress = get_or_create_in_progress(request.user, quiz)
    if in_progress:
        return redirect("attempts:run", attempt_id=in_progress.id)

    if request.method == "POST":
        attempt = start_attempt(request.user, quiz)
        return redirect("attempts:run", attempt_id=attempt.id)

    return render(request, "attempts/quiz_start.html", {"quiz": quiz})


@login_required
def attempt_run(request, attempt_id):
    """The question runner — shows one question at a time.

    `?q=` query param selects the index in the shuffled order (0-based).
    """
    attempt = _get_own_attempt(request.user, attempt_id)

    # Server-side enforcement: if the timer has expired, finalize and bounce.
    if auto_submit_if_expired(attempt):
        messages.info(request, "Time's up — your attempt was submitted automatically.")
        return redirect("attempts:result", attempt_id=attempt.id)

    if attempt.is_finished:
        return redirect("attempts:result", attempt_id=attempt.id)

    questions = attempt.ordered_questions()
    if not questions:
        messages.error(request, "This quiz has no questions.")
        return redirect("quizzes:public_detail", slug=attempt.quiz.slug)

    try:
        idx = int(request.GET.get("q", 0))
    except (TypeError, ValueError):
        idx = 0
    idx = max(0, min(idx, len(questions) - 1))

    question = questions[idx]
    answer = attempt.get_answer_for(question)
    selected_ids = (
        set(answer.selected_choices.values_list("id", flat=True)) if answer else set()
    )

    # Sidebar dot data
    answered_qids = set(attempt.answers.values_list("question_id", flat=True))
    progress = [
        {"idx": i, "answered": q.id in answered_qids, "current": i == idx}
        for i, q in enumerate(questions)
    ]

    return render(request, "attempts/attempt_run.html", {
        "attempt": attempt,
        "quiz": attempt.quiz,
        "question": question,
        "selected_ids": selected_ids,
        "idx": idx,
        "total": len(questions),
        "progress": progress,
        "is_first": idx == 0,
        "is_last": idx == len(questions) - 1,
        "answered_count": len(answered_qids),
        # Timer context
        "has_timer": attempt.time_limit_expires_at is not None,
        "time_remaining_seconds": attempt.time_remaining_seconds,
    })


@login_required
@require_POST
def answer_save(request, attempt_id, question_id):
    """HTMX endpoint: save the user's selection for one question.

    Returns a small HTML fragment confirming the save.
    """
    attempt = _get_own_attempt(request.user, attempt_id)
    if attempt.is_finished:
        # 409 Conflict — the attempt is locked, the client shouldn't try to write.
        return HttpResponse("", status=409)

    # If time ran out between the user clicking and this request landing, finalize.
    if auto_submit_if_expired(attempt):
        return HttpResponse("Time expired", status=410)

    question = get_object_or_404(Question, id=question_id, quiz=attempt.quiz)

    # Choice IDs come in as a list (single → one item; multiple → many).
    raw = request.POST.getlist("choice")
    try:
        choice_ids = [int(x) for x in raw]
    except (TypeError, ValueError):
        choice_ids = []

    # Only allow choices that belong to this question.
    valid_choices = list(
        Choice.objects.filter(id__in=choice_ids, question=question)
    )

    answer, _ = Answer.objects.get_or_create(attempt=attempt, question=question)
    answer.selected_choices.set(valid_choices)

    return render(request, "attempts/partials/answer_saved.html", {
        "question": question,
    })


@login_required
def attempt_submit_confirm(request, attempt_id):
    """Confirmation screen before final submission."""
    attempt = _get_own_attempt(request.user, attempt_id)

    if auto_submit_if_expired(attempt):
        return redirect("attempts:result", attempt_id=attempt.id)

    if attempt.is_finished:
        return redirect("attempts:result", attempt_id=attempt.id)

    questions = attempt.ordered_questions()
    answered_qids = set(attempt.answers.values_list("question_id", flat=True))
    unanswered = [q for q in questions if q.id not in answered_qids]

    return render(request, "attempts/attempt_submit.html", {
        "attempt": attempt,
        "quiz": attempt.quiz,
        "total": len(questions),
        "answered_count": len(answered_qids),
        "unanswered_count": len(unanswered),
    })


@login_required
@require_POST
def attempt_submit(request, attempt_id):
    """Finalize the attempt: mark submitted, then run scoring."""
    attempt = _get_own_attempt(request.user, attempt_id)
    if attempt.is_finished:
        return redirect("attempts:result", attempt_id=attempt.id)

    attempt.status = Attempt.Status.SUBMITTED
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=["status", "submitted_at"])
    score_attempt(attempt)

    messages.success(request, "Quiz submitted!")
    return redirect("attempts:result", attempt_id=attempt.id)


@login_required
def attempt_result(request, attempt_id):
    """Per-attempt result page. Score + per-question breakdown when results
    are visible, else a friendly 'results pending' state.

    Always visible to the attempt's owner. Other users get 404 (privacy)."""
    attempt = _get_own_attempt(request.user, attempt_id)
    quiz = attempt.quiz

    # Edge case: if the attempt was marked SUBMITTED but somehow not yet GRADED
    # (e.g. score_attempt errored mid-way), grade it now. score_attempt is idempotent.
    if attempt.status == Attempt.Status.SUBMITTED:
        score_attempt(attempt)

    results_visible = quiz.results_visible
    questions_with_answers = []
    if results_visible:
        for question in attempt.ordered_questions():
            answer = attempt.get_answer_for(question)
            selected = list(answer.selected_choices.all()) if answer else []
            all_choices = list(question.choices.all())
            correct_ids = {c.id for c in all_choices if c.is_correct}
            questions_with_answers.append({
                "question": question,
                "answer": answer,
                "selected_ids": {c.id for c in selected},
                "correct_ids": correct_ids,
                "all_choices": all_choices,
                "is_correct": answer.is_correct if answer else False,
                "points_earned": answer.points_earned if answer else 0,
            })

    # Time spent (from start to submission).
    time_spent_seconds = None
    if attempt.submitted_at and attempt.started_at:
        delta = attempt.submitted_at - attempt.started_at
        time_spent_seconds = int(delta.total_seconds())

    # Pass/fail badge — only meaningful if the quiz defines a pass_score.
    passed = None
    if quiz.pass_score is not None:
        passed = attempt.score_percent >= quiz.pass_score

    can_retake = (
        quiz.allow_retakes
        and quiz.is_accepting_responses
        and attempt.is_finished
    )

    return render(request, "attempts/attempt_result.html", {
        "attempt": attempt,
        "quiz": quiz,
        "results_visible": results_visible,
        "questions_with_answers": questions_with_answers,
        "time_spent_seconds": time_spent_seconds,
        "time_spent_display": _format_mm_ss(time_spent_seconds),
        "passed": passed,
        "can_retake": can_retake,
    })


@login_required
def attempt_heartbeat(request, attempt_id):
    """Return time remaining for the attempt.

    The client polls this every ~10s to stay synced with the server. Also
    doubles as a safety net — if we detect expiry here, we finalize server-side
    before responding, and the client sees `finished: true` and redirects.
    """
    attempt = _get_own_attempt(request.user, attempt_id)

    if attempt.is_finished:
        return JsonResponse({"finished": True, "remaining": 0})

    if attempt.time_limit_expires_at is None:
        return JsonResponse({"finished": False, "remaining": None})

    if auto_submit_if_expired(attempt):
        return JsonResponse({"finished": True, "remaining": 0})

    return JsonResponse({
        "finished": False,
        "remaining": attempt.time_remaining_seconds,
    })


# ─── Leaderboard ────────────────────────────────────────────────────────

def quiz_leaderboard(request, slug):
    """Public leaderboard for a quiz.

    404 if the quiz is unpublished OR if results aren't yet visible (creator
    hasn't released them). Anyone allowed to see the quiz can see its board.
    """
    from django.http import Http404

    from quizzes.queries import visible_quizzes

    quiz = get_object_or_404(Quiz.objects.filter(is_published=True), slug=slug)

    if not quiz.results_visible:
        raise Http404("Leaderboard not yet available.")

    if not visible_quizzes(request.user).filter(id=quiz.id).exists():
        raise Http404

    # Each user's BEST graded attempt: highest score, then earliest submission as
    # tie-breaker for the initial pick. (Final display sorts by score then time
    # spent, which is what we actually want to show.)
    graded = (
        Attempt.objects.filter(quiz=quiz, status=Attempt.Status.GRADED)
        .select_related("user")
    )

    best_per_user = {}
    for a in graded.order_by("-score", "submitted_at"):
        if a.user_id not in best_per_user:
            best_per_user[a.user_id] = a

    ranked = sorted(
        best_per_user.values(),
        key=lambda a: (
            -a.score,
            (a.submitted_at - a.started_at).total_seconds()
            if a.submitted_at else float("inf"),
        ),
    )

    rows = []
    for rank, a in enumerate(ranked, start=1):
        time_spent = None
        if a.submitted_at and a.started_at:
            time_spent = int((a.submitted_at - a.started_at).total_seconds())
        rows.append({
            "rank": rank,
            "attempt": a,
            "user": a.user,
            "score": a.score,
            "max_score": a.max_score,
            "percent": a.score_percent,
            "time_spent_seconds": time_spent,
            "time_spent_display": _format_mm_ss(time_spent),
            "is_current_user": (
                request.user.is_authenticated and a.user_id == request.user.id
            ),
        })

    # Paginate the ranked list. Paginator accepts a Python list and slices it
    # in memory — fine for our scale (thousands at most per quiz). If a quiz
    # ever has 100k+ attempts, switch to a DB-side window function.
    from core.pagination import paginate
    page_obj, querystring_no_page, page_range = paginate(rows, request, per_page=20)
    top_rows = list(page_obj.object_list)

    # If the current user isn't on this page but exists in the rankings,
    # surface their row separately so they always see where they stand.
    current_user_row = None
    if request.user.is_authenticated:
        in_page = any(r["is_current_user"] for r in top_rows)
        if not in_page:
            current_user_row = next((r for r in rows if r["is_current_user"]), None)

    return render(request, "attempts/leaderboard.html", {
        "quiz": quiz,
        "rows": top_rows,
        "current_user_row": current_user_row,
        "total_participants": len(rows),
        "page_obj": page_obj,
        "querystring_no_page": querystring_no_page,
        "page_range": page_range,
    })
