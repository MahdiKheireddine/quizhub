"""Pytest fixtures shared across all tests.

Conventions:
  - Fixtures named after roles: ``creator``, ``normal_user``, ``admin``.
  - Use the ``db`` fixture for any test touching the database
    (pytest-django auto-marker via ``@pytest.mark.django_db``).
  - Use ``client`` from pytest-django for authenticated request testing.
"""

import pytest

from tests.factories import (
    CreatorFactory,
    QuizFactory,
    StaffFactory,
    UserFactory,
    build_quiz_with_questions,
)


@pytest.fixture
def normal_user(db):
    return UserFactory()


@pytest.fixture
def another_normal_user(db):
    return UserFactory()


@pytest.fixture
def creator(db):
    return CreatorFactory()


@pytest.fixture
def another_creator(db):
    return CreatorFactory()


@pytest.fixture
def admin(db):
    return StaffFactory()


@pytest.fixture
def public_quiz(db, creator):
    return QuizFactory(creator=creator)


@pytest.fixture
def private_quiz(db, creator):
    from quizzes.models import Quiz
    return QuizFactory(creator=creator, visibility=Quiz.Visibility.PRIVATE)


@pytest.fixture
def quiz_with_questions(db, creator):
    """Returns (quiz, questions). 3 single-choice questions, 4 choices each,
    first choice correct, 1 point each."""
    return build_quiz_with_questions(creator=creator)


@pytest.fixture
def authed_client(client, normal_user):
    """A test client logged in as a normal user."""
    client.force_login(normal_user)
    return client