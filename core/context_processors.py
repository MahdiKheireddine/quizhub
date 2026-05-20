from django.apps import apps


def site_meta(request):
    """Expose site-wide context to every template."""
    pending_creator_requests = 0
    if request.user.is_authenticated and request.user.is_staff:
        try:
            CreatorRequest = apps.get_model("accounts", "CreatorRequest")
            pending_creator_requests = CreatorRequest.objects.filter(status="pending").count()
        except LookupError:
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
    }
