"""Tests for the creator request workflow side-effects."""

import pytest
from django.db import IntegrityError, transaction

from accounts.models import CreatorRequest, User
from tests.factories import CreatorRequestFactory, UserFactory


@pytest.mark.django_db
class TestCreatorRequestApprove:
    def test_approve_sets_user_to_creator(self, admin):
        user = UserFactory()  # role=normal, is_creator_approved=False
        req = CreatorRequestFactory(user=user)

        req.approve(admin)

        user.refresh_from_db()
        assert user.is_creator_approved is True
        assert user.role == User.Role.CREATOR
        assert user.can_create_quizzes

    def test_approve_marks_request(self, admin):
        req = CreatorRequestFactory()
        req.approve(admin)

        req.refresh_from_db()
        assert req.status == CreatorRequest.Status.APPROVED
        assert req.reviewed_by == admin
        assert req.reviewed_at is not None


@pytest.mark.django_db
class TestCreatorRequestReject:
    def test_reject_does_not_grant_creator(self, admin):
        user = UserFactory()
        req = CreatorRequestFactory(user=user)

        req.reject(admin, note="Account too new")

        user.refresh_from_db()
        assert not user.can_create_quizzes
        assert user.role == User.Role.NORMAL

    def test_reject_persists_note(self, admin):
        req = CreatorRequestFactory()
        req.reject(admin, note="Account too new")

        req.refresh_from_db()
        assert req.status == CreatorRequest.Status.REJECTED
        assert req.review_note == "Account too new"


@pytest.mark.django_db
class TestCreatorRequestConstraint:
    def test_cannot_create_two_pending_requests(self):
        """The DB-level partial unique constraint on pending creator requests
        should prevent two pending rows for the same user.

        Wrapped in transaction.atomic() so the IntegrityError doesn't poison
        the outer test transaction.
        """
        user = UserFactory()
        CreatorRequestFactory(user=user)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CreatorRequestFactory(user=user)

    def test_can_request_again_after_rejection(self, admin):
        user = UserFactory()
        req1 = CreatorRequestFactory(user=user)
        req1.reject(admin, note="No.")

        # No exception — there's no pending request anymore.
        req2 = CreatorRequestFactory(user=user)
        assert req2.status == CreatorRequest.Status.PENDING