# production.py — production settings.
from .base import *  # noqa: F401,F403
from config.env import env

# Force DEBUG off in production regardless of env, as a safety override.
DEBUG = False

# ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS are already read from env in base.py
# (DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS).

# ─── Email (Gmail SMTP) ──────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# ─── Security headers ────────────────────────────────────────────────────
# Tell Django it's behind an HTTPS-terminating proxy (Render's load balancer).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookies only over HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Strict transport security — tells browsers to only use HTTPS for a year.
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Redirect HTTP to HTTPS at the Django level (belt-and-suspenders; Render does
# this too, but it's free defense in depth).
SECURE_SSL_REDIRECT = True

# Disallow embedding (clickjacking).
X_FRAME_OPTIONS = "DENY"