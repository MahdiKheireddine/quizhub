from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import CreatorRequest, User


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


@admin.register(CreatorRequest)
class CreatorRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at", "reviewed_by", "reviewed_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email", "reason")
    readonly_fields = ("created_at", "reviewed_at", "reviewed_by")
    actions = ("approve_selected", "reject_selected")

    @admin.action(description="Approve selected requests")
    def approve_selected(self, request, queryset):
        pending = queryset.filter(status=CreatorRequest.Status.PENDING)
        approved = 0
        for cr in pending:
            cr.approve(request.user)
            approved += 1
        skipped = queryset.count() - approved
        self.message_user(
            request,
            f"Approved {approved} request(s)."
            + (f" Skipped {skipped} already-reviewed." if skipped else ""),
            level=messages.SUCCESS if approved else messages.WARNING,
        )

    @admin.action(description="Reject selected requests")
    def reject_selected(self, request, queryset):
        pending = queryset.filter(status=CreatorRequest.Status.PENDING)
        rejected = 0
        for cr in pending:
            cr.reject(request.user)
            rejected += 1
        skipped = queryset.count() - rejected
        self.message_user(
            request,
            f"Rejected {rejected} request(s)."
            + (f" Skipped {skipped} already-reviewed." if skipped else ""),
            level=messages.SUCCESS if rejected else messages.WARNING,
        )
