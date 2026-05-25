import json

from django.apps import apps
from django.conf import settings

from accounts.social import get_configured_providers


def site_meta(request):
    """Expose site-wide context to every template."""
    pending_creator_requests = 0
    if request.user.is_authenticated and request.user.is_staff:
        try:
            CreatorRequest = apps.get_model("accounts", "CreatorRequest")
            pending_creator_requests = CreatorRequest.objects.filter(status="pending").count()
        except LookupError:
            pass

    # Defensive: never let a broken provider lookup break every page render.
    configured_providers = []
    try:
        configured_providers = get_configured_providers()
    except Exception:
        pass

    return {
        "SITE_NAME": "QuizHub",
        # daisyUI themes available in the picker.
        # Must match the `themes` array in theme/static_src/src/styles.css
        "DAISY_THEMES": [
            "light", "dark", "dim", "cupcake",
            "synthwave", "dracula", "lemonade",
        ],
        "pending_creator_requests": pending_creator_requests,
        "configured_social_providers": configured_providers,
        # Toast config (defaults) — JSON-serialized here so the template can
        # inject it as a valid JS literal. Plain `{{ dict|safe }}` would render
        # Python's repr (True/False capitalized), which is a JS SyntaxError.
        "toast_defaults": json.dumps(getattr(settings, "TOAST_DEFAULTS", {})),
    }
