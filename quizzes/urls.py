from django.urls import path

from . import views

app_name = "quizzes"

urlpatterns = [
    # Creator dashboard
    path("my/quizzes/", views.my_quizzes, name="my_quizzes"),
    path("my/quizzes/new/", views.quiz_create, name="quiz_create"),
    path("my/quizzes/<slug:slug>/", views.quiz_detail, name="detail"),
    path("my/quizzes/<slug:slug>/edit/", views.quiz_edit, name="quiz_edit"),
    path("my/quizzes/<slug:slug>/delete/", views.quiz_delete, name="quiz_delete"),
    path("my/quizzes/<slug:slug>/publish/", views.quiz_toggle_publish, name="quiz_toggle_publish"),
    path("my/quizzes/<slug:slug>/active/", views.quiz_toggle_active, name="quiz_toggle_active"),

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
]
