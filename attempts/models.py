"""
Quiz-taking state.

Attempt represents one user's pass through a quiz. We persist the shuffled
question order so the experience is stable across page reloads and resumed
sessions — reshuffling on every render would confuse the user.

Answer stores which choices a user selected for a given question. Scoring
happens at submission time and is cached on the Attempt; we never re-score
on the fly (Quiz contents could change after an Attempt is graded).
"""
from django.conf import settings
from django.db import models

from quizzes.models import Choice, Question, Quiz


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        GRADED = "graded", "Graded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts"
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.IN_PROGRESS
    )

    # JSON list of question IDs in the order this user sees them.
    # Captured at attempt creation, frozen for the attempt's lifetime.
    question_order = models.JSONField(default=list)

    # Scoring — populated at submission time.
    score = models.PositiveIntegerField(default=0)
    max_score = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        # Most queries: "does this user have an in-progress attempt for this quiz?"
        indexes = [
            models.Index(fields=["user", "quiz", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.quiz.title} ({self.get_status_display()})"

    @property
    def is_finished(self):
        return self.status != self.Status.IN_PROGRESS

    @property
    def score_percent(self):
        if self.max_score == 0:
            return 0
        return round(100 * self.score / self.max_score)

    def ordered_questions(self):
        """Return the Question objects in this attempt's shuffled order.
        Loads them in a single query, then re-orders client-side using the JSON list."""
        if not self.question_order:
            return []
        questions = {q.id: q for q in self.quiz.questions.all()}
        return [questions[qid] for qid in self.question_order if qid in questions]

    def get_answer_for(self, question):
        """Returns the user's Answer for the given question, or None."""
        return self.answers.filter(question=question).first()


class Answer(models.Model):
    """The user's selection(s) for one question in one attempt.

    For single-choice questions, exactly one Choice is selected.
    For multiple-choice, zero or more.

    We score this row at submission time by comparing selected_choices to the
    question's correct choices, then store points_earned on this row. That
    way each Answer is auditable on its own.
    """

    attempt = models.ForeignKey(
        Attempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="+")
    selected_choices = models.ManyToManyField(Choice, blank=True, related_name="+")
    points_earned = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("attempt", "question")]

    def __str__(self):
        return f"Answer to Q{self.question_id} in attempt {self.attempt_id}"
