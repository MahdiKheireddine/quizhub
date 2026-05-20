from django import forms

from .models import CreatorRequest


class CreatorRequestForm(forms.ModelForm):
    class Meta:
        model = CreatorRequest
        fields = ["reason"]
        widgets = {
            "reason": forms.Textarea(attrs={
                "class": "textarea w-full",
                "rows": 5,
                "placeholder": "Tell us why you'd like to create quizzes. What kind of quizzes would you build? (max 500 chars)",
                "maxlength": 500,
            }),
        }
        labels = {"reason": "Why do you want to create quizzes?"}

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 20:
            raise forms.ValidationError(
                "Please write at least 20 characters so we can review your request meaningfully."
            )
        return reason
