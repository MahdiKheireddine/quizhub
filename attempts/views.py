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
    """Placeholder for commit 16. For now, show a basic completion message."""
    attempt = _get_own_attempt(request.user, attempt_id)
    return render(request, "attempts/attempt_result.html", {
        "attempt": attempt,
        "quiz": attempt.quiz,
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
