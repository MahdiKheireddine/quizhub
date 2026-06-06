"""Helper to determine which social providers are configured (have a SocialApp
row in the database) so templates can conditionally show only the buttons
that will actually work.

This is a deliberate design choice: rather than crashing or rendering a
broken button when keys aren't set, we silently hide the button. Lets the
project run cleanly for anyone who clones the repo without their own keys.
"""

from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site

User = get_user_model()


def get_configured_providers():
    """Return a list of dicts describing the social providers that are ready
    to use. Each dict has 'id' (provider id like 'google') and 'name' (display).
    """
    from allauth.socialaccount.models import SocialApp

    try:
        current_site = Site.objects.get_current()
    except Site.DoesNotExist:
        return []

    apps = SocialApp.objects.filter(sites=current_site)
    display_names = {"google": "Google", "facebook": "Facebook"}
    return [
        {
            "id": app.provider,
            "name": display_names.get(app.provider, app.provider.title()),
        }
        for app in apps
    ]


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social-account adapter.

    Purpose: when a social login (Google, Facebook, etc.) comes in with a
    verified email that matches an existing local user, automatically link
    the social account to that user instead of refusing with 'email already
    in use'.

    Security: we only auto-link when the SOCIAL PROVIDER tells us the email
    is verified. Google always does. Facebook only does when we ask for it
    (SOCIALACCOUNT_PROVIDERS.facebook.VERIFIED_EMAIL = True, which we set).
    Providers that don't verify emails fall through to allauth's default
    behavior (refuse), which is the safer choice.
    """

    def pre_social_login(self, request, sociallogin):
        # Already connected — nothing to do, allauth handles the login.
        if sociallogin.is_existing:
            return

        # No email on the social account — can't auto-link, allauth proceeds
        # to ask the user to provide one (or fails, depending on config).
        if not sociallogin.email_addresses:
            return

        # Use the social account's primary email
        primary_email = next(
            (e for e in sociallogin.email_addresses if e.primary),
            sociallogin.email_addresses[0],
        )

        # Only auto-link if the provider has verified this email. If they
        # haven't, fall through to allauth's default ("email in use" error)
        # — safer, prevents email-spoofing account takeover.
        if not primary_email.verified:
            return

        # Look for an existing user with this email. Use EmailAddress (the
        # canonical record allauth maintains) rather than User.email
        # directly, since allauth supports multiple emails per user.
        try:
            existing = EmailAddress.objects.get(
                email__iexact=primary_email.email,
                verified=True,
            )
        except EmailAddress.DoesNotExist:
            # Maybe the user has the email but never verified it locally.
            # We can still link safely because the SOCIAL provider verified
            # it — meaning the user controls this email address.
            try:
                user = User.objects.get(email__iexact=primary_email.email)
            except User.DoesNotExist:
                # No local user at all — let allauth create a new account.
                return
        else:
            user = existing.user

        # Connect the social account to the existing user. This is the
        # "magic" line — it tells allauth to attach instead of creating new.
        sociallogin.connect(request, user)

        # Friendly UX touch — let the user know we linked their accounts.
        messages.success(
            request,
            f"Linked your {sociallogin.account.get_provider_account().get_brand()['name']} "
            f"account to your existing QuizHub account.",
        )