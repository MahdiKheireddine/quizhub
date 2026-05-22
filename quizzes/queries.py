"""
Helpers for querying quizzes with the right visibility rules.

Visibility rules for a viewer looking at quizzes:

  - Quizzes must be published (`is_published=True`) — drafts are private to the creator.
  - PUBLIC quizzes are always visible to everyone (logged in or not).
  - PRIVATE quizzes are visible only if the viewer has an Invitation to them
    (any status — even DECLINED — counts; the user has been told it exists).

These helpers do NOT filter by `is_active` or `closes_at` — we want closed
quizzes to remain visible (so people can browse leaderboards). Whether a quiz
accepts new responses is a separate concern handled at quiz-taking time.
"""

from django.db.models import Q

from .models import Quiz


def visible_quizzes(viewer):
    """Base queryset of quizzes a viewer is allowed to see in lists/profiles.

    Used for creator profile pages and direct-link access to private quizzes
    the viewer has been invited to. Will be used in commit 13.
    """
    qs = Quiz.objects.filter(is_published=True).select_related("creator")

    if not viewer.is_authenticated:
        return qs.filter(visibility=Quiz.Visibility.PUBLIC)

    return qs.filter(
        Q(visibility=Quiz.Visibility.PUBLIC)
        | Q(visibility=Quiz.Visibility.PRIVATE, invitations__invited_user=viewer)
    ).distinct()


def public_browse_queryset():
    """Just the public, published quizzes — for the global /q/ browse page.

    Private quizzes never appear here, even if the viewer is invited; they
    surface only via direct link or the inviting creator's profile.
    """
    return (
        Quiz.objects.filter(is_published=True, visibility=Quiz.Visibility.PUBLIC)
        .select_related("creator")
    )


def user_invitation_for(user, quiz):
    """Return the Invitation row for this user + quiz, or None.

    Returns ANY invitation regardless of status (pending/accepted/declined) —
    matches the visibility rule that a user who's been invited at all has
    visibility on the quiz.
    """
    if not user.is_authenticated:
        return None
    return quiz.invitations.filter(invited_user=user).first()


def user_pending_join_request_for(user, quiz):
    """Return the user's PENDING join request for this quiz, or None."""
    if not user.is_authenticated:
        return None
    # Import locally to avoid a circular import at module load time.
    from .models import JoinRequest
    return quiz.join_requests.filter(
        user=user, status=JoinRequest.Status.PENDING
    ).first()


def user_can_access_private_quiz(user, quiz):
    """Whether `user` is allowed access to `quiz`, regardless of whether they've
    taken it yet. Creators of the quiz always count.
    """
    if not user.is_authenticated:
        return False
    if user == quiz.creator:
        return True
    return quiz.invitations.filter(invited_user=user).exists()
