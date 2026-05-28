# local.py — development settings.
from .base import *  # noqa: F401,F403

# Print emails to the runserver terminal instead of sending them.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# django-browser-reload: auto-refresh the page when templates/static files change.
INSTALLED_APPS += ["django_browser_reload"]
MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]