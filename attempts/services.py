"""Business logic for attempts that doesn't belong in models or views.

Keeping it here makes it easy to test and easy to reuse from views, signals,
admin actions, or future API endpoints.
"""

import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from quizzes.models import Quiz

from .models import Attempt


def start_attempt(user, quiz):
    """Create a new in-progress Attempt with a shuffled question order and,
    if the quiz has a time limit, a server-enforced expiry timestamp.

    Caller is responsible for verifying access first (see can_user_take_quiz).
    """
    question_ids = list(quiz.questions.values_list("id", flat=True))
    random.shuffle(question_ids)

    expires_at = None
    if quiz.time_limit_minutes:
        expires_at = timezone.now() + timedelta(minutes=quiz.time_limit_minutes)

    return Attempt.objects.create(
        user=user,
        quiz=quiz,
        question_order=question_ids,
        time_limit_expires_at=expires_at,
    )


def score_attempt(attempt):
    """Compute and persist the score for a submitted Attempt.

    Strict scoring rules:
      - SINGLE-choice: full points iff the chosen choice is correct.
      - MULTIPLE-choice: full points iff selected set EXACTLY matches the set
        of correct choices. No partial credit (we can add it later).
      - Unanswered questions: 0 points.
      - A question with no choices marked correct always scores 0 (defensive).
    """
    with transaction.atomic():
        score = 0
        max_score = 0
        for question in attempt.quiz.questions.prefetch_related("choices"):
            max_score += question.points
            answer = attempt.answers.filter(question=question).first()
            if not answer:
                continue
            selected_ids = frozenset(
                answer.selected_choices.values_list("id", flat=True)
            )
            correct_ids = frozenset(
                c.id for c in question.choices.all() if c.is_correct
            )
            is_correct = selected_ids == correct_ids and len(selected_ids) > 0
            points = question.points if is_correct else 0
            answer.is_correct = is_correct
            answer.points_earned = points
            answer.save(update_fields=["is_correct", "points_earned"])
            score += points

        attempt.score = score
        attempt.max_score = max_score
        attempt.status = Attempt.Status.GRADED
        attempt.graded_at = timezone.now()
        attempt.save(
            update_fields=["score", "max_score", "status", "graded_at"]
        )

    return attempt


def can_user_take_quiz(user, quiz):
    """Returns (ok: bool, reason: str). `reason` is a human-readable explanation
    when `ok` is False — useful to surface in the UI."""
    if not user.is_authenticated:
        return False, "You need to log in to take a quiz."
    if not quiz.is_accepting_responses:
        return False, "This quiz isn't currently accepting responses."
    if quiz.visibility == Quiz.Visibility.PRIVATE:
        # Lazy import to avoid pulling the queries module at app load time.
        from quizzes.queries import user_can_access_private_quiz
        if not user_can_access_private_quiz(user, quiz):
            return False, "You need access to take this private quiz."

    existing = (
        Attempt.objects
        .filter(user=user, quiz=quiz)
        .exclude(status=Attempt.Status.IN_PROGRESS)
        .exists()
    )
    if existing and not quiz.allow_retakes:
        return False, "You've already taken this quiz and retakes aren't allowed."

    return True, ""


def auto_submit_if_expired(attempt):
    """If an attempt's timer has expired and it's still in progress, finalize it.

    This is the SAFETY NET. It's called from multiple entry points (runner view,
    answer save, heartbeat, submit_confirm) so no matter how a request lands on
    the server, an expired attempt gets finalized.

    Returns True if we auto-submitted in this call, False otherwise. Idempotent.
    """
    if attempt.status != Attempt.Status.IN_PROGRESS:
        return False
    if not attempt.is_time_expired:
        return False

    attempt.status = Attempt.Status.SUBMITTED
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=["status", "submitted_at"])
    score_attempt(attempt)
    return True


def get_or_create_in_progress(user, quiz):
    """Return the user's in-progress attempt for this quiz, or None.

    Despite the name (mirroring Django's `get_or_create`), this DOESN'T create —
    creation is left to start_attempt(). The name reflects the call site's
    semantic intent: "find an existing attempt to resume, or signal that we
    need to start fresh".
    """
    return Attempt.objects.filter(
        user=user,
        quiz=quiz,
        status=Attempt.Status.IN_PROGRESS,
    ).first()
