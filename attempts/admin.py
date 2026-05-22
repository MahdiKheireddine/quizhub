from django.contrib import admin

from .models import Answer, Attempt


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = (
        "question",
        "selected_choices_display",
        "points_earned",
        "is_correct",
        "answered_at",
    )
    fields = (
        "question",
        "selected_choices_display",
        "points_earned",
        "is_correct",
    )
    can_delete = False

    def selected_choices_display(self, obj):
        return ", ".join(c.text for c in obj.selected_choices.all())
    selected_choices_display.short_description = "Selected choices"


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "quiz",
        "status",
        "score",
        "max_score",
        "score_percent",
        "started_at",
        "submitted_at",
    )
    list_filter = ("status", "quiz", "started_at")
    search_fields = ("user__username", "quiz__title")
    readonly_fields = (
        "user",
        "quiz",
        "question_order",
        "started_at",
        "submitted_at",
        "graded_at",
        "score",
        "max_score",
    )
    inlines = [AnswerInline]
