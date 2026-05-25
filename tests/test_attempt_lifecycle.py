"""Tests for the attempt lifecycle: start, save answer, submit, score."""

from datetime import timedelta

import pytest
from django.utils import timezone

from attempts.models import Attempt
from attempts.services import auto_submit_if_expired, start_attempt
from tests.factories import UserFactory, build_quiz_with_questions


@pytest.mark.django_db
class TestStartAttempt:
    def test_start_creates_in_progress(self):
        quiz, _ = build_quiz_with_questions()
        user = UserFactory()
        attempt = start_attempt(user, quiz)
        assert attempt.status == Attempt.Status.IN_PROGRESS

    def test_start_captures_question_order(self):
        quiz, qs = build_quiz_with_questions(num_questions=5)
        attempt = start_attempt(UserFactory(), quiz)
        assert len(attempt.question_order) == 5
        assert set(attempt.question_order) == {q.id for q in qs}


@pytest.mark.django_db
class TestTimerEnforcement:
    def test_start_with_time_limit_sets_expiry(self):
        quiz, _ = build_quiz_with_questions()
        quiz.time_limit_minutes = 30
        quiz.save()

        attempt = start_attempt(UserFactory(), quiz)
        assert attempt.time_limit_expires_at is not None
        # Should be roughly 30 minutes from now (within ±5 minutes tolerance).
        delta = attempt.time_limit_expires_at - timezone.now()
        assert 25 * 60 < delta.total_seconds() < 35 * 60

    def test_no_time_limit_means_no_expiry(self):
        quiz, _ = build_quiz_with_questions()
        attempt = start_attempt(UserFactory(), quiz)
        assert attempt.time_limit_expires_at is None

    def test_auto_submit_when_expired(self):
        quiz, _ = build_quiz_with_questions()
        quiz.time_limit_minutes = 1
        quiz.save()

        attempt = start_attempt(UserFactory(), quiz)
        attempt.time_limit_expires_at = timezone.now() - timedelta(seconds=1)
        attempt.save()

        result = auto_submit_if_expired(attempt)
        attempt.refresh_from_db()

        assert result is True
        assert attempt.status == Attempt.Status.GRADED
        assert attempt.submitted_at is not None

    def test_auto_submit_idempotent(self):
        quiz, _ = build_quiz_with_questions()
        quiz.time_limit_minutes = 1
        quiz.save()
        attempt = start_attempt(UserFactory(), quiz)
        attempt.time_limit_expires_at = timezone.now() - timedelta(seconds=1)
        attempt.save()

        first = auto_submit_if_expired(attempt)
        second = auto_submit_if_expired(attempt)

        assert first is True
        assert second is False  # Already submitted.

    def test_active_timer_does_not_trigger_submit(self):
        quiz, _ = build_quiz_with_questions()
        quiz.time_limit_minutes = 30
        quiz.save()
        attempt = start_attempt(UserFactory(), quiz)

        assert not attempt.is_time_expired
        assert auto_submit_if_expired(attempt) is False