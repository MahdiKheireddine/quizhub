"""Middleware that bridges Django's messages framework to HTMX responses.

When an HTMX request triggers a view that queues a message (e.g., via
``messages.success(request, "Saved")``), the message would normally be stored
in the session and rendered on the next FULL page load. But HTMX requests
don't trigger a full reload — so the message would silently appear hours
later when the user finally navigates away.

This middleware checks every HTMX response, pulls any queued messages, and
serializes them into an ``HX-Trigger`` header. The client-side toast listener
(in ``base.html``) reads the header and fires toasts immediately.
"""

import json

from django.contrib.messages import get_messages


# Map Django's level integers to a short string used by the client toast code.
# (Django's SUCCESS is 25 — not 20 — because it was added later than INFO.)
LEVEL_NAMES = {
    10: "debug",
    20: "info",
    25: "success",
    30: "warning",
    40: "error",
}


def _parse_extra_tags(tags):
    """Parse ``"position:top-end timer:5000"`` style extras into a dict."""
    if not tags:
        return {}
    out = {}
    for chunk in tags.split():
        if ":" in chunk:
            k, v = chunk.split(":", 1)
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                out[k] = v
    return out


class HtmxMessagesMiddleware:
    """Converts queued Django messages into an ``HX-Trigger`` header on HTMX responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not getattr(request, "htmx", False):
            return response

        # Iterate the messages — this also marks them as consumed so they don't
        # re-appear on the next request.
        storage = get_messages(request)
        toasts = []
        for msg in storage:
            toasts.append({
                "level": LEVEL_NAMES.get(msg.level, "info"),
                "message": str(msg.message),
                "extras": _parse_extra_tags(msg.extra_tags),
            })

        if not toasts:
            return response

        # Merge with any existing HX-Trigger payload the view already set
        # (e.g. a view firing a custom event for its own client code).
        existing = response.get("HX-Trigger")
        try:
            payload = json.loads(existing) if existing else {}
            if not isinstance(payload, dict):
                payload = {}
        except json.JSONDecodeError:
            payload = {}
        payload["django-toast"] = toasts
        response["HX-Trigger"] = json.dumps(payload)
        return response