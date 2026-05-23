from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from core.pagination import paginate

from .forms import ChoiceForm, InviteUserForm, JoinRequestForm, QuestionForm, QuizForm
from .models import Category, Choice, Invitation, JoinRequest, Question, Quiz, Tag
from .queries import (
    public_browse_queryset,
    user_can_access_private_quiz,
    user_pending_join_request_for,
    visible_quizzes,
)


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
            # Quiz now has a pk; attach tags collected by the form.
            quiz.tags.set(form.cleaned_data.get("tags_raw", []))
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
    pending_join_requests_count = quiz.join_requests.filter(
        status=JoinRequest.Status.PENDING
    ).count()
    return render(request, "quizzes/quiz_detail.html", {
        "quiz": quiz,
        "pending_join_requests_count": pending_join_requests_count,
    })


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


# ─── Public browse + detail ─────────────────────────────────────────────

def browse_quizzes(request):
    """Public list of all published public quizzes. No auth required."""
    qs = (
        public_browse_queryset()
        .select_related("category")
        .prefetch_related("tags")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    category_slug = request.GET.get("category", "").strip()
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    tag_slug = request.GET.get("tag", "").strip()
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug)

    sort = request.GET.get("sort", "recent")
    if sort == "popular":
        qs = qs.annotate(invites=Count("invitations")).order_by("-invites", "-created_at")
    elif sort == "alpha":
        qs = qs.order_by("title")
    else:
        qs = qs.order_by("-created_at")

    # .distinct() must come BEFORE pagination — filtering by tags__slug does a
    # JOIN, which would multi-count quizzes with many tags and inflate the
    # paginator's count and page sizes.
    qs = qs.distinct()
    page_obj, querystring_no_page, page_range = paginate(qs, request, per_page=24)

    # Category strip with quiz counts for the filter UI.
    categories = Category.objects.annotate(num=Count("quizzes")).order_by("order")

    # Active filter objects (for breadcrumb-style chips in the template).
    active_category = (
        Category.objects.filter(slug=category_slug).first() if category_slug else None
    )
    active_tag = Tag.objects.filter(slug=tag_slug).first() if tag_slug else None

    return render(request, "quizzes/browse.html", {
        "quizzes": page_obj.object_list,
        "page_obj": page_obj,
        "querystring_no_page": querystring_no_page,
        "page_range": page_range,
        "q": q,
        "sort": sort,
        "categories": categories,
        "active_category": active_category,
        "active_tag": active_tag,
    })


def public_quiz_detail(request, slug):
    """Public detail view for one quiz.

    Visibility rule for this view (more permissive than `visible_quizzes`, which
    is used for listing contexts like profile pages):
      - Public + published → visible to everyone.
      - Private + published → visible to any authenticated viewer; the sidebar
        UI shows the right action (Take quiz / Request access / pending).
      - Private + anonymous → 404, so we don't leak that the quiz exists.
    Drafts always 404 here regardless of viewer.
    """
    quiz = get_object_or_404(
        Quiz.objects.filter(is_published=True).select_related("creator"),
        slug=slug,
    )
    if quiz.visibility == Quiz.Visibility.PRIVATE and not request.user.is_authenticated:
        raise Http404

    return render(request, "quizzes/public_detail.html", {
        "quiz": quiz,
        "user_can_access": user_can_access_private_quiz(request.user, quiz),
        "user_pending_request": user_pending_join_request_for(request.user, quiz),
    })


# ─── Invitations & join requests: creator side ──────────────────────────

@login_required
def quiz_invitations(request, slug):
    """Creator-only page to manage invitations + join requests for a quiz."""
    quiz = _get_own_quiz(request.user, slug)

    if request.method == "POST":
        form = InviteUserForm(request.POST, quiz=quiz)
        if form.is_valid():
            user = form.cleaned_data["user"]
            Invitation.objects.create(
                quiz=quiz,
                invited_user=user,
                invited_by=request.user,
                status=Invitation.Status.PENDING,
            )
            messages.success(request, f"Invited {user.username}.")
            return redirect("quizzes:quiz_invitations", slug=quiz.slug)
    else:
        form = InviteUserForm(quiz=quiz)

    invitations = (
        quiz.invitations
        .select_related("invited_user", "invited_by")
        .order_by("-created_at")
    )
    pending_requests = (
        quiz.join_requests
        .filter(status=JoinRequest.Status.PENDING)
        .select_related("user")
    )
    recent_reviewed = (
        quiz.join_requests
        .exclude(status=JoinRequest.Status.PENDING)
        .select_related("user", "reviewed_by")
        .order_by("-reviewed_at")[:10]
    )

    return render(request, "quizzes/quiz_invitations.html", {
        "quiz": quiz,
        "form": form,
        "invitations": invitations,
        "pending_requests": pending_requests,
        "recent_reviewed": recent_reviewed,
    })


