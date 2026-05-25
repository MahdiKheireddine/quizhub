"""Tests for access-control helpers — who can see/take what."""

import pytest
from django.contrib.auth.models import AnonymousUser

from attempts.services import can_user_take_quiz
from quizzes.models import Quiz
from quizzes.queries import public_browse_queryset, visible_quizzes
from tests.factories import (
    AttemptFactory,
    InvitationFactory,
    QuizFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestVisibleQuizzes:
    def test_anonymous_sees_only_published_public(self):
        public = QuizFactory()
        QuizFactory(visibility=Quiz.Visibility.PRIVATE)  # private — invisible
        QuizFactory(is_published=False)  # draft — invisible

        visible = visible_quizzes(AnonymousUser())
        assert set(visible) == {public}

    def test_normal_user_sees_public_only_without_invites(self, normal_user):
        public = QuizFactory()
        QuizFactory(visibility=Quiz.Visibility.PRIVATE)

        visible = visible_quizzes(normal_user)
        assert set(visible) == {public}

    def test_invited_user_sees_invited_private_quizzes(self, normal_user):
        public = QuizFactory()
        private = QuizFactory(visibility=Quiz.Visibility.PRIVATE)
        InvitationFactory(quiz=private, invited_user=normal_user)

        visible = visible_quizzes(normal_user)
        assert set(visible) == {public, private}

    def test_visible_excludes_drafts(self, normal_user):
        QuizFactory(is_published=False)
        assert visible_quizzes(normal_user).count() == 0

    def test_invitation_does_not_create_duplicates(self, normal_user):
        """A quiz with many invitations should appear once for the invited user."""
        private = QuizFactory(visibility=Quiz.Visibility.PRIVATE)
        InvitationFactory(quiz=private, invited_user=normal_user)
        InvitationFactory(quiz=private, invited_user=UserFactory())
        InvitationFactory(quiz=private, invited_user=UserFactory())

        visible = visible_quizzes(normal_user)
        assert visible.count() == 1


@pytest.mark.django_db
class TestPublicBrowse:
    def test_browse_excludes_private_quizzes_always(self, normal_user):
        """Even invited users don't see private quizzes in the global browse."""
        public = QuizFactory()
        private = QuizFactory(visibility=Quiz.Visibility.PRIVATE)
        InvitationFactory(quiz=private, invited_user=normal_user)

        assert set(public_browse_queryset()) == {public}


@pytest.mark.django_db
class TestCanUserTakeQuiz:
    def test_anonymous_cannot_take(self):
        q = QuizFactory()
        ok, reason = can_user_take_quiz(AnonymousUser(), q)
        assert not ok

    def test_paused_quiz_cannot_be_taken(self, normal_user):
        q = QuizFactory(is_active=False)
        ok, reason = can_user_take_quiz(normal_user, q)
        assert not ok

    def test_draft_quiz_cannot_be_taken(self, normal_user):
        q = QuizFactory(is_published=False)
        ok, reason = can_user_take_quiz(normal_user, q)
        assert not ok

    def test_uninvited_user_cannot_take_private(self, normal_user):
        q = QuizFactory(visibility=Quiz.Visibility.PRIVATE)
        ok, reason = can_user_take_quiz(normal_user, q)
        assert not ok

    def test_invited_user_can_take_private(self, normal_user):
        q = QuizFactory(visibility=Quiz.Visibility.PRIVATE)
        InvitationFactory(quiz=q, invited_user=normal_user)
        ok, reason = can_user_take_quiz(normal_user, q)
        assert ok

    def test_retake_blocked_when_not_allowed(self, normal_user):
        from attempts.models import Attempt
        q = QuizFactory(allow_retakes=False)
        AttemptFactory(user=normal_user, quiz=q, status=Attempt.Status.GRADED)

        ok, reason = can_user_take_quiz(normal_user, q)
        assert not ok
        assert "retake" in reason.lower() or "already" in reason.lower()

    def test_retake_allowed_when_quiz_permits(self, normal_user):
        from attempts.models import Attempt
        q = QuizFactory(allow_retakes=True)
        AttemptFactory(user=normal_user, quiz=q, status=Attempt.Status.GRADED)

        ok, reason = can_user_take_quiz(normal_user, q)
        assert ok