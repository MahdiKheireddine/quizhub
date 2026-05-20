from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Quiz(models.Model):
    """
    A quiz created by a user with creator privileges.

    Lifecycle:
      - Created as a draft (is_published=False).
      - Published (is_published=True) makes it visible per its visibility setting.
      - is_active is a manual on/off switch the creator can toggle any time.
      - closes_at is an optional auto-close datetime; once it passes, the quiz
        stops accepting responses regardless of is_active.

    A quiz is "accepting responses" only when ALL of these are true:
      published, active, and (closes_at is null OR closes_at is in the future).
    See `is_accepting_responses` below.

    Visibility:
      - public: any authenticated user can take it
      - private: only invited users or users with an approved JoinRequest can take it
    """

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    is_published = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    allow_retakes = models.BooleanField(
        default=False,
        help_text="If true, users can attempt this quiz multiple times.",
    )
    show_results_immediately = models.BooleanField(
        default=True,
        help_text="If true, users see their score and correct answers right after submitting. "
        "If false, the creator must release results manually.",
    )
    pass_score = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Optional minimum percentage to pass (0-100). Leave blank for no pass mark.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Quizzes"
        constraints = [
            models.CheckConstraint(
                check=models.Q(pass_score__isnull=True)
                | (models.Q(pass_score__gte=0) & models.Q(pass_score__lte=100)),
                name="pass_score_between_0_and_100",
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            # Reserve room for a "-N" suffix so the field never overflows.
            base = slugify(self.title)[:200] or "quiz"
            slug = base
            n = 2
            while Quiz.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def total_points(self):
        return self.questions.aggregate(total=models.Sum("points"))["total"] or 0

    @property
    def question_count(self):
        return self.questions.count()

    @property
    def is_accepting_responses(self):
        if not (self.is_published and self.is_active):
            return False
        if self.closes_at is None:
            return True
        return self.closes_at > timezone.now()

    def get_absolute_url(self):
        return reverse("quizzes:detail", kwargs={"slug": self.slug})


class Question(models.Model):
    """
    A single question within a quiz.

    Question types:
      - single: exactly one correct choice (radio buttons in UI)
      - multiple: one or more correct choices (checkboxes in UI)

    For SINGLE-choice questions, scoring is binary: full points if the chosen
    option is correct, 0 otherwise.

    For MULTIPLE-choice questions we use strict scoring: full points only if
    the user selected EXACTLY the set of correct options. No partial credit.
    (We can introduce partial credit later if needed - keeping it simple now.)

    `order` controls the canonical sort order; the *shuffled* order shown to
    each user is stored on the Attempt model (commit 13).
    """

    class QuestionType(models.TextChoices):
        SINGLE = "single", "Single choice"
        MULTIPLE = "multiple", "Multiple choice"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    type = models.CharField(
        max_length=10, choices=QuestionType.choices, default=QuestionType.SINGLE
    )
    points = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Q{self.order}: {self.text[:60]}"

    @property
    def correct_choice_ids(self):
        return frozenset(
            self.choices.filter(is_correct=True).values_list("id", flat=True)
        )


class Choice(models.Model):
    """
    A possible answer to a Question. `is_correct` flags whether selecting this
    choice contributes to a correct answer. Multiple choices can be correct
    for a MULTIPLE-type question; for SINGLE-type, exactly one should be marked
    correct (validated at the form/admin layer, not the DB layer - keeping the
    DB tolerant during quiz construction).
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:60]


class Invitation(models.Model):
    """
    An invitation from a creator to a specific user to take a private quiz.
    A user can be invited to a quiz at most once (enforced by unique_together).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name="invitations"
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_invitations",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations_sent",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("quiz", "invited_user")]

    def __str__(self):
        return f"{self.invited_user} → {self.quiz}"


class JoinRequest(models.Model):
    """
    A user-initiated request to access a private quiz. The quiz's creator
    decides whether to approve.

    A user can have at most one PENDING join request per quiz (DB-enforced).
    Approved/rejected requests are kept as history.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name="join_requests"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_join_requests",
    )
    message = models.CharField(
        max_length=300, blank=True, help_text="Optional note to the creator."
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="join_requests_reviewed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "user"],
                condition=models.Q(status="pending"),
                name="unique_pending_join_request_per_quiz_user",
            ),
        ]

    def __str__(self):
        return f"{self.user} requests {self.quiz}"
