from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Choice, Invitation, JoinRequest, Question, Quiz, Tag

User = get_user_model()


# Reusable daisyUI v5 classes. `input`, `textarea`, `select` are bordered by
# default in v5 — the `-bordered` modifier was removed.
INPUT = "input w-full"
TEXTAREA = "textarea w-full"
SELECT = "select w-full"
CHECKBOX = "checkbox checkbox-primary"


class QuizForm(forms.ModelForm):
    """Create/edit form for a Quiz. Used by both `quiz_create` and `quiz_edit` views."""

    class Meta:
        model = Quiz
        fields = [
            "title", "description", "category",
            # tags handled separately via the tags_raw CharField below
            "visibility",
            "is_active", "closes_at", "time_limit_minutes",
            "allow_retakes", "show_results_immediately", "results_released_at", "pass_score",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Django ORM basics", "maxlength": 200,
            }),
            "description": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 4,
                "placeholder": "Optional. What's this quiz about?",
            }),
            "category": forms.Select(attrs={"class": SELECT}),
            "visibility": forms.Select(attrs={"class": SELECT}),
            "closes_at": forms.DateTimeInput(
                attrs={"class": INPUT, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "results_released_at": forms.DateTimeInput(
                attrs={"class": INPUT, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "allow_retakes": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "show_results_immediately": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "pass_score": forms.NumberInput(attrs={
                "class": INPUT, "min": 0, "max": 100, "placeholder": "e.g. 70",
            }),
            "time_limit_minutes": forms.NumberInput(attrs={
                "class": INPUT, "min": 1, "max": 480, "placeholder": "e.g. 30",
            }),
        }
        labels = {
            "category": "Category",
            "is_active": "Currently accepting responses",
            "closes_at": "Auto-close date (optional)",
            "allow_retakes": "Allow users to retake this quiz",
            "show_results_immediately": "Show users their score immediately after submitting",
            "pass_score": "Pass score (%)",
            "time_limit_minutes": "Time limit (minutes, optional)",
            "results_released_at": "Results released at (optional)",
        }
        help_texts = {
            "visibility": "Public quizzes are visible to all users. Private ones require invitation or approval.",
            "closes_at": "Leave blank for no auto-close. After this datetime the quiz stops accepting responses.",
            "time_limit_minutes": (
                "Total time for the whole quiz. Counter starts when the user begins. "
                "Leave blank for no time limit."
            ),
            "results_released_at": (
                "If 'Show results immediately' is off, set this to reveal scores to participants. "
                "Leave blank to keep results hidden. The 'Release results' button on the quiz page "
                "sets this to now in one click."
            ),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Title must be at least 3 characters.")
        return title

    def clean_closes_at(self):
        closes_at = self.cleaned_data.get("closes_at")
        if closes_at and closes_at <= timezone.now():
            raise forms.ValidationError("Auto-close date must be in the future.")
        return closes_at

    def clean_pass_score(self):
        ps = self.cleaned_data.get("pass_score")
        if ps is not None and (ps < 0 or ps > 100):
            raise forms.ValidationError("Pass score must be between 0 and 100.")
        return ps

    def clean_time_limit_minutes(self):
        val = self.cleaned_data.get("time_limit_minutes")
        if val is not None and (val < 1 or val > 480):
            raise forms.ValidationError(
                "Time limit must be between 1 and 480 minutes (8 hours)."
            )
        return val

    # ── Tags (free-form, comma-separated) ────────────────────────────────
    # NOT a ModelForm field — we accept a comma-separated string and resolve
    # to Tag objects ourselves so we can normalize and create-on-the-fly.
    tags_raw = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": INPUT,
            "placeholder": "e.g. django, web, beginner (comma-separated)",
            "autocomplete": "off",
        }),
        label="Tags",
        help_text="Up to 8 tags. Lowercase. Letters, numbers, hyphens only.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prefill tags_raw from the existing instance, if editing.
        if self.instance and self.instance.pk:
            existing = self.instance.tags.values_list("name", flat=True)
            self.fields["tags_raw"].initial = ", ".join(existing)

    def clean_tags_raw(self):
        raw = self.cleaned_data.get("tags_raw", "").strip()
        if not raw:
            return []
        parts = [p for p in (s.strip() for s in raw.split(",")) if p]
        if len(parts) > 8:
            raise forms.ValidationError("Up to 8 tags per quiz.")
        tags = []
        seen_slugs = set()
        for raw_tag in parts:
            tag = Tag.from_string(raw_tag)
            if tag is None:
                raise forms.ValidationError(f"'{raw_tag}' is not a valid tag.")
            if tag.slug in seen_slugs:
                continue  # dedupe within this form (e.g. "Django, django" → 1)
            seen_slugs.add(tag.slug)
            tags.append(tag)
        return tags

    def save(self, commit=True):
        """Save the Quiz then attach tags.

        For NEW quizzes the caller is responsible for assigning .creator on the
        commit=False instance and then calling .save() before any M2M attaches.
        See `quiz_create` in views.py.
        """
        quiz = super().save(commit=commit)
        if commit:
            quiz.tags.set(self.cleaned_data.get("tags_raw", []))
        return quiz


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "type", "points"]
        widgets = {
            "text": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 2,
                "placeholder": "Question text",
            }),
            "type": forms.Select(attrs={"class": "select select-sm"}),
            "points": forms.NumberInput(attrs={
                "class": "input input-sm w-20", "min": 1, "max": 100,
            }),
        }

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 3:
            raise forms.ValidationError("Question is too short.")
        return text


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ["text", "is_correct"]
        widgets = {
            "text": forms.TextInput(attrs={
                "class": "input input-sm w-full",
                "placeholder": "Choice text",
            }),
            "is_correct": forms.CheckboxInput(attrs={"class": CHECKBOX}),
        }

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if not text:
            raise forms.ValidationError("Choice cannot be empty.")
        return text


class InviteUserForm(forms.Form):
    """Creator side: invite someone by username to take a private quiz."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": INPUT,
            "placeholder": "Username",
            "autocomplete": "off",
        }),
    )

    def __init__(self, *args, quiz=None, **kwargs):
        self.quiz = quiz
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No user with that username.")
        if self.quiz and user == self.quiz.creator:
            raise forms.ValidationError("You can't invite yourself to your own quiz.")
        if self.quiz and Invitation.objects.filter(quiz=self.quiz, invited_user=user).exists():
            raise forms.ValidationError(f"{user.username} is already invited.")
        self.cleaned_data["user"] = user
        return username


class JoinRequestForm(forms.ModelForm):
    """User side: request access to a private quiz with an optional message."""

    class Meta:
        model = JoinRequest
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 3,
                "placeholder": "Optional: a short note to the creator (why you want to take this quiz).",
                "maxlength": 300,
            }),
        }
        labels = {"message": "Message (optional)"}
