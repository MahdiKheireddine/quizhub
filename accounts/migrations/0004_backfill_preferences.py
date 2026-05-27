"""Backfill ``UserPreferences`` rows for users who existed before this commit.

The ``post_save`` signal in ``accounts/signals.py`` covers users created from
now on. This migration covers users that pre-date the signal so
``user.preferences`` is always present on every existing row.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserPreferences = apps.get_model("accounts", "UserPreferences")
    existing_user_ids = set(
        UserPreferences.objects.values_list("user_id", flat=True)
    )
    to_create = [
        UserPreferences(user_id=u.id, theme="dim")
        for u in User.objects.exclude(id__in=existing_user_ids)
    ]
    UserPreferences.objects.bulk_create(to_create)


def unbackfill(apps, schema_editor):
    # Reverse is intentionally a no-op — we can't tell which rows were created
    # by the backfill vs by the signal afterward, so deleting them all would
    # be wrong. To fully undo, reverse 0003 (drops the table entirely).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_userpreferences"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=unbackfill),
    ]