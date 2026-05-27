from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("request-creator/", views.request_creator_view, name="request_creator"),
    path("creator-status/", views.creator_request_status_view, name="creator_status"),
    path("creator-requests/", views.creator_requests_admin_view, name="creator_requests_admin"),
    path("creator-requests/<int:pk>/approve/", views.approve_creator_request, name="approve_creator_request"),
    path("creator-requests/<int:pk>/reject/", views.reject_creator_request, name="reject_creator_request"),

    path("preferences/theme/", views.save_theme_preference, name="save_theme"),

    # MUST stay last: this greedy `<str:username>/` pattern would otherwise
    # swallow `request-creator/`, `creator-status/`, etc.
    path("<str:username>/", views.creator_profile, name="creator_profile"),
]
