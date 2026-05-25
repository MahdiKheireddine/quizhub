from django.urls import path

from . import views

app_name = "quizzes"

urlpatterns = [
    # Public browse + public detail
    path("q/", views.browse_quizzes, name="browse"),
    path("q/<slug:slug>/", views.public_quiz_detail, name="public_detail"),
    path("q/<slug:slug>/request-access/", views.request_join, name="request_join"),

    # Creator dashboard
    path("my/dashboard/", views.creator_dashboard, name="creator_dashboard"),
    path("my/quizzes/", views.my_quizzes, name="my_quizzes"),
    path("my/quizzes/new/", views.quiz_create, name="quiz_create"),
    path("my/quizzes/<slug:slug>/", views.quiz_detail, name="detail"),
    path("my/quizzes/<slug:slug>/edit/", views.quiz_edit, name="quiz_edit"),
    path("my/quizzes/<slug:slug>/delete/", views.quiz_delete, name="quiz_delete"),
    path("my/quizzes/<slug:slug>/publish/", views.quiz_toggle_publish, name="quiz_toggle_publish"),
    path("my/quizzes/<slug:slug>/active/", views.quiz_toggle_active, name="quiz_toggle_active"),
    path("my/quizzes/<slug:slug>/release-results/", views.quiz_release_results, name="quiz_release_results"),

    # Question editor (HTMX-driven)
    path("my/quizzes/<slug:slug>/edit-questions/", views.edit_questions, name="edit_questions"),
    path("my/quizzes/<slug:slug>/questions/create/", views.question_create, name="question_create"),
    path("questions/<int:question_id>/update/", views.question_update, name="question_update"),
    path("questions/<int:question_id>/delete/", views.question_delete, name="question_delete"),
    path("questions/<int:question_id>/move/<str:direction>/", views.question_move, name="question_move"),

    # Choices
    path("questions/<int:question_id>/choices/create/", views.choice_create, name="choice_create"),
    path("choices/<int:choice_id>/update/", views.choice_update, name="choice_update"),
    path("choices/<int:choice_id>/toggle-correct/", views.choice_toggle_correct, name="choice_toggle_correct"),
    path("choices/<int:choice_id>/delete/", views.choice_delete, name="choice_delete"),

    # Invitations & join requests: creator side
    path("my/quizzes/<slug:slug>/invitations/", views.quiz_invitations, name="quiz_invitations"),
    path("invitations/<int:invitation_id>/cancel/", views.invitation_cancel, name="invitation_cancel"),
    path("join-requests/<int:join_request_id>/<str:action>/", views.join_request_review, name="join_request_review"),

    # Invitations & join requests: user side
    path("my/invitations/", views.my_invitations, name="my_invitations"),
    path("invitations/<int:invitation_id>/respond/<str:action>/", views.invitation_respond, name="invitation_respond"),
    path("my/join-requests/", views.my_join_requests, name="my_join_requests"),
]
