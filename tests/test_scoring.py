"""Tests for the scoring service — the heart of the product.

Strict scoring means: full points only if selected choices EXACTLY match
the correct set.
"""

import pytest

from attempts.services import score_attempt, start_attempt
from quizzes.models import Question
from tests.factories import (
    ChoiceFactory,
    CreatorFactory,
    QuestionFactory,
    QuizFactory,
    UserFactory,
    build_quiz_with_questions,
)


@pytest.mark.django_db
class TestSingleChoiceScoring:
    def test_correct_answer_gets_full_points(self):
        quiz, qs = build_quiz_with_questions(num_questions=1, points_per_question=10)
        q = qs[0]
        correct = q.choices.get(is_correct=True)

        user = UserFactory()
        attempt = start_attempt(user, quiz)
        ans = attempt.answers.create(question=q)
        ans.selected_choices.set([correct])

        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 10
        assert attempt.max_score == 10

    def test_wrong_answer_gets_zero(self):
        quiz, qs = build_quiz_with_questions(num_questions=1, points_per_question=10)
        q = qs[0]
        wrong = q.choices.filter(is_correct=False).first()

        user = UserFactory()
        attempt = start_attempt(user, quiz)
        ans = attempt.answers.create(question=q)
        ans.selected_choices.set([wrong])

        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 0

    def test_unanswered_question_gets_zero(self):
        quiz, qs = build_quiz_with_questions(num_questions=1, points_per_question=10)
        user = UserFactory()
        attempt = start_attempt(user, quiz)
        # No answer created.
        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 0
        # max_score should still account for the unanswered question.
        assert attempt.max_score == 10


@pytest.mark.django_db
class TestMultipleChoiceScoring:
    def _build_multi_choice_quiz(self, correct_indices=(0, 2)):
        creator = CreatorFactory()
        quiz = QuizFactory(creator=creator)
        q = QuestionFactory(quiz=quiz, type=Question.QuestionType.MULTIPLE, points=10)
        choices = [
            ChoiceFactory(question=q, order=i, is_correct=(i in correct_indices))
            for i in range(4)
        ]
        return quiz, q, choices

    def test_exact_match_gets_full_points(self):
        quiz, q, choices = self._build_multi_choice_quiz(correct_indices=(0, 2))
        user = UserFactory()
        attempt = start_attempt(user, quiz)
        ans = attempt.answers.create(question=q)
        ans.selected_choices.set([choices[0], choices[2]])

        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 10

    def test_missing_a_correct_choice_gets_zero(self):
        quiz, q, choices = self._build_multi_choice_quiz(correct_indices=(0, 2))
        user = UserFactory()
        attempt = start_attempt(user, quiz)
        ans = attempt.answers.create(question=q)
        ans.selected_choices.set([choices[0]])  # missing choices[2]

        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 0

    def test_extra_wrong_choice_gets_zero(self):
        quiz, q, choices = self._build_multi_choice_quiz(correct_indices=(0, 2))
        user = UserFactory()
        attempt = start_attempt(user, quiz)
        ans = attempt.answers.create(question=q)
        ans.selected_choices.set([choices[0], choices[1], choices[2]])  # extra: 1

        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 0


@pytest.mark.django_db
class TestMixedQuizScoring:
    def test_partial_correct_answers_sum_correctly(self):
        quiz, qs = build_quiz_with_questions(
            num_questions=3, points_per_question=10,
        )
        user = UserFactory()
        attempt = start_attempt(user, quiz)

        # Answer Q0 correctly, Q1 wrong, leave Q2 unanswered.
        ans0 = attempt.answers.create(question=qs[0])
        ans0.selected_choices.set([qs[0].choices.get(is_correct=True)])
        ans1 = attempt.answers.create(question=qs[1])
        ans1.selected_choices.set([qs[1].choices.filter(is_correct=False).first()])

        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 10  # Q0 only
        assert attempt.max_score == 30

    def test_score_percent_calculates_correctly(self):
        quiz, qs = build_quiz_with_questions(num_questions=4, points_per_question=5)
        user = UserFactory()
        attempt = start_attempt(user, quiz)
        # Answer 2 of 4 correctly.
        for q in qs[:2]:
            ans = attempt.answers.create(question=q)
            ans.selected_choices.set([q.choices.get(is_correct=True)])

        score_attempt(attempt)
        attempt.refresh_from_db()
        assert attempt.score == 10
        assert attempt.max_score == 20
        assert attempt.score_percent == 50