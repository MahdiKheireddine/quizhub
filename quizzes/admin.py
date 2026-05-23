from django.contrib import admin

from .models import Category, Choice, Invitation, JoinRequest, Question, Quiz, Tag


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2
    fields = ("text", "is_correct", "order")


class QuestionInline(admin.StackedInline):
    """Lightweight question inline on the Quiz admin.
    Choices are managed on the dedicated Question admin page since they have
    their own inline."""
    model = Question
    extra = 1
    fields = ("text", "type", "points", "order")
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title", "creator", "category", "visibility", "is_published",
        "is_active", "closes_at", "question_count", "total_points", "created_at",
    )
    list_filter = ("category", "visibility", "is_published", "is_active", "created_at")
    search_fields = ("title", "description", "creator__username")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    inlines = [QuestionInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("creator", "title", "slug", "description")}),
        ("Categorization", {"fields": ("category", "tags")}),
        ("Access", {"fields": ("visibility", "is_published", "is_active", "closes_at")}),
        ("Behavior", {"fields": ("allow_retakes", "show_results_immediately", "pass_score")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "order", "quiz_count")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)

    @admin.display(description="Quizzes")
    def quiz_count(self, obj):
        return obj.quizzes.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "quiz_count", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("created_at",)

    @admin.display(description="Quizzes")
    def quiz_count(self, obj):
        return obj.quizzes.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "quiz", "type", "points", "order")
    list_filter = ("type", "quiz")
    search_fields = ("text", "quiz__title")
    inlines = [ChoiceInline]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("quiz", "invited_user", "status", "invited_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("quiz__title", "invited_user__username")
    readonly_fields = ("created_at", "responded_at")


@admin.register(JoinRequest)
class JoinRequestAdmin(admin.ModelAdmin):
    list_display = ("quiz", "user", "status", "reviewed_by", "created_at", "reviewed_at")
    list_filter = ("status", "created_at")
    search_fields = ("quiz__title", "user__username")
    readonly_fields = ("created_at", "reviewed_at")