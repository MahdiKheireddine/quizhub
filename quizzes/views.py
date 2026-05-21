from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_http_methods

from .forms import ChoiceForm, QuestionForm, QuizForm
from .models import Choice, Question, Quiz


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


# ─── Question editor (HTMX) ─────────────────────────────────────────────

def _get_own_question(user, question_id):
    return get_object_or_404(Question, id=question_id, quiz__creator=user)


def _get_own_choice(user, choice_id):
    return get_object_or_404(Choice, id=choice_id, question__quiz__creator=user)


@login_required
def edit_questions(request, slug):
    """Full-page question editor for a quiz."""
    quiz = _get_own_quiz(request.user, slug)
    return render(request, "quizzes/edit_questions.html", {
        "quiz": quiz,
        "question_form": QuestionForm(),
    })


# Question CRUD via HTMX ────────────────────────────────────────────────

@login_required
@require_POST
def question_create(request, slug):
    quiz = _get_own_quiz(request.user, slug)
    form = QuestionForm(request.POST)
    if not form.is_valid():
        # Re-render the form with errors via OOB swap so the visible form picks up the errors.
        return render(request, "quizzes/partials/new_question_form_oob.html", {
            "quiz": quiz, "question_form": form,
        })
    q = form.save(commit=False)
    q.quiz = quiz
    q.order = (quiz.questions.aggregate(m=Max("order"))["m"] or 0) + 1
    q.save()

    # Two fragments in one response:
    #  1. The full re-rendered question list (replaces #question-list innerHTML)
    #     — re-rendering the whole list is cheap and avoids the empty-state
    #       sticking around after the first add (vs. beforeend with one card).
    #  2. A fresh empty form via OOB swap that replaces #new-question-form.
    html = render_to_string("quizzes/partials/question_list.html",
                            {"quiz": quiz}, request=request)
    html += render_to_string("quizzes/partials/new_question_form_oob.html",
                             {"quiz": quiz, "question_form": QuestionForm()},
                             request=request)
    return HttpResponse(html)


@login_required
@require_POST
def question_update(request, question_id):
    q = _get_own_question(request.user, question_id)
    form = QuestionForm(request.POST, instance=q)
    if form.is_valid():
        form.save()
    return render(request, "quizzes/partials/question_card.html", {
        "q": q, "quiz": q.quiz,
    })


@login_required
@require_http_methods(["DELETE"])
def question_delete(request, question_id):
    q = _get_own_question(request.user, question_id)
    q.delete()
    # HTMX hx-swap="delete" will remove the target; return 200 with empty body.
    return HttpResponse("")


@login_required
@require_POST
def question_move(request, question_id, direction):
    """Swap order with the upper/lower neighbor. direction is 'up' or 'down'."""
    q = _get_own_question(request.user, question_id)
    siblings = list(q.quiz.questions.order_by("order", "id"))
    idx = next((i for i, x in enumerate(siblings) if x.id == q.id), None)
    if idx is None:
        return HttpResponse("")
    if direction == "up" and idx > 0:
        neighbor = siblings[idx - 1]
    elif direction == "down" and idx < len(siblings) - 1:
        neighbor = siblings[idx + 1]
    else:
        # Already at the edge — re-render the list so any optimistic UI state resets.
        return render(request, "quizzes/partials/question_list.html", {"quiz": q.quiz})

    with transaction.atomic():
        q.order, neighbor.order = neighbor.order, q.order
        q.save(update_fields=["order"])
        neighbor.save(update_fields=["order"])
    return render(request, "quizzes/partials/question_list.html", {"quiz": q.quiz})


# Choice CRUD via HTMX ──────────────────────────────────────────────────

@login_required
@require_POST
def choice_create(request, question_id):
    q = _get_own_question(request.user, question_id)
    form = ChoiceForm(request.POST)
    if not form.is_valid():
        return render(request, "quizzes/partials/choices_list.html", {
            "q": q, "choice_form_errors": form.errors,
        })
    c = form.save(commit=False)
    c.question = q
    c.order = (q.choices.aggregate(m=Max("order"))["m"] or 0) + 1
    c.save()
    return render(request, "quizzes/partials/choices_list.html", {"q": q})


@login_required
@require_POST
def choice_update(request, choice_id):
    c = _get_own_choice(request.user, choice_id)
    form = ChoiceForm(request.POST, instance=c)
    if form.is_valid():
        form.save()
    return render(request, "quizzes/partials/choices_list.html", {"q": c.question})


@login_required
@require_POST
def choice_toggle_correct(request, choice_id):
    """One-click toggle: flip is_correct via HTMX."""
    c = _get_own_choice(request.user, choice_id)
    c.is_correct = not c.is_correct
    c.save(update_fields=["is_correct"])

    # For 'single'-type questions, marking one correct should unmark the others.
    # Enforced server-side so the UI doesn't have to know the rule.
    if c.is_correct and c.question.type == Question.QuestionType.SINGLE:
        c.question.choices.exclude(id=c.id).update(is_correct=False)

    return render(request, "quizzes/partials/choices_list.html", {"q": c.question})


@login_required
@require_http_methods(["DELETE"])
def choice_delete(request, choice_id):
    c = _get_own_choice(request.user, choice_id)
    question = c.question
    c.delete()
    return render(request, "quizzes/partials/choices_list.html", {"q": question})