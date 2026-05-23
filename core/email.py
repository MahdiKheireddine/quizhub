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
    """Send a multipart email using two templates.

    ``template_base`` is the name without extension, e.g.
    ``'emails/invitation_received'``. We render ``<base>.txt`` for the plain-text
    part and ``<base>.html`` for the HTML part. Both are required — plain-text
    matters for accessibility and spam scoring.

    Silent failure: if the recipient has no email (rare with allauth, but
    possible), we log and return False. Callers don't need to check; email is
    fire-and-forget.
    """
    if not recipient or not recipient.email:
        logger.info("Skipping email: no recipient or no email on %r", recipient)
        return False

    full_context = {**context, "site_name": "QuizHub", "recipient": recipient}

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

    try:
        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", recipient.email)
        return False