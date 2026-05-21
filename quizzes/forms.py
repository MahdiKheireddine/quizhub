from django import forms
from django.utils import timezone

from .models import Choice, Question, Quiz


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
            "title", "description", "visibility",
            "is_active", "closes_at",
            "allow_retakes", "show_results_immediately", "pass_score",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Django ORM basics", "maxlength": 200,
            }),
            "description": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 4,
                "placeholder": "Optional. What's this quiz about?",
            }),
            "visibility": forms.Select(attrs={"class": SELECT}),
            "closes_at": forms.DateTimeInput(
                attrs={"class": INPUT, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "allow_retakes": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "show_results_immediately": forms.CheckboxInput(attrs={"class": CHECKBOX}),
            "pass_score": forms.NumberInput(attrs={
                "class": INPUT, "min": 0, "max": 100, "placeholder": "e.g. 70",
            }),
        }
        labels = {
            "is_active": "Currently accepting responses",
            "closes_at": "Auto-close date (optional)",
            "allow_retakes": "Allow users to retake this quiz",
            "show_results_immediately": "Show users their score immediately after submitting",
            "pass_score": "Pass score (%)",
        }
        help_texts = {
            "visibility": "Public quizzes are visible to all users. Private ones require invitation or approval.",
            "closes_at": "Leave blank for no auto-close. After this datetime the quiz stops accepting responses.",
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
