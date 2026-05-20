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
]
