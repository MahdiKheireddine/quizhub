"""Statistics queries for the creator dashboard.

All queries are scoped to a single creator's quizzes. Aggregations happen in
SQL via Django ORM (``annotate`` + ``Aggregate``). Avoid N+1: never loop
quizzes and run per-quiz queries — annotate them once.
"""

from django.db.models import Avg, Count, FloatField, Max, Q
from django.db.models.functions import Cast

from attempts.models import Attempt
from quizzes.models import Quiz


def creator_overview_stats(creator):
    """Top-of-dashboard stat block.

    Returns a dict with:
      - ``quiz_count``: total quizzes (any status)
      - ``published_count``: published quizzes
      - ``drafts_count``: quiz_count - published_count (pre-computed for templates)
      - ``total_attempts``: graded attempts across all their quizzes
      - ``unique_participants``: distinct users who finished any of their quizzes
      - ``avg_score_percent``: overall average across all graded attempts
    """
    quizzes = Quiz.objects.filter(creator=creator)
    quiz_count = quizzes.count()
    published_count = quizzes.filter(is_published=True).count()

    graded = Attempt.objects.filter(
        quiz__creator=creator,
        status=Attempt.Status.GRADED,
        max_score__gt=0,  # avoid division by zero for empty quizzes
    )
    agg = graded.aggregate(
        total_attempts=Count("id"),
        unique_participants=Count("user", distinct=True),
        avg_score_percent=Avg(
            Cast("score", FloatField()) * 100.0 / Cast("max_score", FloatField()),
        ),
    )

    return {
        "quiz_count": quiz_count,
        "published_count": published_count,
        "drafts_count": quiz_count - published_count,
        "total_attempts": agg["total_attempts"] or 0,
        "unique_participants": agg["unique_participants"] or 0,
        "avg_score_percent": round(agg["avg_score_percent"] or 0),
    }


def creator_per_quiz_stats(creator):
    """Per-quiz aggregations for the dashboard table.

    One query annotates every quiz with its attempt count, average score,
    and best score. The top scorer per quiz is a separate (small) lookup —
    bounded by the number of quizzes the creator owns.
    """
    qs = (
        Quiz.objects.filter(creator=creator)
        .annotate(
            attempts_count=Count(
                "attempts",
                filter=Q(attempts__status=Attempt.Status.GRADED),
            ),
            avg_score_percent=Avg(
                Cast("attempts__score", FloatField()) * 100.0
                / Cast("attempts__max_score", FloatField()),
                filter=Q(
                    attempts__status=Attempt.Status.GRADED,
                    attempts__max_score__gt=0,
                ),
            ),
            top_score=Max(
                "attempts__score",
                filter=Q(attempts__status=Attempt.Status.GRADED),
            ),
        )
        .order_by("-updated_at")
    )

    results = []
    for quiz in qs:
        top_scorer = None
        if quiz.top_score is not None:
            top_attempt = (
                Attempt.objects.filter(
                    quiz=quiz,
                    status=Attempt.Status.GRADED,
                    score=quiz.top_score,
                )
                .select_related("user")
                .order_by("submitted_at")
                .first()
            )
            if top_attempt:
                top_scorer = top_attempt.user
        results.append({
            "quiz": quiz,
            "attempts_count": quiz.attempts_count or 0,
            "avg_score_percent": round(quiz.avg_score_percent or 0),
            "top_score": quiz.top_score,
            "top_scorer": top_scorer,
        })
    return results


def creator_recent_activity(creator, limit=10):
    """Recent graded attempts on this creator's quizzes."""
    return (
        Attempt.objects.filter(
            quiz__creator=creator,
            status=Attempt.Status.GRADED,
        )
        .select_related("user", "quiz")
        .order_by("-submitted_at")[:limit]
    )