@login_required
@require_POST
def invitation_cancel(request, invitation_id):
    inv = get_object_or_404(
        Invitation.objects.select_related("quiz"),
        id=invitation_id,
        quiz__creator=request.user,
    )
    quiz = inv.quiz
    invited_username = inv.invited_user.username
    inv.delete()
    messages.info(request, f"Invitation for {invited_username} cancelled.")
    return redirect("quizzes:quiz_invitations", slug=quiz.slug)


@login_required
@require_POST
def join_request_review(request, join_request_id, action):
    """Approve or reject a pending join request. Only the quiz's creator can act."""
    jr = get_object_or_404(
        JoinRequest.objects.select_related("quiz", "user"),
        id=join_request_id,
        quiz__creator=request.user,
    )
    if jr.status != JoinRequest.Status.PENDING:
        messages.error(request, "This request has already been resolved.")
        return redirect("quizzes:quiz_invitations", slug=jr.quiz.slug)

    if action == "approve":
        with transaction.atomic():
            jr.status = JoinRequest.Status.APPROVED
            jr.reviewed_by = request.user
            jr.reviewed_at = timezone.now()
            jr.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            # Grant access by creating an ACCEPTED invitation if one doesn't exist.
            Invitation.objects.get_or_create(
                quiz=jr.quiz,
                invited_user=jr.user,
                defaults={
                    "invited_by": request.user,
                    "status": Invitation.Status.ACCEPTED,
                    "responded_at": timezone.now(),
                },
            )
        messages.success(request, f"Approved {jr.user.username}'s request.")
    elif action == "reject":
        jr.status = JoinRequest.Status.REJECTED
        jr.reviewed_by = request.user
        jr.reviewed_at = timezone.now()
        jr.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        messages.info(request, f"Rejected {jr.user.username}'s request.")
    else:
        messages.error(request, "Invalid action.")

    return redirect("quizzes:quiz_invitations", slug=jr.quiz.slug)


# ─── Invitations & join requests: user side ─────────────────────────────

@login_required
def my_invitations(request):
    """User's incoming invitations."""
    invitations = (
        request.user.quiz_invitations
        .select_related("quiz", "quiz__creator", "invited_by")
        .order_by("-created_at")
    )
    return render(request, "quizzes/my_invitations.html", {"invitations": invitations})


@login_required
@require_POST
def invitation_respond(request, invitation_id, action):
    """User accepts or declines their own invitation."""
    inv = get_object_or_404(Invitation, id=invitation_id, invited_user=request.user)

    if action == "accept":
        inv.status = Invitation.Status.ACCEPTED
    elif action == "decline":
        inv.status = Invitation.Status.DECLINED
    else:
        messages.error(request, "Invalid action.")
        return redirect("quizzes:my_invitations")

    inv.responded_at = timezone.now()
    inv.save(update_fields=["status", "responded_at"])
    messages.success(request, f"Invitation {action}ed.")
    return redirect("quizzes:my_invitations")


@login_required
def my_join_requests(request):
    """User's outgoing join requests."""
    requests_qs = (
        request.user.quiz_join_requests
        .select_related("quiz", "quiz__creator", "reviewed_by")
        .order_by("-created_at")
    )
    return render(request, "quizzes/my_join_requests.html", {"join_requests": requests_qs})


@login_required
def request_join(request, slug):
    """User-side: request access to a private quiz."""
    quiz = get_object_or_404(
        Quiz,
        slug=slug,
        is_published=True,
        visibility=Quiz.Visibility.PRIVATE,
    )

    if user_can_access_private_quiz(request.user, quiz):
        messages.info(request, "You already have access to this quiz.")
        return redirect("quizzes:public_detail", slug=quiz.slug)

    if user_pending_join_request_for(request.user, quiz):
        messages.info(request, "You already have a pending request for this quiz.")
        return redirect("quizzes:my_join_requests")

    if request.method == "POST":
        form = JoinRequestForm(request.POST)
        if form.is_valid():
            jr = form.save(commit=False)
            jr.quiz = quiz
            jr.user = request.user
            jr.save()
            messages.success(
                request,
                "Request sent. You'll be notified when the creator responds.",
            )
            return redirect("quizzes:my_join_requests")
    else:
        form = JoinRequestForm()

    return render(request, "quizzes/request_join.html", {"quiz": quiz, "form": form})


@login_required
@require_POST
def quiz_release_results(request, slug):
    """One-way action: release results to all participants for a quiz that
    wasn't showing them immediately. Idempotent — re-clicking does nothing."""
    quiz = _get_own_quiz(request.user, slug)
    if quiz.results_released_at is None:
        quiz.results_released_at = timezone.now()
        quiz.save(update_fields=["results_released_at", "updated_at"])
        messages.success(
            request,
            f"Results released for '{quiz.title}'. Participants can now see their scores.",
        )
    else:
        messages.info(request, "Results were already released.")
    return redirect("quizzes:detail", slug=quiz.slug)