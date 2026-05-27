from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone


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


class CreatorRequest(models.Model):
    """
    A user's request to be granted creator privileges.

    A single user may only have one pending request at a time — enforced by a
    partial unique constraint (``status='pending'``). Approving a request flips
    both ``user.is_creator_approved=True`` and ``user.role='creator'`` inside a
    single atomic transaction, so the user is never left half-promoted if the
    save fails midway. Rejection is non-destructive — it just records the
    decision (and an optional note shown to the user) so they can submit again.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator_requests",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="creator_requests_reviewed",
    )
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="pending"),
                name="unique_pending_creator_request_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"

    def approve(self, reviewer):
        with transaction.atomic():
            self.status = self.Status.APPROVED
            self.reviewed_by = reviewer
            self.reviewed_at = timezone.now()
            self.save()

            self.user.is_creator_approved = True
            self.user.role = self.user.Role.CREATOR
            self.user.save(update_fields=["is_creator_approved", "role"])

    def reject(self, reviewer, note=""):
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note
        self.save()


class UserPreferences(models.Model):
    """Per-user preferences. Auto-created via signal when a User is created
    (see ``accounts/signals.py``) so ``user.preferences`` is always present.

    For now only stores the daisyUI theme. The list of allowed theme names is
    validated at save time in the view, not as a TextChoices, so the curated
    list can evolve without a schema migration.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    theme = models.CharField(max_length=32, default="dim")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "User preferences"

    def __str__(self):
        return f"Preferences for {self.user.username}"
