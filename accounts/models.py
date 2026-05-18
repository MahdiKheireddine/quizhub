from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user for QuizHub.

    Role semantics:
        - ``normal``  : standard account, can take quizzes.
        - ``creator`` : has requested (or been granted) creator status. Whether
                        they can actually publish quizzes is gated by
                        ``is_creator_approved`` so that admins can revoke
                        publishing rights without rewriting the user's role.
        - ``admin``   : platform administrator. Implies ``can_create_quizzes``
                        regardless of the approval flag.

    ``is_creator_approved`` is the canonical gate for quiz creation. It is kept
    separate from ``role`` deliberately: ``role`` describes the user's identity
    on the platform, while ``is_creator_approved`` describes a permission that
    can be granted or revoked independently.
    """

    class Role(models.TextChoices):
        NORMAL = "normal", "Normal"
        CREATOR = "creator", "Creator"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.NORMAL,
    )
    is_creator_approved = models.BooleanField(default=False)
    bio = models.CharField(max_length=280, blank=True)

    def __str__(self):
        return self.username

    @property
    def can_create_quizzes(self):
        return (
            self.is_creator_approved
            or self.is_staff
            or self.role == self.Role.ADMIN
        )