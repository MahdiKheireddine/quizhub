"""Centralized email sending.

All notification emails go through ``send_notification()``. Benefits:
  - One place to add features later (logging, retry, async offload).
  - One place to enforce silent fail in dev / production behavior.
  - Templates live under ``templates/emails/`` in a consistent layout.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_notification(*, recipient, subject, template_base, context):
    """Send a multipart email — best-effort, never raises.

    Email is a side-effect of user actions, not part of the critical path.
    A failure to send (network blip, provider outage, expired API key)
    should be logged but MUST NOT break the user's request.

    ``template_base`` is the name without extension, e.g.
    ``'emails/invitation_received'``. We render ``<base>.txt`` for the plain-text
    part and ``<base>.html`` for the HTML part. Both are required — plain-text
    matters for accessibility and spam scoring.

    Returns True on successful send, False on any failure.
    """
    if not recipient or not recipient.email:
        logger.info("Skipping email: no recipient or no email on %r", recipient)
        return False

    full_context = {**context, "site_name": "QuizHub", "recipient": recipient}

    # Render templates first. If templates are broken we want to know about it
    # in logs (this is our bug, not a provider issue).
    try:
        text_body = render_to_string(f"{template_base}.txt", full_context)
        html_body = render_to_string(f"{template_base}.html", full_context)
    except Exception:
        logger.exception("Failed to render email templates for %s", template_base)
        return False

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient.email],
    )
    msg.attach_alternative(html_body, "text/html")

    # Catch EVERYTHING. Network errors, auth errors, provider 500s, timeouts —
    # none of them should bubble up to the view. Email is best-effort.
    try:
        sent = msg.send(fail_silently=False)
        return bool(sent)
    except Exception:
        logger.exception("Failed to send email to %s (template=%s)",
                         recipient.email, template_base)
        return False