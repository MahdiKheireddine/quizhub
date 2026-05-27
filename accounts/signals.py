"""Auto-create ``UserPreferences`` whenever a new User is created.

Registered in ``accounts/apps.py``'s ``ready()`` so it's loaded once at app
startup. Using ``get_or_create`` defends against the edge case where the
backfill migration ran for an existing user and a duplicate `created=True`
signal could otherwise IntegrityError.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserPreferences


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_preferences(sender, instance, created, **kwargs):
    if not created:
        return
    UserPreferences.objects.get_or_create(user=instance)