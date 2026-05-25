"""Tests for Quiz model state machine and derived properties."""

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.factories import QuizFactory, build_quiz_with_questions


@pytest.mark.django_db
class TestQuizStateMachine:
    def test_draft_quiz_not_accepting_responses(self):
        q = QuizFactory(is_published=False)
        assert not q.is_accepting_responses

    def test_paused_quiz_not_accepting_responses(self):
        q = QuizFactory(is_active=False)
        assert not q.is_accepting_responses

    def test_closed_quiz_not_accepting_responses(self):
        q = QuizFactory(closes_at=timezone.now() - timedelta(hours=1))
        assert not q.is_accepting_responses

    def test_open_quiz_is_accepting(self):
        q = QuizFactory()
        assert q.is_accepting_responses

    def test_future_close_does_not_block(self):
        q = QuizFactory(closes_at=timezone.now() + timedelta(hours=1))
        assert q.is_accepting_responses


@pytest.mark.django_db
class TestResultsVisibility:
    def test_immediate_results_visible(self):
        q = QuizFactory(show_results_immediately=True)
        assert q.results_visible

    def test_deferred_results_not_visible_until_released(self):
        q = QuizFactory(show_results_immediately=False)
        assert not q.results_visible

    def test_released_results_visible(self):
        q = QuizFactory(show_results_immediately=False)
        q.results_released_at = timezone.now()
        q.save()
        assert q.results_visible


@pytest.mark.django_db
class TestQuizProperties:
    def test_total_points_sums_questions(self):
        quiz, qs = build_quiz_with_questions(num_questions=4, points_per_question=5)
        assert quiz.total_points == 20

    def test_question_count(self):
        quiz, qs = build_quiz_with_questions(num_questions=3)
        assert quiz.question_count == 3

    def test_empty_quiz_total_points_zero(self):
        quiz = QuizFactory()
        assert quiz.total_points == 0
        assert quiz.question_count == 0


@pytest.mark.django_db
class TestSlug:
    def test_slug_auto_generated_from_title(self):
        q = QuizFactory(title="Django Basics", slug="")
        # The save() override should populate slug.
        assert q.slug == "django-basics" or "django" in q.slug

    def test_duplicate_titles_get_unique_slugs(self):
        q1 = QuizFactory(title="Python Quiz", slug="")
        q2 = QuizFactory(title="Python Quiz", slug="")
        assert q1.slug != q2.slug