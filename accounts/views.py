from allauth.account.views import EmailView

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.context_processors import DAISY_THEMES
from core.email import send_notification

from .forms import CreatorRequestForm
from .models import CreatorRequest, User, UserPreferences


@login_required
def request_creator_view(request):
    user = request.user

    if user.can_create_quizzes:
        messages.info(request, "You're already a creator.")
        return redirect("core:home")

    pending = user.creator_requests.filter(status=CreatorRequest.Status.PENDING).first()
    if pending:
        return render(
            request,
            "accounts/creator_request_pending.html",
            {"request_obj": pending},
        )

    if request.method == "POST":
        form = CreatorRequestForm(request.POST)
        if form.is_valid():
            cr = form.save(commit=False)
            cr.user = user
            cr.save()
            messages.success(request, "Your creator request has been submitted.")
            return redirect("accounts:creator_status")
    else:
        form = CreatorRequestForm()

    return render(request, "accounts/request_creator.html", {"form": form})


@login_required
def creator_request_status_view(request):
    latest = request.user.creator_requests.order_by("-created_at").first()
    if not latest:
        return redirect("accounts:request_creator")
    return render(
        request,
        "accounts/creator_request_status.html",
        {"request_obj": latest},
    )


@login_required
def creator_requests_admin_view(request):
    if not request.user.is_staff:
        raise PermissionDenied

    pending = (
        CreatorRequest.objects
        .filter(status=CreatorRequest.Status.PENDING)
        .select_related("user")
    )
    reviewed = (
        CreatorRequest.objects
        .exclude(status=CreatorRequest.Status.PENDING)
        .select_related("user", "reviewed_by")
        [:20]
    )
    return render(
        request,
        "accounts/creator_requests_admin.html",
        {"pending": pending, "reviewed": reviewed},
    )


@login_required
@require_POST
def approve_creator_request(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied

    cr = get_object_or_404(CreatorRequest, pk=pk)
    if cr.status != CreatorRequest.Status.PENDING:
        messages.warning(
            request,
            f"Request #{cr.pk} is already {cr.get_status_display().lower()}.",
        )
        return redirect("accounts:creator_requests_admin")

    cr.approve(request.user)
    send_notification(
        recipient=cr.user,
        subject="Your creator request was approved",
        template_base="emails/creator_request_approved",
        context={
            "quizzes_url": request.build_absolute_uri(reverse("quizzes:my_quizzes")),
        },
    )
    messages.success(request, f"Approved {cr.user.username}'s creator request.")
    return redirect("accounts:creator_requests_admin")


@login_required
@require_POST
def reject_creator_request(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied

    cr = get_object_or_404(CreatorRequest, pk=pk)
    if cr.status != CreatorRequest.Status.PENDING:
        messages.warning(
            request,
            f"Request #{cr.pk} is already {cr.get_status_display().lower()}.",
        )
        return redirect("accounts:creator_requests_admin")

    note = request.POST.get("note", "").strip()
    cr.reject(request.user, note=note)
    send_notification(
        recipient=cr.user,
        subject="Your creator request was reviewed",
        template_base="emails/creator_request_rejected",
        context={
            "review_note": cr.review_note,
            "request_again_url": request.build_absolute_uri(reverse("accounts:request_creator")),
        },
    )
    messages.success(request, f"Rejected {cr.user.username}'s creator request.")
    return redirect("accounts:creator_requests_admin")


# ─── Public profile ─────────────────────────────────────────────────────

def creator_profile(request, username):
    """Public profile page for any user with creator privileges.

    Shows their published quizzes — public ones to everyone, plus any private
    ones the viewer has been invited to (the visibility helper handles this).

    Returns 404 (not 403) for non-creators so we don't leak which usernames
    have accounts on the platform.
    """
    profile_user = get_object_or_404(User, username=username)

    has_creator_role = (
        profile_user.is_creator_approved
        or profile_user.role == User.Role.CREATOR
    )
    if not has_creator_role:
        raise Http404

    # Lazy import — keeps the accounts app from depending on the quizzes app at
    # module import time, which simplifies app-level test isolation.
    from quizzes.queries import visible_quizzes
    quizzes = (
        visible_quizzes(request.user)
        .filter(creator=profile_user)
        .order_by("-created_at")
    )

    return render(request, "accounts/creator_profile.html", {
        "profile_user": profile_user,
        "quizzes": quizzes,
        "quiz_count": quizzes.count(),
        "is_own_profile": request.user.is_authenticated and request.user == profile_user,
    })


# ─── Preferences ────────────────────────────────────────────────────────

@login_required
@require_POST
def save_theme_preference(request):
    """Persist the user's chosen daisyUI theme.

    Validates against the curated list in ``DAISY_THEMES`` so we never store
    junk. Returns 204 on success, 400 on invalid input. Client UI relies on
    localStorage for instant feedback; this call is the durable source of
    truth across devices.
    """
    theme = request.POST.get("theme", "").strip()
    if theme not in DAISY_THEMES:
        return HttpResponseBadRequest("Invalid theme")
    prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
    if prefs.theme != theme:
        prefs.theme = theme
        prefs.save(update_fields=["theme", "updated_at"])
    return HttpResponse(status=204)


# ─── Email management ───────────────────────────────────────────────────

class SingleEmailView(EmailView):
    """Variant of allauth's EmailView that enforces 'one email per account'.

    Allauth's default EmailView supports four POST actions: add, remove,
    change_primary, and send (resend verification). We want only `send` to work.

    Anyone who tries to POST add/remove gets a polite redirect with an error
    message — covers the case of a stale browser tab, a direct curl call, or
    a user who somehow finds the (now hidden) form.
    """

    BLOCKED_ACTIONS = {"action_add", "action_remove", "action_primary"}

    def post(self, request, *args, **kwargs):
        # Allauth determines the action by which submit button was clicked,
        # encoded as a key in the request body. Refuse if any blocked action
        # is present.
        if any(key in request.POST for key in self.BLOCKED_ACTIONS):
            messages.error(
                request,
                "QuizHub accounts use a single email address. "
                "Email changes aren't currently supported through this page.",
            )
            return HttpResponseRedirect(reverse("account_email"))

        # action_send (resend verification) is fine — let allauth handle it.
        return super().post(request, *args, **kwargs)

from django.http import HttpResponse
from django.conf import settings
from django.core.mail import send_mail

def email_test(request):
    key = settings.ANYMAIL.get("BREVO_API_KEY", "")
    info = [
        f"backend={settings.EMAIL_BACKEND}",
        f"from={settings.DEFAULT_FROM_EMAIL}",
        f"key_len={len(key)}",
        f"key_prefix={key[:12]}",
    ]
    try:
        n = send_mail("QuizHub test", "hello", None,
                      ["mahdikheireddine2@gmail.com"], fail_silently=False)
        info.append(f"RESULT sent={n}")
    except Exception as e:
        info.append(f"ERROR {type(e).__name__}: {e}")
    return HttpResponse("\n".join(info), content_type="text/plain")