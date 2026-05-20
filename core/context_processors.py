def site_meta(request):
    """Expose site-wide context to every template."""
    return {
        "SITE_NAME": "QuizHub",
        # daisyUI themes available in the picker.
        # Must match the `themes` array in theme/static_src/tailwind.config.js
        "DAISY_THEMES": [
            "light", "dark", "dim", "cupcake",
            "synthwave", "dracula", "lemonade",
        ],
    }