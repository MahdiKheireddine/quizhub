from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import QuizForm
from .models import Quiz


def _require_creator(user):
    """Raise PermissionDenied if user can't create quizzes."""
    if not user.is_authenticated:
        raise PermissionDenied
    if not user.can_create_quizzes:
        raise PermissionDenied


def _get_own_quiz(user, slug):
    """Fetch a quiz the user owns or raise 404. Defends against URL guessing."""
    return get_object_or_404(Quiz, slug=slug, creator=user)


@login_required
def my_quizzes(request):
    """Creator dashboard — list of the user's own quizzes."""
    _require_creator(request.user)
    quizzes = Quiz.objects.filter(creator=request.user).order_by("-updated_at")
    return render(request, "quizzes/my_quizzes.html", {"quizzes": quizzes})


@login_required
def quiz_create(request):
    _require_creator(request.user)
    if request.method == "POST":
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.creator = request.user
            quiz.is_published = False  # always start as draft
            quiz.save()
            messages.success(
                request,
                f"Quiz '{quiz.title}' created as a draft. Add questions next.",
            )
            return redirect("quizzes:detail", slug=quiz.slug)
    else:
        form = QuizForm()
    return render(request, "quizzes/quiz_form.html", {"form": form, "mode": "create"})


@login_required
def quiz_detail(request, slug):
    """Creator's view of their own quiz. Public/take-quiz view comes in commit 12."""
    quiz = _get_own_quiz(request.user, slug)
    return render(request, "quizzes/quiz_detail.html", {"quiz": quiz})


@login_required
def quiz_edit(request, slug):
    quiz = _get_own_quiz(request.user, slug)
    if request.method == "POST":
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, "Quiz updated.")
            return redirect("quizzes:detail", slug=quiz.slug)
    else:
        form = QuizForm(instance=quiz)
    return render(
        request,
        "quizzes/quiz_form.html",
        {"form": form, "mode": "edit", "quiz": quiz},
    )


@login_required
def quiz_delete(request, slug):
    quiz = _get_own_quiz(request.user, slug)
    if request.method == "POST":
        title = quiz.title
        quiz.delete()
        messages.success(request, f"Deleted '{title}'.")
        return redirect("quizzes:my_quizzes")
    return render(request, "quizzes/quiz_delete.html", {"quiz": quiz})


@login_required
@require_POST
def quiz_toggle_publish(request, slug):
    """POST-only action button that flips the draft/published state."""
    quiz = _get_own_quiz(request.user, slug)

    if not quiz.is_published:
        # Refuse to publish a quiz with no questions.
        if quiz.question_count == 0:
            messages.error(request, "Add at least one question before publishing.")
            return redirect("quizzes:detail", slug=quiz.slug)
        quiz.is_published = True
        quiz.save(update_fields=["is_published", "updated_at"])
        messages.success(request, f"'{quiz.title}' is now published.")
    else:
        quiz.is_published = False
        quiz.save(update_fields=["is_published", "updated_at"])
        messages.info(request, f"'{quiz.title}' is back to draft.")

    return redirect("quizzes:detail", slug=quiz.slug)


@login_required
@require_POST
def quiz_toggle_active(request, slug):
    """POST-only action button that flips is_active."""
    quiz = _get_own_quiz(request.user, slug)
    quiz.is_active = not quiz.is_active
    quiz.save(update_fields=["is_active", "updated_at"])
    if quiz.is_active:
        messages.success(request, "Quiz is now accepting responses.")
    else:
        messages.info(request, "Quiz has been paused.")
    return redirect("quizzes:detail", slug=quiz.slug)