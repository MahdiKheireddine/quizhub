# production.py — production settings.
from .base import *  # noqa: F401,F403
from config.env import env

# Force DEBUG off in production regardless of env, as a safety override.
DEBUG = False

# ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS are already read from env in base.py
# (DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS).

# ─── Email (Brevo HTTP API via Anymail) ──────────────────────────────────
# Render's free tier blocks outbound SMTP (port 587), so we send via Brevo's
# HTTP API instead. The API key is set in Render's dashboard, not in this file.
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
ANYMAIL = {
    "BREVO_API_KEY": env("ANYMAIL_BREVO_API_KEY", default=""),
}

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