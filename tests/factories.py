
import factory
from django.contrib.auth import get_user_model

from accounts.models import CreatorRequest
from attempts.models import Attempt
from quizzes.models import (
    Category,
    Choice,
    Invitation,
    JoinRequest,
    Question,
    Quiz,
    Tag,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    is_active = True
    role = User.Role.NORMAL


class CreatorFactory(UserFactory):
    """A user who has been approved as a creator."""
    role = User.Role.CREATOR
    is_creator_approved = True


class StaffFactory(UserFactory):
    """A user with admin/staff access."""
    is_staff = True
    role = User.Role.ADMIN


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"cat-{n}")


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"tag-{n}")
    slug = factory.LazyAttribute(lambda o: o.name)


class QuizFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Quiz

    creator = factory.SubFactory(CreatorFactory)
    title = factory.Sequence(lambda n: f"Quiz {n}")
    description = "A test quiz."
    visibility = Quiz.Visibility.PUBLIC
    is_published = True
    is_active = True


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Question

    quiz = factory.SubFactory(QuizFactory)
    text = factory.Sequence(lambda n: f"Question {n}?")
    type = Question.QuestionType.SINGLE
    points = 1
    order = factory.Sequence(lambda n: n)


class ChoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Choice

    question = factory.SubFactory(QuestionFactory)
    text = factory.Sequence(lambda n: f"Choice {n}")
    is_correct = False
    order = factory.Sequence(lambda n: n)


class CreatorRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CreatorRequest

    user = factory.SubFactory(UserFactory)
    reason = "I have great ideas for quizzes that will benefit everyone."


class InvitationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invitation

    quiz = factory.SubFactory(QuizFactory, visibility=Quiz.Visibility.PRIVATE)
    invited_user = factory.SubFactory(UserFactory)
    invited_by = factory.LazyAttribute(lambda o: o.quiz.creator)


class JoinRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JoinRequest

    quiz = factory.SubFactory(QuizFactory, visibility=Quiz.Visibility.PRIVATE)
    user = factory.SubFactory(UserFactory)
    message = "Please let me in!"


class AttemptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Attempt

    user = factory.SubFactory(UserFactory)
    quiz = factory.SubFactory(QuizFactory)


# ─── Helpers ────────────────────────────────────────────────────────────


def build_quiz_with_questions(
    creator=None,
    num_questions=3,
    num_choices_per_question=4,
    points_per_question=1,
    correct_choice_index=0,
    question_type=Question.QuestionType.SINGLE,
):
    """Build a fully-formed quiz with questions and choices.

    Convenience for scoring/attempt tests: returns ``(quiz, [questions])``.
    By default the first choice in each question is correct.
    """
    if creator is None:
        creator = CreatorFactory()
    quiz = QuizFactory(creator=creator)
    questions = []
    for q_idx in range(num_questions):
        q = QuestionFactory(
            quiz=quiz,
            type=question_type,
            points=points_per_question,
            order=q_idx,
        )
        for c_idx in range(num_choices_per_question):
            ChoiceFactory(
                question=q,
                order=c_idx,
                is_correct=(c_idx == correct_choice_index),
            )
        questions.append(q)
    return quiz, questions