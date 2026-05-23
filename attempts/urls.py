from django.urls import path

from . import views

app_name = "attempts"

urlpatterns = [
    path("q/<slug:slug>/take/", views.quiz_start, name="start"),
    path("attempts/<int:attempt_id>/", views.attempt_run, name="run"),
    path("attempts/<int:attempt_id>/answer/<int:question_id>/", views.answer_save, name="answer_save"),
    path("attempts/<int:attempt_id>/submit/", views.attempt_submit_confirm, name="submit_confirm"),
    path("attempts/<int:attempt_id>/finalize/", views.attempt_submit, name="submit"),
    path("attempts/<int:attempt_id>/result/", views.attempt_result, name="result"),
    path("attempts/<int:attempt_id>/heartbeat/", views.attempt_heartbeat, name="heartbeat"),
    path("q/<slug:slug>/leaderboard/", views.quiz_leaderboard, name="leaderboard"),
]
