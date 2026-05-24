"""Helper to determine which social providers are configured (have a SocialApp
row in the database) so templates can conditionally show only the buttons
that will actually work.

This is a deliberate design choice: rather than crashing or rendering a
broken button when keys aren't set, we silently hide the button. Lets the
project run cleanly for anyone who clones the repo without their own keys.
"""

from django.contrib.sites.models import Site


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