from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "is_creator_approved",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("role", "is_creator_approved", "is_staff", "is_active")
    search_fields = ("username", "email")

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Quiz platform", {"fields": ("role", "is_creator_approved", "bio")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Quiz platform", {"fields": ("role", "is_creator_approved", "bio")}),
    )
